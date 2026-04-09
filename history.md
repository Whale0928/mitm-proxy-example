# mitm-proxy-example 실록

이 프로젝트의 모든 결정, 작업, 관찰, 취소 내역을 시간순으로 기록한다.
조선왕조실록의 원칙을 따른다:

1. **append-only** — 기존 항목은 절대 삭제·수정하지 않는다.
2. **명시적 취소** — 결정이 뒤집히면 원래 항목은 그대로 두고, 새 항목에서
   "20XX-XX-XX에 취소됨. 사유: ..." 라고 밝힌다.
3. **있는 그대로** — 실패, 오류, 혼란도 숨기지 않고 기록한다.
4. **새 항목은 파일 최하단에 append** 한다.

형식:
```
## YYYY-MM-DD · 세션 구분 · 제목
- 배경/상황
- 한 일
- 결과/관찰
- (필요 시) 취소 또는 보류 사유
```

---

## 2026-04-09 · 세션 A · 실록 개시 및 과거 작업 요약

다른 세션(세션 0)에서 이뤄진 논의와 본 세션(세션 A) 초반 작업을 실록에 편입.
아래는 사후 기록이므로 정확한 시각은 생략하고 논리 순서로만 기재한다.

### 과거 세션 요약 — 프로젝트 정체 정리
- **배경**: 자작 뉴스 크롤러 개발 중, 19개(후에 18개로 정리됨) IT/AI 사이트에
  사이트별 100~500건, 총 1,900~9,500건 규모 문서 수집 예정.
- **문제**: 크롤러 반복 실행·디버깅 중 실사이트 차단 리스크 존재.
- **결정**: mitmproxy + 자작 `cache_addon.py` 로 **봉인된 스냅샷 캐시 레이어**
  구축. 최초 1회만 실사이트 접근, 이후 크롤러는 캐시에서만 응답 수령.

### 과거 세션 결정 — 경로 필터링 도입 보류
- `allow_hosts` / `ignore_hosts` 는 `host:port` 매칭만 지원. 경로 필터링 불가.
- addon 레벨 `flow.request.path` 필터링은 기술적으로 가능하나, 서브리소스
  (CSS/JS/XHR) 누락 시 크롤러 동작 비결정적이 되고 미스 시 실서버 유출 위험.
- **결정**: 경로 필터링 도입하지 않음. 호스트 단위 화이트리스트만 유지.

### 과거 세션 결정 — warcprox/pywb 대안 기각
- 자작 크롤러라 WARC 포맷 호환성 이득 없음.
- 수집 규모(~9,500건)가 dedup/CDX 인덱싱 없이도 관리 가능.
- **결정**: 기존 mitmproxy + cache_addon 구성 유지.

### 세션 A — 문서 정비 (TODO.md 삭제, README 재구성)
- **배경**: 위 결정들로 기존 `TODO.md` 의 "allow_hosts 동작 조사 필요" 섹션이
  사실상 해결된 상태가 됨.
- **한 일**:
  - `TODO.md` 전체 삭제 (내용은 README 와 본 실록에 이관).
  - `README.md` 상단에 "왜 필요한가", "알려진 제약", "로드맵" 섹션 추가. 프로젝트
    정체를 "개발용 캐시" → "크롤러용 스냅샷 캐시"로 명시.
  - `config.yaml` 의 낡은 TODO 주석 제거, allow_hosts 는 여전히 비활성 상태로 둠.
- **결과**: 문서 최신화 완료.

### 세션 A — addon 레벨 호스트 화이트리스트 구현
- **배경**: `config.yaml` 의 `allow_hosts` 가 주석 처리된 상태라 모든 호스트가
  mitmproxy 에 의해 가로채져 `cache/` 가 오염될 수 있었음. 사용자는 "target-sites
  에 있는 18개 사이트만 캐시"되길 명확히 원함.
- **한 일**:
  - `docker-compose.yml` 에 `./target-sites.txt:/work/target-sites.txt:ro` 마운트
    추가.
  - `cache_addon.py` 에 `_load_allowed_suffixes()` 추가. `target-sites.txt` 의 3번째
    컬럼(호스트)을 파싱해 `ALLOWED_HOST_SUFFIXES` 튜플 생성.
  - 기존 `_is_excluded()` → `_is_allowed()` 로 교체. 화이트리스트 밖 호스트는
    `[SKIP]` 로그만 남기고 그대로 통과.
  - 기동 시 `[INIT] allowed host suffixes (N): ...` 로그 출력.
- **검증**: 파이썬 단독 파서 실행으로 18개 호스트 파싱 및 서브도메인 매칭 확인.
  - `www.engadget.com`, `finance.yahoo.com`, `news.mit.edu` → True
  - `naver.com`, `anthropic.com`, `evil-mit.edu.attacker.com` → False
- **결과**: addon 레벨 화이트리스트 동작. 단, mitmproxy 자체의 TLS 가로채기는
  여전히 전체 호스트에 대해 일어나는 상태.

### 세션 A — 사용자 테스트 관찰: 네이버 접속 불가
- **관찰**: 사용자가 프록시 켠 상태에서 네이버 접속 시도 → 접속 안 됨.
- **원인 추정**: mitmproxy 가 모든 호스트에 TLS 가로채기를 수행하므로 (allow_hosts
  미적용 상태), 네이버 측에서 어떤 이유로(HSTS, cert pinning, QUIC fallback 이슈
  등) 연결이 깨지는 것으로 보임.
- **사용자 요청**: `ignore_hosts` 에 "18개 빼고 전부" 같은 wildcard 가 없는지 문의.
- **답변**: mitmproxy 에는 이미 `allow_hosts` 옵션이 있으며, 이것이 정확히 "오직
  이 호스트들만 가로채고 나머지는 건드리지 않는다" 의미. 과거 TODO 에 기록된
  allow_hosts 타임아웃 문제는 당시 `connection_strategy: lazy` 등 설정이 미흡했을
  가능성이 있어, 현 상태에서 다시 시도하기로 결정.

### 세션 A — 실록 제도 개시
- **배경**: 다른 세션에서도 작업이 이어지므로 컨텍스트 유실 방지 필요. 사용자가
  "조선왕조실록" 방식의 append-only 기록을 요청.
- **결정**: 본 파일(`실록.md`) 개설. 모든 작업·결정·관찰·취소를 시간순으로
  기록. 기존 항목 삭제·수정 금지. 결정 번복 시 명시적으로 "취소됨" 기재.
- **한 일**: `실록.md` 생성, 과거 맥락을 본 문서에 편입.

### 세션 A — `config.yaml` 에 `allow_hosts` 재도입
- **배경**: 네이버 등 일반 사이트가 프록시 경유 시 끊기는 문제 해결 필요. 과거
  TODO 에 적혀있던 "allow_hosts 타임아웃" 이슈는 당시 `connection_strategy: lazy`
  미설정 등 다른 요인이었을 가능성이 큼. 현재 설정에서 재시도.
- **한 일**: `config.yaml` 에 target-sites.txt 기반 18개 호스트의 `host:port` 정규식
  (`^(.+\.)?<domain>:\d+$`) 을 `allow_hosts` 로 추가. 원칙: "오직 이 18개만
  가로채고, 나머지는 CONNECT 터널 통째로 통과". addon 레벨 화이트리스트는 그대로
  두어 이중 안전장치 유지.
- **결과**: `docker compose up -d --force-recreate` 로 컨테이너 재생성 성공.
  `docker compose ps` → `Up 4 seconds` 확인. `docker compose logs` 에 addon 기동
  메시지 `[INIT] allowed host suffixes (18): engadget.com, gizmodo.com, ...
  aitimes.kr` 정상 출력. 아직 실제 트래픽 유입은 없음(로그에 요청 없음).
- **후속**: 사용자가 시스템 프록시 설정(브라우저 또는 OS) 켜고 실제로 네이버
  접속되는지, 타겟 사이트 접속 시 `[MISS]`/`[SAVE]` 찍히는지 확인 필요.

### 세션 A — curl 경유 실제 동작 검증 (성공)
- **배경**: 시스템 프록시를 건드리기 전에 curl `-x` 옵션으로 프록시 경유 요청을
  보내 addon 동작과 allow_hosts 동작을 검증.
- **한 일**:
  - `curl -x http://127.0.0.1:8080 -k https://www.engadget.com/` → 1차 호출
  - 동일 호출 2차 반복
  - `curl -x http://127.0.0.1:8080 -k https://www.naver.com/` → 화이트리스트 밖
    호스트 동작 확인
- **결과**:

  | 호출 | HTTP | 시간 | addon 로그 |
  |---|---|---|---|
  | engadget 1차 | 200 | 2.091s | `[MISS] GET https://www.engadget.com/` → `[SAVE]` |
  | engadget 2차 | 200 | **0.029s** | `[HIT]  GET https://www.engadget.com/` |
  | naver | 200 | 0.375s | **로그 없음** (mitmproxy 레벨에서 터널링, addon 미경유) |

  - 캐시 파일 생성 확인: `cache/0a81f11844203eef7c29f5f429bce8ea0bd80bcb241d8dcc3fc12ff248b6c798.json` (408KB)
  - HIT 응답이 MISS 대비 약 70배 빠름 → 네트워크 경유 없음 확인
- **중요 관찰**: naver 가 addon 로그에 전혀 찍히지 않음 = mitmproxy 가
  `allow_hosts` 에 의해 CONNECT 단계에서 터널링만 하고 TLS 를 가로채지 않음.
  이는 과거 TODO 에 기록된 "allow_hosts 적용 시 타임아웃" 문제가 **현 설정
  (`connection_strategy: lazy` + 현재 mitmproxy 버전)에서 재현되지 않음**을 의미.
  과거 시도 당시의 문제 원인은 명확히 특정되지 않았으나, 현재는 정상 동작.
- **결론**: 의도한 아키텍처(18개 타겟만 가로채 캐시, 나머지는 통과) 가 실제로
  동작함을 검증 완료.

### 세션 A — 사용 방식 방침 결정: 시스템 프록시 미사용, 애플리케이션별 지정
- **배경**: 사용자가 "프록시 등록 안 했는데 어떻게 프록시를 탔냐" 고 의문 제기.
  검증용 curl 은 `-x http://127.0.0.1:8080` 옵션으로 curl 프로세스 단독으로만
  프록시 경유한 것이었음. 시스템 네트워크 설정(`networksetup ...`) 은 건드리지
  않은 상태.
- **결정**: 본 프로젝트에서는 **시스템 프록시를 사용하지 않는다.** 대신 각
  클라이언트(curl, 크롤러, 필요 시 브라우저) 에 개별적으로 `HTTPS_PROXY=...` 또는
  라이브러리 옵션으로 프록시를 지정하는 방식을 채택.
- **근거**:
  1. sudo 불필요
  2. iCloud/푸시/업데이트/기타 앱 등 OS 백그라운드에 영향 없음
  3. 환경변수 토글로 crawler on/off 가능
  4. 컨테이너 장애 시 "전체 인터넷 먹통" 사고 방지
  5. 크롤러가 어차피 라이브러리 단에서 프록시 지정 가능
- **보류**: README 사전 준비 섹션의 `networksetup` 관련 지침은 당장 삭제하지 않고
  "대안" 으로 격하하는 문서 수정이 필요할 수 있음. 지금은 방침만 실록에 기록하고
  문서는 후속 작업으로 둔다.

### 세션 A — Firefox 설정 완료 및 첫 실사용 (성공)
- **배경**: 위 방침에 따라 사용자가 Firefox 를 캐싱 전용 브라우저로 설정.
- **한 일**: 사용자가 Firefox 에서
  1. 연결 설정 → 수동 프록시 설정: HTTP `127.0.0.1:8080`, "HTTPS 에도 이 프록시를
     사용" 체크.
  2. 최초 engadget 접속 시 "보안 위험" 경고 발생 (예상된 동작: Firefox 가
     mitmproxy 의 가짜 CA 를 아직 모름).
  3. `about:preferences#privacy` → 인증서 보기 → 기관 탭 → 가져오기 →
     `<프로젝트>/ca/mitmproxy-ca-cert.pem`
     등록, "웹 사이트 식별 신뢰" 체크.
  4. engadget 메인 및 특정 기사 페이지 접속:
     `https://www.engadget.com/audio/speakers/fender-elie-review-handsome-speakeramp-hybrids-with-excellent-clarity-123000448.html`
- **결과** (docker compose logs 기준):

  | 지표 | 값 |
  |---|---|
  | 캐시 파일 수 | 164개 |
  | 캐시 크기 | 6.2MB |
  | `[MISS]` | 172 |
  | `[SAVE]` | 165 |
  | `[HIT]` | 36 (페이지 내 리소스 재사용 / 새로고침) |
  | `[SKIP]` | 3 (Firefox captive portal 감지: `detectportal.firefox.com`) |

  - 지정한 Fender 기사 URL 이 정상적으로 `[MISS] → [SAVE]` 됨.
  - 캐시된 호스트 목록: `www.engadget.com`, `guce.engadget.com`, `*.yahoo.com`
    (engadget 이 Yahoo Media 소속이라 Yahoo 트래커/API 호출이 섞여 있음. yahoo.com
    은 target-sites 에 있으므로 의도된 동작).
  - 화이트리스트 밖 호스트는 캐시에 전혀 들어오지 않음. `[SKIP]` 은 Firefox 자체
    상태 체크 요청(detectportal)으로 HTTP 평문이라 allow_hosts 적용 밖이었음 —
    addon 에서 즉시 SKIP 처리되어 캐시에 저장 안 됨.
- **결론**: Firefox 로 수동 탐색 + mitmproxy 캐시 레이어 조합이 의도대로 완전히
  동작함. 사용자는 이제 Firefox 로 타겟 사이트를 돌아다니며 사전 캐싱을 진행할
  수 있고, 같은 `cache/` 를 공유하는 크롤러는 추후 디버깅 실행 시 `[HIT]` 로
  오프라인 재생됨.

### 세션 A — 화이트리스트 외 호스트(naver) 재검증
- **배경**: 사용자가 "그럼 naver 는?" 재확인 요청. 과거 TODO 에 적혀있던
  "allow_hosts 적용 시 naver 타임아웃" 이슈가 재현되는지 명확히 기록 필요.
- **한 일**: `curl -x http://127.0.0.1:8080 -k https://www.naver.com/`
- **결과**:
  - HTTP 200, 0.409s, 256349 bytes 수신 → naver 정상 응답
  - `docker compose logs ... | grep naver` → 0건
- **해석**: `allow_hosts` 가 mitmproxy 레벨에서 naver.com 을 터널링만 수행.
  TLS 를 쪼개지 않으므로 addon flow 자체가 생성되지 않아 로그 0건. 크롤러/브라우저
  입장에서는 "프록시 경유는 했지만 내용은 mitmproxy 를 거치지 않은" 상태.
- **결론**: 과거 TODO 에 기록된 "allow_hosts 적용 시 naver 타임아웃" 이슈는
  **2026-04-09 현 시점 설정에서는 재현되지 않음.** 원인은 특정하지 못했으나
  가능한 추측: (1) 당시 `connection_strategy: lazy` 미적용, (2) config 경로 문제로
  옵션 미로드, (3) mitmproxy 버전 동작 차이. 과거 항목은 삭제하지 않고 본 기록으로
  해소 표시만 함.

### 세션 A — 오프라인 재생 가능 여부 질문 및 이론 설명
- **배경**: 사용자가 "인터넷을 끊으면 캐시된 페이지를 볼 수 있어야 하는데, 되는지"
  확인 요청.
- **답변 요지**:
  - `connection_strategy: lazy` 덕분에 mitmproxy 는 캐시 히트 시 업스트림에
    연결을 전혀 시도하지 않음. addon 의 `request()` 훅에서 `flow.response` 를
    채우는 순간 mitmproxy 는 "응답이 이미 있다" 고 판단하고 네트워크에 한 바이트도
    내보내지 않음.
  - 이미 HIT 호출 시간이 0.029s (MISS 2.091s 대비 약 70배 빠름)로 측정된 점이
    네트워크 미경유를 뒷받침.
  - 단, 페이지 하나는 수십~수백 개 서브리소스를 포함. **한 번이라도 온라인에서
    열어본 페이지**는 오프라인 재생이 대체로 잘 되지만, **처음 열어보는 페이지**는
    미스 → 실서버 시도 → 오프라인에선 실패. 기사 본문은 대체로 뜨되 일부 광고/
    트래킹/동적 API 는 깨질 수 있음.
- **후속 (검증 예정)**: 사용자가 직접 Wi-Fi 를 끄고 이미 캐싱된 Fender 기사 탭을
  강력 새로고침 해서 오프라인 재생 가능 여부 확인. 결과는 다음 항목에서 기록.

### 세션 A — 오프라인 재생 검증 완료 (성공)
- **배경**: 위 항목의 후속. 사용자가 직접 Wi-Fi OFF 상태에서 이미 캐싱된 Fender
  기사를 재생해보고 동작 여부 확인.
- **한 일**: 사용자가 Mac Wi-Fi 를 끄고 Firefox 에서 캐싱된 Fender 기사 탭을
  강력 새로고침.
- **결과**: 사용자 피드백 — "잘 되네, 인정한다."
- **결론**: `connection_strategy: lazy` + cache_addon 조합이 **완전 오프라인 상태
  에서도 캐시된 페이지를 재생**함을 실사용 검증으로 확인. 프로젝트의 핵심 목표
  (차단 회피용 봉인된 스냅샷 캐시) 의 기술적 기반이 동작함을 증명한 마일스톤.

### 세션 A — strict 모드 구현
- **배경**: 사용자 요청 — "타겟 중 캐싱 안 된 페이지는 차단하고, 실제 접근은
  안 하도록". README 로드맵에 있던 strict 모드 본격 구현.
- **설계**:
  - 환경변수 `MITM_CACHE_STRICT` 로 ON/OFF 토글 (기본 OFF).
  - ON 일 때 캐시 미스 발생 시 실서버 경유 대신 `504 Gateway Timeout` + 명확한
    에러 바디(`mitm-cache: strict mode - URL not in cache, upstream blocked`) 로
    즉시 차단. `X-Cache: BLOCK` 헤더로 식별.
  - `flow.response` 를 `request()` 훅에서 채우므로 mitmproxy 는 업스트림에
    연결조차 시도하지 않음.
- **구현**:
  - `cache_addon.py`:
    - `STRICT_MODE = os.environ.get("MITM_CACHE_STRICT", "").lower() in ("1", "true", "yes")`
    - `request()` 훅에 미스 + strict 시 504 합성 응답 분기 추가.
    - 기동 시 `[INIT] strict_mode=ON/OFF` 로그 출력.
    - 로그 태그 `[BLOCK]` 추가.
  - `docker-compose.yml` 에 `environment: - MITM_CACHE_STRICT=${MITM_CACHE_STRICT:-0}`
    추가하여 호스트 환경변수를 컨테이너에 전달.
- **1차 오류 — SyntaxError (em-dash)**:
  - 504 바디 bytes literal 에 em-dash(—) 를 썼다가 파이썬 `SyntaxError: bytes can
    only contain ASCII literal characters`. em-dash → 일반 하이픈(-) 으로 교체.
- **2차 오류 — 합성 응답이 캐시에 저장되는 버그 (치명적)**:
  - strict OFF 동작 확인 후 `MITM_CACHE_STRICT=1` 로 재기동하고 테스트 중 사용자가
    로그의 다량 에러를 발견하여 "키기 전에 로그 확인 한번 해봐" 지시.
    조사 결과, SyntaxError 는 수정 이전 과거 로그임을 확인. 옵션 2 선택 —
    `docker compose down` 으로 로그 초기화 후 `MITM_CACHE_STRICT=1 docker compose
    up -d` 로 재기동.
  - 첫 strict 검증 수행: 캐싱된 URL → HIT, 미캐싱 URL → BLOCK (504, 0.01s), naver
    → 터널링 200. 표면적으로는 의도대로 동작.
  - **그러나 로그에 `[BLOCK]` 뒤에 `[SAVE]` 가 같은 URL 로 찍히는 패턴 발견.**
    원인: `response()` 훅이 strict 모드가 합성한 504 응답도 "새 응답" 으로 판정해
    디스크에 저장하고 있었음. 이렇게 되면:
    1. 첫 요청 → BLOCK → 504 가 캐시로 저장됨
    2. 같은 URL 두 번째 요청 → 캐시 파일 존재 → HIT → 영구적으로 504 반환
    3. 이후 strict OFF 로 돌려도 해당 URL 은 영원히 504 가 반환됨
- **수정**:
  - `response()` 훅에 `flow.response.headers.get("X-Cache") == "BLOCK"` 이면 저장
    스킵하는 가드 추가.
  - `docker compose restart mitmproxy` 로 addon 재로드.
- **사후 정리 — 오염된 캐시 파일 스캔 및 삭제**:
  - 파이썬 스크립트로 `cache/*.json` 전수 조사: `status_code == 504` 이면서
    `X-Cache: BLOCK` 헤더가 포함된 파일 검출.
  - **총 412 파일 중 27 개가 오염된 BLOCK 캐시** 로 확인. 대부분 Yahoo
    트래커/분석 엔드포인트였으나, **실제 engadget 기사 URL 하나가 포함**되어
    있었음: `https://www.engadget.com/transportation/evs/uber-begins-testing-its-
    volkswagen-id-buzz-robotaxi-fleet-in-la-120000762.html`. 만약 정리하지 않았
    으면 이 기사 URL 은 나중에 strict OFF 에서 정상 캐싱을 시도해도 이미 캐시
    파일이 존재(504) 하므로 영원히 차단 응답을 반환했을 것.
  - 27 개 모두 삭제.
- **재검증**:
  - 같은 미캐싱 URL 을 연속 2회 호출 → 둘 다 `[BLOCK]` 로그 + 504 응답 (HIT 아님).
    → **504 가 캐시에 저장되지 않음을 확인.** 수정 반영됨.
- **결론**: strict 모드 동작 정상. 사용자가 원하던 "타겟 사이트의 캐싱된 페이지만
  응답, 미캐싱 URL 은 실사이트 접근 없이 차단" 동작 완성. 버그 발견 경위 포함
  실록에 기록.
- **운영 방법**:
  - 캐싱 단계: `docker compose down && docker compose up -d` (strict OFF)
  - 봉인 단계: `docker compose down && MITM_CACHE_STRICT=1 docker compose up -d`
- **교훈**: 합성 응답(mitmproxy 의 `request()` 훅에서 만든 response) 도 addon 의
  `response()` 훅을 거친다. 캐시 저장 로직이 있는 훅은 합성 응답을 식별해서 저장
  대상에서 제외해야 한다. 사용자가 로그를 꼼꼼히 본 덕분에 조기 발견 가능했음.

### 세션 A — 현재 캐시 상태 조사 (용어 정리 직전)
- **배경**: 용어 변경 작업 중 사용자 문의 — "지금 캐시에 저장 얼마나 된 거야?"
- **결과**:
  - 총 파일: 385 개, 디스크 8.5MB (본문 base64 기준 7.0MB)
  - 상태 코드: 200 (321), 204 (51), 302 (11), 404 (2), 504 BLOCK (0 — 정리됨)
  - 호스트 분포:
    - www.engadget.com: **38** (실제 기사/페이지)
    - *.yahoo.com 트래커 (noa/3p-geo/udc/pbs/ups/opus/pbd 등): 347 (총 90%)
    - guce.engadget.com: 1
  - 관찰: 페이지 하나 열 때 Yahoo 분석/광고 API 가 수십 건씩 호출되어 트래커가
    압도적 다수. engadget 이 Yahoo Media 소속이라 구조적 현상.
- **조치 없음**: 현 시점 8.5MB 는 미미해 즉각적 조치 불필요. 로드맵의
  `EXCLUDED_HOST_SUFFIXES` 확장 항목에 "특히 Yahoo 분석 도메인" 으로 구체화해둠.

### 세션 A — 모드 용어 확정: ALLOW(허용) / BLOCK(차단)
- **배경**: 기존 `MITM_CACHE_STRICT=0/1` 은 사용자 입장에서 직관이 약함. 모드에
  이름을 붙이자고 합의.
- **제안 과정**:
  1. 한글 1안: "수집 모드 / 봉인 모드". 직관적이나 영어 쌍도 필요.
  2. 영어 1안: "RECORD / REPLAY". 업계 표준 용어이나 VCR.py, Polly.js, rr,
     Replay.io 등 **이미 쓰이는 이름 공간**과 충돌 우려로 사용자가 기각.
  3. 영어 2안: "LIVE / VAULT". 독특하고 발음 명확하나 의미 전달이 비유적.
  4. 최종: 사용자가 **"허용 / 차단"** 제안. 영어로는 **ALLOW / BLOCK** 로 병기.
     방화벽·HTTP ACL 표준 용어이며 한영 모두 발음·의미 직관적.
- **결정**: 모드 이름은 **`ALLOW(허용)` / `BLOCK(차단)`** 로 확정. 문서·주석·로그
  라벨 모두 이 표기로 병기.
- **구현 변경**:
  - `cache_addon.py`:
    - 환경변수 `MITM_CACHE_STRICT` → `MITM_CACHE_MODE` 로 교체.
    - 값: `allow` (기본) / `block`. 잘못된 값은 경고 후 `allow` 로 폴백.
    - 내부 플래그 `STRICT_MODE` → `BLOCK_MODE`.
    - 기동 로그: `[INIT] mode=ALLOW(허용)` 또는 `[INIT] mode=BLOCK(차단)`.
    - 504 차단 응답 바디: `"mitm-cache: BLOCK mode - URL not in cache, upstream
      blocked"`.
    - 주석 전반을 새 용어로 정리.
  - `docker-compose.yml`:
    - `environment:` 에 `MITM_CACHE_MODE=${MITM_CACHE_MODE:-allow}` 로 교체.
    - 주석에 두 모드 설명 추가.
  - `README.md`:
    - 기존 "알려진 제약" 의 일부 항목(strict 모드 도입 예정 등) 제거.
    - 새로운 **"동작 모드 — ALLOW(허용) / BLOCK(차단)"** 섹션 추가. 표로 두 모드
      비교, 각 모드 기동 명령 및 로그 태그 명시.
    - 로드맵에서 strict 모드 항목 체크 표시, "ALLOW/BLOCK 모드로 구현 완료" 로 갱신.
    - 로드맵의 `EXCLUDED_HOST_SUFFIXES` 확장 항목에 "특히 Yahoo 분석 도메인" 메모
      추가.
- **로그 태그 방침**: 기존 `[HIT]` / `[MISS]` / `[SAVE]` / `[SKIP]` / `[BLOCK]` 는
  범용 HTTP 캐시 용어라 그대로 유지. 모드 이름(ALLOW/BLOCK) 과 로그 태그
  `[BLOCK]` 이 글자가 겹치지만 의미가 일치(BLOCK 모드에서 [BLOCK] 로그가 찍힘)
  하므로 혼동 없음.
- **검증**:
  - `docker compose down && docker compose up -d` 기동 시:
    - `[INIT] mode=ALLOW(허용)` 출력, 18개 호스트 로드, 기존 Fender 기사 등 `[HIT]`
      정상 반환, 백그라운드 Yahoo 분석 POST 는 `[MISS]` 로 새로 저장.
  - `docker compose down && MITM_CACHE_MODE=block docker compose up -d` 기동 시:
    - `[INIT] mode=BLOCK(차단)` 출력.
    - 미캐싱 URL `curl` → HTTP 504, 0.053s, 본문
      `mitm-cache: BLOCK mode - URL not in cache, upstream blocked`.
    - 캐싱된 URL → HTTP 200, 0.026s (`[HIT]`).
  - 검증 후 다시 ALLOW 모드(기본값)로 원위치.
- **마무리 상태**: 사용자는 현재 ALLOW(허용) 모드에서 Firefox/크롤러로 수집을
  계속할 수 있음. 봉인 단계로 넘어갈 때 `MITM_CACHE_MODE=block` 한 줄만 추가하면 됨.

### 세션 A — BLOCK 모드 실사용 검증 및 Yahoo HIT 성격 규명
- **배경**: 사용자가 직접 `MITM_CACHE_MODE=block docker compose up -d` 로 전환해
  Firefox 에서 engadget 을 탐색. 로그 확인 요청.
- **로그 집계**:
  - `[INIT]`: 2 (mode, allowed hosts)
  - `[HIT]`: 138
  - `[BLOCK]`: 282
  - `[MISS]`: **0**, `[SAVE]`: **0**, `[SKIP]`: 0
- **핵심 관찰**: `[MISS]`/`[SAVE]` 가 0건 = **실서버로 단 한 바이트도 나가지
  않음**. 282건의 미캐싱 요청이 전부 로컬 504 로 종료. BLOCK 모드 의도대로 동작.
- **BLOCK 건의 대부분**은 `noa.yahoo.com`, `3p-geo.yahoo.com`, `udc.yahoo.com` 등
  타임스탬프·랜덤 토큰을 URL 에 싣는 Yahoo 실시간 트래커. 매 요청마다 URL 이
  달라지므로 캐시 키 매칭이 안 되는 것이 정상.
- **engadget.com 기사 1건이 BLOCK**: `computing/laptops/asus-zenbook-a16-review-...`
  - 이건 ALLOW 모드에서 한 번도 안 열어본 기사라 BLOCK 됐음.
  - 사용자 입장에선 "봉인 계약대로 작동" — 사전 수집 범위 밖 URL 은 차단됨.
- **Yahoo HIT 들의 성격**:
  - `pbs.yahoo.com/cookie_sync`, `/openrtb2/auction`, `/setuid?bidder=...`
  - `pbd.yahoo.com/data/logs/taboola`, `/ay/v2/result?...`
  - `templates.cds.yahoo.com/remote/injection`
  - `nexus-gateway-prod.media.yahoo.com/?dd_resource=...`
  - 이유: URL 이 고정이거나 쿼리스트링이 안정적이라서 ALLOW 세션에서 수집된
    캐시와 매칭됨. 나머지 트래커(BLOCK 분류)는 매번 URL 이 다름.
  - 정체: 전부 **광고·트래킹 인프라** (실시간 광고 경매, Taboola 추천, 쿠키
    동기화 등). 기사 본문·이미지·레이아웃과 무관. 없어도 본문 렌더링엔 영향 0,
    광고 자리만 빈 공간으로 남음. 크롤러 관점에선 오히려 없는 게 나음.

### 세션 A — 캐시 용량 분석 및 전체 예산 추정
- **배경**: 사용자 우려 — "벌써 8MB 넘었다. 1GB 기준 사이트당 기사 몇 개 들어갈까?
  20GB 상한 가정해서."
- **현재 실측** (ALLOW + BLOCK 혼합 세션 후 기준):

  | 지표 | 값 |
  |---|---|
  | 총 캐시 파일 | 552 개 |
  | 본문 총합(raw) | 5.27 MB |
  | 디스크 사용량 (base64 + JSON 오버헤드 포함) | ~8.5 MB |

  호스트별 용량 분포 (본문 기준):

  | 호스트 | 파일 수 | 용량 | 평균 |
  |---|---:|---:|---:|
  | **www.engadget.com** | **38** | **5,318 KB (98.6%)** | **140 KB** |
  | opus.analytics.yahoo.com | 7 | 41 KB | 5.9 KB |
  | pbs.yahoo.com | 23 | 12.7 KB | 0.6 KB |
  | 3p-geo.yahoo.com | 211 | 9.3 KB | 0.0 KB |
  | noa.yahoo.com | 169 | 7.4 KB | 0.0 KB |
  | 기타 트래커 | ~104 | ~3 KB | ~0 KB |

- **핵심 발견**: **트래커 500+ 파일이 차지하는 용량은 전체의 1.4% (약 72KB).**
  대부분 204 No Content 또는 수백 바이트 빈 JSON 응답. 파일 개수는 많지만 용량
  부담은 사실상 없음. 실제 용량 98% 는 engadget.com HTML 본문과 서브리소스가 차지.

- **base64 오버헤드**: base64 인코딩으로 +33%, JSON 구조 오버헤드 추가.
  디스크 사용량은 본문 크기 대비 약 1.6배.

- **기사 1개당 크기 추정** (수집 방식별):

  | 방식 | 기사당 평균 | 근거 |
  |---|---:|---|
  | Firefox 수동 (공통 리소스 공유 가정) | 800KB ~ 1MB | 첫 기사는 2-3MB, 이후 CSS/JS/폰트 HIT 되어 기사당 500KB-1MB |
  | 크롤러 + 본문 이미지 | 300 ~ 600 KB | HTML + 대표 이미지, JS 미실행 |
  | 크롤러 HTML only | 100 ~ 300 KB | 본문 HTML 한 건 |

- **1GB/사이트 → 기사 수 추정** (engadget 같은 무거운 사이트 기준):

  | 수집 방식 | 기사당 | **1GB/사이트 수용** |
  |---|---:|---:|
  | Firefox 수동 | ~1 MB | **~1,000 기사** |
  | 크롤러 + 이미지 | ~500 KB | **~2,000 기사** |
  | 크롤러 HTML only | ~200 KB | **~5,000 기사** |

  가벼운 사이트(itworld.co.kr, aitimes.kr 같은 한글 매체)는 이미지/JS 적어
  **2-3배 더** 들어감.

- **20GB/20사이트 예산 검증** (목표: 사이트당 100-500 기사, 총 ~9,500):

  | 시나리오 | 최악 | 평균 | 최선 |
  |---|---:|---:|---:|
  | 20사이트 총 수용량 | 20,000 기사 | 50,000 기사 | 100,000 기사 |
  | 목표 9,500 대비 여유 | 2배 | 5배 | 10배 |

- **결론**: **20GB 상한이면 충분히 여유.** 크롤러 중심으로 수집 설계하면 5-10GB로도 목표
  달성 가능. 지금 8.5MB 가 "커 보이는" 건 트래커 파일 개수(500+) 로 인한 착시이고,
  실제 용량은 engadget HTML 38 건이 대부분.

- **절감 방법** (나중에 필요할 때):
  1. `EXCLUDED_HOST_SUFFIXES` 에 Yahoo 트래커 추가 — 용량 효과는 미미(<1%), 파일
     개수/로그 정리 효과 큼.
  2. 수집 단계에서 Firefox 수동 캐싱 최소화, 크롤러 중심으로. Firefox 는 로그인/
     쿠키 동의 같은 사람이 개입해야 하는 페이지에만 사용.
  3. 이미지 CDN(`s.yimg.com` 등) 을 `EXCLUDED_HOST_SUFFIXES` 에 넣어 이미지 캐싱
     스킵. 단 크롤러가 이미지 없이 동작 가능한지 먼저 확인 필요.
  4. 주기적 청소: `du -sh cache/ && ls cache/ | wc -l` 로 모니터링.

### 세션 A — README 가이드 형태 전면 재작성
- **배경**: 세션 A 에서 확립된 여러 결정(ALLOW/BLOCK 모드, 시스템 프록시 대신
  클라이언트별 프록시, Firefox 수동 캐싱 가이드, 클라이언트별 사용법)이 README
  에는 반영되지 않은 상태였음. 기존 README 는 "셋업 메뉴얼" 중심이었고, 낡은
  내용(시스템 프록시 중심 지침, 존재하지 않는 `log.log` 파일, `--conf` 옵션 참조
  등)이 섞여 있었음. 사용자 요청 — "README랑 문서 정리 한번만 해줘. 가이드
  형태로도 하고".
- **한 일**: `README.md` 전면 재작성. 섹션 구성:
  1. 왜 필요한가
  2. 동작 모드 — ALLOW(허용) / BLOCK(차단) (전환 명령, 로그 태그 표)
  3. 빠른 시작 (Quickstart) — 컨테이너 기동, curl 테스트, 캐시 확인
  4. 사용 가이드 — 클라이언트별:
     A. Firefox 로 수동 캐싱 (프록시 설정 + CA 등록 단계별)
     B. curl / 셸에서 일회성 사용 (`-x` 또는 `HTTPS_PROXY`)
     C. 크롤러에서 사용 (Python requests/httpx, Playwright, 환경변수 예시)
  5. 수집→디버깅 워크플로우 (6단계 시나리오)
  6. 캐시 대상 사이트 관리 (target-sites.txt + config.yaml 의 allow_hosts)
  7. 오프라인 재생 검증
  8. 구성 (파일별 역할)
  9. 알려진 제약
  10. 용량 가늠 (수집 방식별 기사당 크기, 1GB/사이트 추정)
  11. 로드맵
  12. 트러블슈팅 (Firefox CA 미등록, logs 비어있음, BLOCK 모드 504 잔재 정리
      스크립트 등)
  13. 참고 문서 링크
- **제거된 항목**:
  - `networksetup` 기반 시스템 프록시 설정 지침 (세션 A 의 방침에 반함)
  - 존재하지 않는 `log.log` 항목
  - `--conf /work/config.yaml` 참조 (현재는 `~/.mitmproxy/config.yaml` 경로에
    마운트해서 자동 로드)
  - `sudo networksetup ... off` 종료 순서 (시스템 프록시 안 쓰므로 불필요)
  - "개발용 캐시" 표현 (정체성: "크롤러용 스냅샷 캐시")
- **추가된 항목**:
  - Firefox CA 인증서 등록 단계별 가이드
  - curl / requests / httpx / Playwright 각각의 프록시 지정 예시
  - 수집→디버깅 6단계 워크플로우 다이어그램
  - 용량 가늠 표 (실록 데이터 기반)
  - BLOCK 모드 504 오염 파일 정리 스크립트 (트러블슈팅)
  - 실록 / what-is-mitm-proxy 교차 링크
- **`what-is-mitm-proxy.md`**: 개념 해설 문서로 세션 작업과 독립적. 변경 없음.
- **결과**: `README.md` 137 줄 → 380 줄. 가이드 형태로 재구성 완료. 사용자가 처음
  프로젝트에 왔을 때 "왜 필요한가 → 빠른 시작 → 클라이언트별 가이드 → 워크플로우"
  순으로 자연스럽게 읽을 수 있음.

---
