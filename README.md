# mitm-proxy-example

mitmproxy 기반 **개발용 HTTP(S) 캐시 프록시** 예제.

## 목적

크롤러/스크래퍼를 개발할 때 매번 실제 사이트에 요청을 보내면
- 차단당할 수 있고
- 사이트가 변하면 재현이 안 되고
- 개발 속도가 느려진다.

이 프록시는 한 번 본 응답을 디스크에 저장해두고, 다음부터는 캐시에서 그대로
돌려준다. 사람이 브라우저로 사이트를 돌아다니면서 페이지를 채워두면, 이후
개발/테스트에선 인터넷이 없어도 동일한 응답을 재생할 수 있다.

## 구성

| 파일 | 역할 |
|---|---|
| `cache_addon.py` | mitmproxy addon. URL 단위로 요청을 캐시 디렉토리에 JSON 으로 저장 |
| `run.sh` | mitmdump 실행 래퍼. 필수 옵션 + 노이즈 차단 + 로그 기록 |
| `cache/` | 캐시된 응답 (한 요청 = 한 JSON 파일, 키는 URL 의 sha256) |
| `log.log` | mitmdump 실행 로그 (자동 생성) |

## 사전 준비

### 1. 설치

```sh
brew install mitmproxy
```

### 2. 시스템 프록시 설정

활성 네트워크 인터페이스에 프록시를 박는다 (예: Ethernet).
인터페이스 이름은 `networksetup -listnetworkserviceorder` 로 확인.

```sh
sudo networksetup -setwebproxy "Ethernet" 127.0.0.1 8080
sudo networksetup -setsecurewebproxy "Ethernet" 127.0.0.1 8080
```

확인:

```sh
scutil --proxy
# HTTPProxy / HTTPSProxy 가 127.0.0.1:8080 으로 잡혀있어야 함
```

### 3. mitmproxy CA 인증서 신뢰 등록

HTTPS 사이트를 가로채려면 mitmproxy 의 가짜 인증서를 시스템이 신뢰해야 한다.
한 번 mitmdump 를 실행한 적이 있으면 `~/.mitmproxy/` 에 인증서가 생성돼 있다.

```sh
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain \
  ~/.mitmproxy/mitmproxy-ca-cert.pem
```

또는 브라우저로 `http://mitm.it` 접속 → Apple 로 표시된 인증서 다운로드 →
키체인 접근에서 "항상 신뢰" 설정.

## 실행

```sh
./run.sh
```

이 스크립트는 다음을 수행한다:

1. **`-s cache_addon.py`** — 캐시 addon 로드
2. **`--set connection_strategy=lazy`** — 업스트림 사전 연결을 막아 캐시 HIT 시
   네트워크에 전혀 나가지 않게 한다. **이 옵션 없으면 오프라인 재생이 안 됨.**
3. **`--ignore-hosts '...'`** — certificate pinning 으로 가로채기를 거부하는
   호스트들을 우회한다. 두 가지 효과:
   - **Claude Code 등 자체 도구**(`anthropic.com`) 트래픽이 캐시에 잡혀
     의도치 않게 재생되는 것을 방지
   - **OS 백그라운드 트래픽**(`icloud.com`, `apple.com`, `gvt1.com` 등)이
     handshake 실패 로그로 화면을 도배하는 것을 차단
4. **`2>&1 | tee log.log`** — 화면 출력과 동시에 `log.log` 파일에 전체 로그 저장

## 사용 흐름

1. `./run.sh` 로 mitmdump 기동
2. 시스템 프록시가 켜진 상태에서 브라우저로 대상 사이트 탐색
   (메인 → 기사 → 카테고리 등 필요한 페이지를 직접 클릭)
3. mitmdump 화면(또는 `log.log`)에서 `[MISS]` `[SAVE]` 로그 확인
4. 같은 URL 을 다시 호출하면 `[HIT]` 로그가 뜨고 네트워크에 안 나감
5. 개발 중엔 같은 사이트의 같은 URL 을 무한히 반복 호출해도 OK

## 종료 후 원복

작업이 끝나면 시스템 프록시를 반드시 꺼야 일반 인터넷이 복구된다:

```sh
sudo networksetup -setwebproxystate "Ethernet" off
sudo networksetup -setsecurewebproxystate "Ethernet" off
```

## 검증 (오프라인 재생)

캐시가 진짜로 동작하는지 확실히 확인하는 방법:

1. 한번 온라인으로 대상 페이지를 브라우저로 방문해 캐시를 채운다
2. **Wi-Fi/이더넷을 끈다**
3. 브라우저에서 같은 페이지를 강력 새로고침 (Cmd+Shift+R)
4. 페이지가 그대로 뜨고, `log.log` 에 `[MISS]` 없이 `[HIT]` 만 찍히면 성공

## 알려진 한계

- **304 Not Modified**: 서버가 304 + 빈 본문을 돌려주면 캐시에 본문이
  없어서 오프라인 재생 시 이미지가 깨질 수 있다. 브라우저 캐시가 채워준
  덕분에 화면엔 보이지만, 캐시 비우면 깨진다. 해결 필요 시 addon 에서
  요청의 `If-Modified-Since` / `If-None-Match` 헤더를 제거하면 된다.
- **Timestamp 쿼리스트링**: `?t=1775724192679` 같이 매번 변하는 쿼리는
  매번 새 캐시 키로 잡혀서 항상 MISS. 필요 시 addon 의 캐시 키 함수에서
  특정 파라미터를 무시하도록 수정.
- **Cert pinning 앱**: `--ignore-hosts` 에 추가하지 않은 cert pinning
  앱들은 handshake 실패 로그를 남기지만 동작엔 영향 없다.
