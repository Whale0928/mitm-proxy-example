# TODO

다음 세션에서 이어서 할 일 메모.

## 현재 상태

- `docker compose up -d` 로 mitmproxy 컨테이너가 정상 기동됨
- `config.yaml` 이 `~/.mitmproxy/config.yaml` 경로로 마운트돼 자동 로드됨
  (별도의 `--conf` 옵션 없음 — mitmproxy 12.x 는 `--conf` 플래그가 없다)
- `connection_strategy: lazy`, `block_global: false`, `termlog_verbosity: warn`,
  `flow_detail: 0` 등 기본 동작 옵션은 정상 동작 확인 완료
- 호스트 → 컨테이너 cache 디렉토리 공유 및 HIT/MISS/SAVE 로그 정상 확인 완료

## 미해결 — allow_hosts 동작 조사 필요

### 시도한 것
`config.yaml` 에 18개 타겟 사이트를 `allow_hosts` whitelist 로 지정했다.

처음 작성:
```yaml
allow_hosts:
  - (^|\.)engadget\.com$
  - ...
```

→ 매칭 안 됨. mitmproxy 공식 문서에 따르면 `allow_hosts` / `ignore_hosts` 는
`"host:port"` 문자열에 매칭되므로 패턴에 `:\d+$` 가 필요하다.

다음 수정:
```yaml
allow_hosts:
  - ^(.+\.)?engadget\.com:\d+$
  - ...
```

→ 브라우저에서 **allow 리스트에 없는 모든 사이트** (naver.com 등) 로의
   접속이 타임아웃. curl 테스트에서도 `httpbin.org` 가 timeout.

### 원인 가설
`allow_hosts` 가 regular proxy 모드에서 매칭 안 되는 호스트를
- "터널링으로 그냥 통과" (원했던 동작)
- "연결 차단"

중 어느 쪽인지 실제 동작이 분명하지 않다. 과거 `#6554` 버그로 allow_hosts /
ignore_hosts 모두 연결을 닫던 문제가 있었고 `#6559` 에서 고쳐졌으나, 현재
설치 버전에서의 실제 동작을 소스로 직접 확인해야 한다.

### 다음에 할 일

1. **mitmproxy 소스 / 최신 이슈 트래커에서 allow_hosts 실제 동작 확인.**
   - https://github.com/mitmproxy/mitmproxy/issues/6554 (과거 버그)
   - https://github.com/mitmproxy/mitmproxy/issues/6279 (domain 매칭 이슈)
   - https://docs.mitmproxy.org/stable/howto/ignore-domains/

2. 실제 동작이 "차단" 이면 접근 방식 변경:

   **옵션 A — addon 단 호스트 필터링**
   - mitmproxy 는 전부 MITM (현 상태)
   - `cache_addon.py` 에서 `allow_hosts` 내부 리스트를 두고 매칭 안 되는
     호스트는 캐시 저장 / 반환을 하지 않고 `[SKIP]` 로그만 남김
   - 단점: cert pinning 앱들이 여전히 handshake 실패 로그를 찍음

   **옵션 B — ignore_hosts 블랙리스트 유지**
   - 원래 방식으로 롤백
   - cert pinning / 노이즈 호스트만 ignore_hosts 에 올림
   - 단점: "화이트리스트" 의도와 거리가 있음. 관리 대상이 많아질 수 있음

3. 선택한 방향으로 `config.yaml` / `cache_addon.py` 수정 후 재검증.

## 참고 — 현재 비활성화된 allow_hosts

복구 시 참고용. 올바른 정규식 형태 (`host:port` 매칭):

```yaml
allow_hosts:
  - ^(.+\.)?engadget\.com:\d+$
  - ^(.+\.)?gizmodo\.com:\d+$
  - ^(.+\.)?marktechpost\.com:\d+$
  - ^(.+\.)?mit\.edu:\d+$                          # news.mit.edu
  - ^(.+\.)?theverge\.com:\d+$
  - ^(.+\.)?tomshardware\.com:\d+$
  - ^(.+\.)?wccftech\.com:\d+$
  - ^(.+\.)?yahoo\.com:\d+$                        # finance.yahoo.com
  - ^(.+\.)?businessinsider\.com:\d+$
  - ^(.+\.)?aibusiness\.com:\d+$
  - ^(.+\.)?artificialintelligence-news\.com:\d+$
  - ^(.+\.)?aitimes\.com:\d+$
  - ^(.+\.)?cnbc\.com:\d+$
  - ^(.+\.)?techcrunch\.com:\d+$
  - ^(.+\.)?trendforce\.com:\d+$
  - ^(.+\.)?venturebeat\.com:\d+$
  - ^(.+\.)?itworld\.co\.kr:\d+$
  - ^(.+\.)?aitimes\.kr:\d+$
```
