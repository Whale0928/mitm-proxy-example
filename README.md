# mitm-proxy-example

mitmproxy 기반 **개발용 HTTP(S) 캐시 프록시**.

> 이 프록시가 왜 필요한지, 어떻게 동작하는지부터 알고 싶다면 → [what-is-mitm-proxy.md](./what-is-mitm-proxy.md)

이 문서는 **셋업과 실행 방법**만 다룬다.

## 구성

| 파일 | 역할 |
|---|---|
| `cache_addon.py` | mitmproxy addon. URL 단위로 응답을 디스크에 저장/재생 |
| `config.yaml` | mitmproxy 옵션 (캐시 대상 사이트, 동작 옵션 모음) |
| `docker-compose.yml` | 공식 mitmproxy 이미지로 컨테이너 기동 |
| `ca/` | mitmproxy CA 인증서 (개인키 포함, **프라이빗 저장소 전제**) |
| `cache/` | 캐시된 응답 (한 요청 = 한 JSON 파일) |
| `log.log` | 실행 로그 (자동 생성) |

## 사전 준비

### 1. mitmproxy CA 인증서 신뢰 등록 (한 번만)

HTTPS 사이트를 가로채려면 mitmproxy 의 가짜 CA 인증서를 시스템이 신뢰해야 한다.
이 저장소의 `ca/` 디렉토리에 인증서가 들어있다.

```sh
sudo security add-trusted-cert -d -r trustRoot \
  -k /Library/Keychains/System.keychain \
  ./ca/mitmproxy-ca-cert.pem
```

확인: 키체인 접근 → 시스템 → "mitmproxy" 검색.

### 2. 시스템 프록시 설정

활성 네트워크 인터페이스 이름 확인:
```sh
networksetup -listnetworkserviceorder
route get default | grep interface
```

활성 인터페이스에 프록시 설정 (예: Ethernet):
```sh
sudo networksetup -setwebproxy "Ethernet" 127.0.0.1 8080
sudo networksetup -setsecurewebproxy "Ethernet" 127.0.0.1 8080
```

확인:
```sh
scutil --proxy
# HTTPProxy / HTTPSProxy 가 127.0.0.1:8080 으로 잡혀있어야 함
```

> ⚠️ 이 시점부터는 mitmproxy 컨테이너가 떠 있어야 인터넷이 동작한다.
> 다음 단계로 바로 가야 한다.

## 기동

```sh
docker compose up -d
```

로그 보기 (다른 터미널):
```sh
docker compose logs -f mitmproxy
```

`config.yaml` 의 `allow_hosts` 에 등록된 사이트로 트래픽이 가면
`[MISS]` `[SAVE]` 가 찍히고, 같은 URL 을 다시 호출하면 `[HIT]` 가 찍힌다.

## 종료

**반드시 이 순서**로 끄는 게 안전하다.

```sh
# 1. 시스템 프록시 OFF (인터넷 복구)
sudo networksetup -setwebproxystate "Ethernet" off
sudo networksetup -setsecurewebproxystate "Ethernet" off

# 2. 컨테이너 종료
docker compose down
```

순서가 중요한 이유: 시스템 프록시가 켜진 채로 컨테이너만 먼저 내리면
8080 으로 보내는 트래픽을 받는 사람이 없어서 모든 인터넷이 막힌다.

## 사용 흐름

1. 위 사전 준비 + 기동 완료
2. 브라우저로 `config.yaml` 의 `allow_hosts` 에 등록된 사이트들을 평소처럼 탐색
3. 로그에서 `[MISS]` → `[SAVE]` 확인
4. 같은 URL 다시 방문하면 `[HIT]`
5. 개발 중엔 같은 URL 을 무한히 반복 호출해도 캐시에서 응답

## 캐시 대상 사이트 추가/제거

`config.yaml` 의 `allow_hosts:` 리스트 수정 후 컨테이너 재시작:

```sh
docker compose restart mitmproxy
```

## 검증 (오프라인 재생)

캐시가 진짜로 동작하는지 확실히 확인하는 방법:

1. 온라인으로 한 번 사이트 방문해서 캐시를 채운다
2. Wi-Fi/이더넷을 끈다
3. 브라우저에서 같은 페이지 강력 새로고침 (Cmd+Shift+R)
4. 페이지가 그대로 뜨고 로그가 모두 `[HIT]` 이면 성공

## 트러블슈팅

### 인터넷이 안 된다
시스템 프록시가 켜져 있는데 mitmproxy 컨테이너가 죽었거나 안 떠있다.
- `docker compose ps` 로 컨테이너 살아있는지 확인
- 정 안 되면 시스템 프록시 OFF

### 페이지가 인증서 경고로 안 열린다
mitmproxy CA 신뢰 등록이 안 됐다. 사전 준비 1단계 다시 수행.

### 오프라인에서 캐시 HIT 인데도 페이지가 안 뜬다
mitmproxy 가 응답 전에 업스트림 서버 연결을 시도하다 실패하고 있다.
`config.yaml` 에 `connection_strategy: lazy` 가 있는지 확인.

### `docker compose logs` 가 비어있다
TTY 부족. `docker-compose.yml` 에 `tty: true` 가 있는지 확인.

### 컨테이너 안에서 "killed by block_global" 로그
도커 NAT 를 통해 들어오는 호스트 트래픽을 mitmproxy 가 외부 접근으로
간주해 차단하고 있다. `config.yaml` 에 `block_global: false` 가 있는지 확인.

### 등록 안 한 사이트의 트래픽까지 캐시된다
`config.yaml` 의 `allow_hosts` 가 설정 안 됐거나 mitmproxy 가 옵션을
못 읽고 있다. `--conf /work/config.yaml` 이 docker-compose.yml 의
`command` 에 들어있는지 확인.
