# mitm-proxy-example

mitmproxy 기반 **크롤러용 HTTP(S) 스냅샷 캐시 프록시**.

> mitmproxy 개념/동작 원리는 → [what-is-mitm-proxy.md](./what-is-mitm-proxy.md)
> 설계 결정은 [ADR](adr/0001%20스냅샷%20캐시와%20로컬%20실행.md), 과거 작업 기록은 [history.md](history.md)를 참고한다.

---

## 왜 필요한가

자작 뉴스 크롤러를 개발하면서 18개 IT/AI 사이트(→ [target-sites.txt](./target-sites.txt))에서
사이트별 100~500건, 총 1,900~9,500건 규모의 문서를 수집한다.

크롤러를 **반복 실행·디버깅하는 동안 실사이트를 매번 때리면 차단된다.** 이 프록시는
최초 한 번만 실제 사이트에 접근해 응답을 디스크에 저장하고, 이후 크롤러가 같은 URL 을
요청하면 네트워크 대신 캐시에서 응답을 돌려준다. 즉 **봉인된 스냅샷 환경**을 만드는 것이
목표다.

---

## 동작 모드 — ALLOW(허용) / BLOCK(차단)

환경변수 `MITM_CACHE_MODE` 로 두 가지 모드를 전환한다. 아래 캐시 동작은 `target-sites.txt`의 대상 호스트에 적용한다. 목록 밖 호스트는 통과한다.

| 모드 | 값 | 용도 | 캐시 미스 시 |
|---|---|---|---|
| **ALLOW(허용)** | `allow` *(기본)* | 사전 캐싱 단계 | 실서버로 통과 후 응답 저장 |
| **BLOCK(차단)** | `block` | 크롤러 개발·디버깅 단계 | `504 Gateway Timeout` 즉시 반환, 실서버 접근 안 함 |

### 두 모드 전환

```sh
# ALLOW(허용) — 기본값. 캐시에 없는 URL 은 실사이트로 나가서 저장
docker compose down && docker compose up -d

# BLOCK(차단) — 캐시에 없는 URL 은 504 로 즉시 차단. 실사이트 접근 0
docker compose down && MITM_CACHE_MODE=block docker compose up -d
```

기동 시 addon 이 현재 모드를 로그에 출력한다:

```
[INIT] mode=ALLOW(허용)
[INIT] allowed host suffixes (18): engadget.com, gizmodo.com, ...
```

### 로그 태그

| 태그 | 의미 |
|---|---|
| `[HIT]` | 캐시에서 응답 반환 (네트워크 경유 없음) |
| `[MISS]` | ALLOW 모드에서 캐시 없음, 실서버로 통과 중 |
| `[SAVE]` | 실서버 응답을 디스크에 저장 완료 |
| `[BLOCK]` | BLOCK 모드에서 캐시 없음, 504 로 차단 |
| `[SKIP]` | 화이트리스트(`target-sites.txt`) 밖 호스트, 캐시 로직 건너뜀 |

---

## 빠른 시작 (Quickstart)

### 1. 컨테이너 기동

```sh
docker compose up -d
docker compose logs -f mitmproxy   # 다른 터미널에서 로그 모니터링
```

기동 로그에 `[INIT] mode=ALLOW(허용)` + `allowed host suffixes (18)` 이 뜨면 정상.

### 로컬 CA와 접근 범위

처음 실행하면 mitmproxy가 `ca/`에 설치별 CA를 생성한다. 인증서와 개인키는 저장소에 포함하지 않는다.
클라이언트에 등록할 파일은 공개 인증서인 `ca/mitmproxy-ca-cert.pem`이다. `mitmproxy-ca.pem`과 `.p12` 개인키 파일을 공유하지 않는다.
이전 저장소의 CA를 등록한 환경에서는 기존 CA의 신뢰를 해제하고 새로 생성한 CA를 등록해야 한다.

Compose는 프록시 포트를 `127.0.0.1:8080`에만 노출한다. 시스템 프록시나 OS 인증서 저장소를 자동으로 변경하지 않는다.

### 2. 프록시 경유 테스트 (curl)

```sh
# 타겟 사이트 (engadget.com) — 첫 호출: [MISS] → [SAVE], 두 번째: [HIT]
curl -x http://127.0.0.1:8080 -k https://www.engadget.com/ -o /dev/null -s -w "%{http_code} %{time_total}s\n"
curl -x http://127.0.0.1:8080 -k https://www.engadget.com/ -o /dev/null -s -w "%{http_code} %{time_total}s\n"

# 화이트리스트 밖 호스트 (naver) — mitmproxy 가 터널링만, addon 미경유
curl -x http://127.0.0.1:8080 -k https://www.naver.com/ -o /dev/null -s -w "%{http_code} %{time_total}s\n"
```

- `-x http://127.0.0.1:8080` : curl 에만 프록시 지정 (시스템 프록시 안 건드림)
- `-k` : mitmproxy 의 가짜 인증서를 검증 없이 수용 (본격 사용 시 CA 등록 필요, 아래 참조)

### 3. 캐시 상태 확인

```sh
ls cache/ | wc -l        # 총 파일 수
du -sh cache/            # 총 크기
```

---

## 사용 가이드 — 클라이언트별

이 프록시는 **시스템 전체 프록시를 건드리지 않는다.** 프록시를 사용할 클라이언트
(Firefox, 크롤러, curl)에만 개별적으로 지정한다. 이 방식의 장점:

- sudo 불필요
- OS 백그라운드(iCloud, 푸시, 업데이트) 및 다른 앱에 영향 0
- 컨테이너 장애 시 "전체 인터넷 먹통" 사고 없음
- 환경변수 토글로 on/off

### A. Firefox 로 수동 캐싱

SPA, 로그인 벽, 무한스크롤처럼 크롤러로 긁기 어려운 페이지를 사람이 직접 돌아다니며
캐시에 채울 때 사용한다.

#### 1. 프록시 설정
1. Firefox 설정 → 일반 → 네트워크 설정 → **"수동 프록시 설정"**
2. HTTP 프록시: `127.0.0.1`, 포트: `8080`
3. **"HTTPS 에도 이 프록시를 사용"** 체크
4. "프록시 사용 안 함" 필드는 기본값 유지 (`localhost, 127.0.0.1/8, ::1`)

#### 2. CA 인증서 등록 (한 번만)

Firefox 는 macOS 시스템 키체인과 별도의 자체 인증서 저장소를 쓰므로 별도 등록 필요.

1. `about:preferences#privacy` 페이지로 이동
2. 맨 아래 "인증서" → **"인증서 보기"**
3. **"기관"** 탭 → **"가져오기"**
4. 파일 선택:
   ```
   <프로젝트>/ca/mitmproxy-ca-cert.pem
   ```
5. **"이 인증 기관이 웹 사이트를 식별하는 것을 신뢰"** 체크

#### 3. 검증

Firefox 에서 `https://www.engadget.com/` 접속. 경고 없이 정상 로드되면 성공.
`docker compose logs -f mitmproxy` 에 `[MISS]` / `[SAVE]` 대량 출력됨.

Firefox 로 캐싱한 내용과 크롤러가 만드는 캐시는 **같은 `cache/` 디렉토리를 공유**
하므로, Firefox 로 사전 탐색 후 크롤러로 본격 수집하면 된다.

### B. curl / 셸에서 일회성 사용

```sh
curl -x http://127.0.0.1:8080 -k https://www.engadget.com/
```

또는 환경변수:

```sh
export HTTPS_PROXY=http://127.0.0.1:8080
export HTTP_PROXY=http://127.0.0.1:8080
export NO_PROXY=localhost,127.0.0.1
curl -k https://www.engadget.com/
```

### C. 크롤러에서 사용

#### Python `requests`

```python
import requests

proxies = {
    "http":  "http://127.0.0.1:8080",
    "https": "http://127.0.0.1:8080",
}
# 방법 1: mitmproxy CA 를 verify 에 지정
resp = requests.get(
    "https://www.engadget.com/",
    proxies=proxies,
    verify="ca/mitmproxy-ca-cert.pem",
)
```

#### Python `httpx`

```python
import httpx

with httpx.Client(
    proxy="http://127.0.0.1:8080",
    verify="ca/mitmproxy-ca-cert.pem",
) as client:
    resp = client.get("https://www.engadget.com/")
```

#### Playwright / Puppeteer

```python
# Playwright
browser = playwright.chromium.launch(
    proxy={"server": "http://127.0.0.1:8080"},
    args=["--ignore-certificate-errors"],  # 또는 CA 를 브라우저 프로필에 등록
)
```

#### 환경변수만으로

```sh
HTTPS_PROXY=http://127.0.0.1:8080 \
HTTP_PROXY=http://127.0.0.1:8080  \
REQUESTS_CA_BUNDLE=./ca/mitmproxy-ca-cert.pem \
python crawler.py
```

---

## 수집→디버깅 워크플로우

권장 작업 순서:

```
(1) ALLOW 모드 기동
    ↓
(2) Firefox 로 로그인·쿠키 동의 등 사람 개입이 필요한 화면 처리
    ↓
(3) ALLOW 모드에서 크롤러 한 번 실행 → 모든 응답이 캐시에 저장됨
    ↓
(4) BLOCK 모드로 전환
    ↓
(5) 크롤러 반복 실행·디버깅. 캐시 미스는 504 로 차단되므로 실사이트 무접근
    ↓
(6) 캐싱 범위 확장이 필요하면 다시 ALLOW 모드로 돌아가 (3) 단계 반복
```

---

## 캐시 대상 사이트 관리

캐시 대상 호스트는 **두 곳**에서 관리한다.

### 1. `target-sites.txt` (addon 화이트리스트)

파일 포맷: `이름 | URL | 호스트(eTLD+1)`

addon 이 기동 시 3번째 컬럼을 파싱해 `ALLOWED_HOST_SUFFIXES` 로 로드한다.
suffix 매칭이므로 `www.engadget.com`, `news.engadget.com` 모두 `engadget.com` 에 매칭.

화이트리스트 밖 호스트는 addon 에서 `[SKIP]` 로그만 남기고 캐시 로직을 건너뛴다.

### 2. `config.yaml` 의 `allow_hosts` (mitmproxy 레벨)

mitmproxy 가 TLS 가로채기를 할 호스트를 `host:port` 정규식으로 지정.
화이트리스트 밖 호스트는 **TLS 를 쪼개지 않고 CONNECT 터널 그대로 통과**시킨다.
→ 가짜 인증서를 내밀지 않으므로 cert pinning 앱(은행 등) 이 깨지지 않음.

### 추가/제거 절차

1. `target-sites.txt` 에 항목 추가
2. `config.yaml` 의 `allow_hosts:` 에 대응하는 정규식 추가
3. 재시작:
   ```sh
   docker compose restart mitmproxy
   ```

---

## 오프라인 재생 검증

캐시가 네트워크 없이도 동작하는지 확실히 확인하는 방법:

1. ALLOW 모드에서 대상 페이지 한 번 방문해 캐시를 채운다
2. Mac Wi-Fi OFF
3. Firefox 에서 같은 페이지 강력 새로고침 (`Cmd+Shift+R`)
4. 페이지가 정상 뜨고 로그가 전부 `[HIT]` 이면 성공

비교용으로 같은 오프라인 상태에서 naver 같은 화이트리스트 밖 사이트를 열어
접속이 안 되는 것도 확인하면 명확해진다.

> 동작 원리: `config.yaml` 의 `connection_strategy: lazy` 가 업스트림 사전 연결을
> 막는다. addon 의 `request()` 훅이 `flow.response` 를 캐시에서 채우면 mitmproxy 는
> 실서버에 연결조차 시도하지 않는다.

---

## 구성

| 파일 | 역할 |
|---|---|
| `cache_addon.py` | mitmproxy addon. 화이트리스트 + 캐시 + 모드 로직 |
| `config.yaml` | mitmproxy 옵션 (`allow_hosts`, `connection_strategy` 등) |
| `docker-compose.yml` | 공식 mitmproxy 이미지로 컨테이너 기동, 환경변수 주입 |
| `target-sites.txt` | 캐시 대상 사이트 목록 (addon 화이트리스트 소스) |
| `ca/` | 첫 실행 시 생성하는 로컬 CA. 개인키를 포함하므로 Git에서 제외 |
| `cache/` | 캐시된 응답 (한 요청 = 한 JSON 파일, 파일명 = sha256(method+URL)) |
| `README.md` | 본 문서 |
| `what-is-mitm-proxy.md` | mitmproxy 개념 해설 |
| `실록.md` | 프로젝트 작업 이력 (append-only) |

---

## 알려진 제약

- BLOCK 모드는 허용 목록에 포함된 요청의 캐시 미스만 차단한다. 허용 목록 밖 호스트는 통과하므로 전체 네트워크를 차단하는 모드가 아니다.
- 캐시 키는 HTTP 메서드와 전체 URL만 사용한다. POST 본문, Cookie, Authorization, `Vary` 차이는 구분하지 않으므로 로그인 세션이나 여러 사용자가 공유하는 캐시로 사용하지 않는다.
- 응답 헤더와 본문을 그대로 저장한다. 캐시와 로그에는 쿠키, URL 파라미터, 개인정보가 포함될 수 있으므로 공개하거나 커밋하지 않는다.

- **경로 단위 필터링 불가.** `allow_hosts`/`ignore_hosts` 는 CONNECT 단계에서 동작
  하므로 `host:port` 매칭만 된다. addon 레벨에서 `flow.request.path` 필터링은
  기술적으로 가능하지만, 본문 HTML 외 서브리소스(CSS/JS/XHR) 누락 시 크롤러 동작이
  비결정적이 되고 미스 시 실서버로 빠져나가므로 **이 시나리오에선 도입하지 않는다.**
  호스트 단위 화이트리스트만 유지한다.
- **캐시 내역 불투명.** 파일명이 `sha256(method+URL).json` 이라 현재 어떤 URL 이
  캐시됐는지 직접 확인할 수 없다. → 로드맵의 `cache/index.jsonl` 경량 인덱스로 해결 예정.
- **warcprox/pywb 대안 기각.** 자작 크롤러라 WARC 포맷 호환성 이득이 없고, 수집
  규모(~9,500건)가 dedup/CDX 인덱싱 없이도 관리 가능하다.

---

## 용량 가늠 (참고)

1GB / 사이트 예산 기준, engadget 같이 무거운 사이트에서:

| 수집 방식 | 기사당 평균 | 1GB 당 기사 |
|---|---:|---:|
| Firefox 수동 (공통 리소스 공유) | ~1 MB | ~1,000 |
| 크롤러 + 본문 이미지 | ~500 KB | ~2,000 |
| 크롤러 HTML only | ~200 KB | ~5,000 |

20GB 상한 가정 시 목표(9,500 기사) 대비 최소 2배, 최대 10배 여유. 상세 근거는
[실록.md](history.md) 의 "캐시 용량 분석" 항목 참조.

---

## 로드맵

- [x] ~~`cache_addon.py` strict 모드 옵션~~ → **ALLOW/BLOCK 모드로 구현 완료**
- [ ] `cache/index.jsonl` 경량 캐시 인덱스 (URL/메서드/상태/해시/시각/크기 추적)
- [ ] 광고/트래커 도메인 `EXCLUDED_HOST_SUFFIXES` 확장 (특히 Yahoo 분석 도메인)
- [ ] 사전 캐싱 단계에서 쿼리스트링 정규화 규칙 (크롤러 URL과 일치 보장)

---

## 트러블슈팅

### Firefox 에서 "경고: 보안 위험"
mitmproxy CA 가 Firefox 인증서 저장소에 등록 안 됨.
"사용 가이드 — A. Firefox > 2. CA 인증서 등록" 단계 수행.

### `docker compose logs` 가 비어있음
TTY 부족. `docker-compose.yml` 에 `tty: true` 있는지 확인.

### 캐시 HIT 인데 오프라인에서 페이지가 안 뜸
`connection_strategy: lazy` 가 `config.yaml` 에 있는지 확인.

### 기동 로그에 `killed by block_global`
Docker NAT 트래픽을 mitmproxy 가 외부 악용 시도로 간주하고 차단.
`config.yaml` 에 `block_global: false` 있는지 확인.

### 등록 안 한 사이트의 트래픽까지 캐시됨
- `config.yaml` 의 `allow_hosts` 확인 (비어있으면 모든 호스트 가로채기 대상)
- addon 기동 로그 `[INIT] allowed host suffixes (N): ...` 의 N 확인. 0 이면
  `target-sites.txt` 마운트 또는 파싱 실패

### BLOCK 모드에서 이미 수집한 기사도 차단됨
쿼리스트링 차이(타임스탬프·트래킹 파라미터)로 캐시 키가 달라져 미스 발생 중.
현재는 URL 전체를 해싱하므로 쿼리가 다르면 다른 캐시 파일. 로드맵의 "쿼리스트링
정규화 규칙" 항목 참조.

### BLOCK 모드에서 엉뚱한 504 가 캐싱됨
과거 버그(BLOCK 합성 응답이 저장되던 이슈)의 잔재일 수 있음. 수정 완료됐으나
과거에 돌린 적 있으면 `cache/` 에 오염 파일이 남아있을 수 있음. 오염 파일 정리:

```sh
python3 -c "
import json
from pathlib import Path
n = 0
for f in Path('cache').glob('*.json'):
    try:
        d = json.loads(f.read_text())
        if d.get('status_code') == 504 and any(
            k.lower() == 'x-cache' and v == 'BLOCK'
            for k, v in d.get('headers', {}).items()
        ):
            f.unlink()
            n += 1
    except: pass
print(f'삭제: {n}')
"
```

---

## 참고 문서

- [mitmproxy 공식 문서](https://docs.mitmproxy.org/)
- [what-is-mitm-proxy.md](./what-is-mitm-proxy.md) — mitmproxy 개념 해설
- [실록.md](history.md) — 프로젝트 작업 이력 및 의사결정 기록

## 라이선스

프로젝트 코드는 [MIT License](LICENSE)를 따른다. mitmproxy에는 원본 프로젝트의 라이선스가 적용된다.
