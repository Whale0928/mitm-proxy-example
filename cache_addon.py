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
from pathlib import Path

from mitmproxy import http


# ─────────────────────────────────────────────────────────────
# Step 0. 캐시 디렉토리 준비
# ─────────────────────────────────────────────────────────────
# 스크립트 옆에 ./cache 디렉토리를 만들어 응답을 파일 단위로 저장한다.
# 한 요청 = 한 파일 (파일명은 요청에서 만든 해시값).
CACHE_DIR = Path(__file__).parent / "cache"
CACHE_DIR.mkdir(exist_ok=True)


# ─────────────────────────────────────────────────────────────
# Step 0-1. 캐시/가로채기 제외 호스트
# ─────────────────────────────────────────────────────────────
# 여기에 들어간 호스트는 캐시에 저장하지도 않고, 캐시에서 응답하지도 않는다.
# (Claude Code 같은 자체 도구의 트래픽이 캐시에 들어가는 것을 막기 위함)
#
# 주의: addon 단의 차단은 "캐시 동작만" 막는 것이고, mitmproxy 자체의 TLS
# 가로채기는 여전히 일어난다. TLS 가로채기까지 완전히 우회하려면 mitmdump
# 실행 시 다음 옵션을 함께 줘야 한다:
#
#     mitmdump -s cache_addon.py --ignore-hosts '(^|\.)anthropic\.com$'
#
EXCLUDED_HOST_SUFFIXES = (
    "anthropic.com",
)


def _is_excluded(request: http.Request) -> bool:
    host = request.pretty_host or ""
    return any(host == s or host.endswith("." + s) for s in EXCLUDED_HOST_SUFFIXES)


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
    if _is_excluded(flow.request):
        # 제외 호스트: 캐시 로직을 전혀 적용하지 않고 그대로 통과시킨다.
        print(f"[SKIP] {flow.request.method} {flow.request.url}")
        return

    path = _cache_path(flow.request)

    if not path.exists():
        # 캐시 미스: 일단 통과시키면 mitmproxy가 실제 서버로 보낸다.
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
    if _is_excluded(flow.request):
        # 제외 호스트는 저장도 하지 않는다.
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
