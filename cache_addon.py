"""
mitmproxy 캐시 addon 예제
=========================

목적:
- 처음 보는 요청은 실제 사이트로 나가서 응답을 디스크에 저장한다.
- 같은 요청이 다시 들어오면 디스크에서 읽어 그대로 반환한다 (네트워크 안 탐).
- 사이트가 바뀌어도 캐시는 그대로 유지된다 (개발용 고정 스냅샷).

실행:
    mitmdump -s cache_addon.py

테스트:
    curl -k -x http://localhost:8080 https://httpbin.org/get   # 1회: MISS + SAVE
    curl -k -x http://localhost:8080 https://httpbin.org/get   # 2회: HIT
"""

import base64
import hashlib
import json
import os
from pathlib import Path

from mitmproxy import http


# ─────────────────────────────────────────────────────────────
# Step -1. 동작 모드 (ALLOW / BLOCK)
# ─────────────────────────────────────────────────────────────
# 환경변수 MITM_CACHE_MODE 로 동작 모드를 선택한다. 기본값은 "allow".
#
# - ALLOW(허용) — 기본값
#     캐시 미스 시 실서버로 통과시키고 응답을 캐시에 저장한다.
#     타겟 사이트를 돌아다니면서 캐시를 채우는 수집 단계에서 사용.
#
# - BLOCK(차단)
#     캐시 미스 시 504 응답으로 즉시 차단. 실서버에 한 바이트도 안 보낸다.
#     크롤러 반복 실행·오프라인 디버깅 단계에서 사용. 이미 수집해둔 캐시로만
#     응답하고, 예상 못 한 URL 접근으로 실사이트가 차단될 위험을 원천 봉쇄.
#
# 토글 방법:
#   docker compose down && docker compose up -d                                 # ALLOW(허용) - 기본
#   docker compose down && MITM_CACHE_MODE=block docker compose up -d           # BLOCK(차단)
_MODE_RAW = os.environ.get("MITM_CACHE_MODE", "allow").strip().lower()
if _MODE_RAW not in ("allow", "block"):
    print(f"[WARN] invalid MITM_CACHE_MODE={_MODE_RAW!r}, falling back to 'allow'")
    _MODE_RAW = "allow"
MODE = _MODE_RAW
BLOCK_MODE = (MODE == "block")
_MODE_LABEL = {"allow": "ALLOW(허용)", "block": "BLOCK(차단)"}[MODE]


# ─────────────────────────────────────────────────────────────
# Step 0. 캐시 디렉토리 준비
# ─────────────────────────────────────────────────────────────
# 스크립트 옆에 ./cache 디렉토리를 만들어 응답을 파일 단위로 저장한다.
# 한 요청 = 한 파일 (파일명은 요청에서 만든 해시값).
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────
# Step 0-1. 캐시 대상 호스트 화이트리스트
# ─────────────────────────────────────────────────────────────
# target-sites.txt 에서 캐시 대상 호스트 목록을 읽어온다.
# 파일 형식: "이름 | URL | 호스트(eTLD+1)"  (# 으로 시작하는 줄은 주석)
# 세 번째 컬럼(호스트)만 추출해 suffix 매칭에 쓴다.
#
# 화이트리스트에 없는 호스트는 캐시에 저장되지도, 캐시에서 응답되지도 않고
# 그대로 실서버로 통과한다 ([SKIP] 로그만 찍힘). mitmproxy 자체의 TLS
# 가로채기는 여전히 일어나므로, cert pinning 을 하는 앱이 있다면 별도로
# config.yaml 의 ignore_hosts 에 추가해야 한다.
TARGET_SITES_FILE = Path(__file__).parent / "target-sites.txt"


def _load_allowed_suffixes(path: Path) -> tuple[str, ...]:
    if not path.exists():
        print(f"[WARN] target-sites.txt not found at {path}; allowing nothing")
        return ()
    suffixes: list[str] = []
    for line in path.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        parts = [p.strip() for p in line.split("|")]
        if len(parts) < 3:
            continue
        host = parts[2]
        if host and host not in suffixes:
            suffixes.append(host)
    return tuple(suffixes)


ALLOWED_HOST_SUFFIXES = _load_allowed_suffixes(TARGET_SITES_FILE)
print(f"[INIT] mode={_MODE_LABEL}")
print(f"[INIT] allowed host suffixes ({len(ALLOWED_HOST_SUFFIXES)}): "
      f"{', '.join(ALLOWED_HOST_SUFFIXES) or '(none)'}")


def _is_allowed(request: http.Request) -> bool:
    host = request.pretty_host or ""
    return any(host == s or host.endswith("." + s) for s in ALLOWED_HOST_SUFFIXES)


# ─────────────────────────────────────────────────────────────
# Step 1. 캐시 키 만들기
# ─────────────────────────────────────────────────────────────
# 같은 요청인지 판단하는 기준을 정한다.
# 여기서는 "HTTP 메서드 + 전체 URL"을 sha256으로 해싱해서 파일명으로 쓴다.
# (쿼리스트링은 URL에 포함되므로 자동으로 키에 반영된다)
def _cache_path(request: http.Request) -> Path:
    raw = f"{request.method}:{request.url}".encode()
    digest = hashlib.sha256(raw).hexdigest()
    return CACHE_DIR / f"{digest}.json"


# ─────────────────────────────────────────────────────────────
# Step 2. 요청 가로채기 — 캐시가 있으면 즉시 응답
# ─────────────────────────────────────────────────────────────
# mitmproxy는 클라이언트가 보낸 요청을 실제 서버로 보내기 직전에
# 이 함수를 호출한다. 여기서 flow.response 를 채워주면
# mitmproxy는 "아, 이미 응답이 있구나" 하고 외부로 나가지 않는다.
def request(flow: http.HTTPFlow) -> None:
    if not _is_allowed(flow.request):
        # 화이트리스트에 없는 호스트: 캐시 로직을 전혀 적용하지 않고
        # 그대로 실서버로 통과시킨다.
        print(f"[SKIP] {flow.request.method} {flow.request.url}")
        return

    path = _cache_path(flow.request)

    if not path.exists():
        if BLOCK_MODE:
            # BLOCK(차단) 모드: 실서버로 내보내지 않고 504 로 즉시 차단한다.
            # flow.response 를 채우면 mitmproxy 는 업스트림에 연결조차 안 함.
            print(f"[BLOCK] {flow.request.method} {flow.request.url}")
            flow.response = http.Response.make(
                504,
                b"mitm-cache: BLOCK mode - URL not in cache, upstream blocked\n",
                {
                    "Content-Type": "text/plain; charset=utf-8",
                    "X-Cache": "BLOCK",
                },
            )
            return
        # ALLOW(허용) 모드: 캐시 미스면 mitmproxy 가 실제 서버로 보낸다.
        # 실제 응답은 아래 response() 훅에서 저장한다.
        print(f"[MISS] {flow.request.method} {flow.request.url}")
        return

    # 캐시 히트: 디스크에서 응답을 읽어 flow.response 에 채워넣는다.
    with path.open("r", encoding="utf-8") as f:
        cached = json.load(f)

    # content 는 base64 로 저장돼 있으므로 디코딩해서 bytes 로 복원.
    content = base64.b64decode(cached["content_b64"])

    flow.response = http.Response.make(
        cached["status_code"],
        content,
        cached["headers"],
    )
    print(f"[HIT]  {flow.request.method} {flow.request.url}")


# ─────────────────────────────────────────────────────────────
# Step 3. 응답 가로채기 — 새 응답이면 디스크에 저장
# ─────────────────────────────────────────────────────────────
# 실제 서버에서 응답이 돌아온 직후 호출되는 훅.
# 캐시 미스였던 요청만 여기서 저장하면 된다.
def response(flow: http.HTTPFlow) -> None:
    if not _is_allowed(flow.request):
        # 화이트리스트 밖 호스트는 저장도 하지 않는다.
        return

    if flow.response and flow.response.headers.get("X-Cache") == "BLOCK":
        # BLOCK 모드에서 request() 훅이 합성한 504 차단 응답.
        # 이걸 저장하면 다음 요청부터 차단 응답이 영구 히트되어버린다.
        return

    path = _cache_path(flow.request)

    if path.exists():
        # 이미 캐시에 있는 응답이면 (= 위 request() 에서 만들어 넣은 응답)
        # 다시 저장할 필요 없다.
        return

    # 응답을 JSON 직렬화 가능한 dict 로 변환해 저장.
    # 응답 본문(content)은 바이너리일 수 있으므로 base64 로 인코딩한다.
    # (HTML/JSON 같은 텍스트도 동일하게 base64 처리하면 인코딩 이슈 없음)
    payload = {
        "url": flow.request.url,
        "method": flow.request.method,
        "status_code": flow.response.status_code,
        "headers": dict(flow.response.headers),
        "content_b64": base64.b64encode(flow.response.content).decode("ascii"),
    }
    with path.open("w", encoding="utf-8") as f:
        json.dump(payload, f, ensure_ascii=False, indent=2)

    print(f"[SAVE] {flow.request.method} {flow.request.url}")
