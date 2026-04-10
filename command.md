# command.md

- 서버: `192.0.2.10` (홈 네트워크 내부)
- 공개: `http://proxy.example.invalid:8889`
- SSH 키: `~/.ssh/example_key`
- 서버 레포: `~/mitm-proxy-example`

---

## SSH 접속

```sh
ssh -i ~/.ssh/example_key demo@192.0.2.10
cd ~/mitm-proxy-example
```

---

## 허용 모드 재기동

```sh
docker compose down && docker compose up -d
```

## 차단 모드 재기동

```sh
docker compose down && MITM_CACHE_MODE=block docker compose up -d
```

## 캐시 정리

```sh
find cache/ -type f -name "*.json" -delete
```

## 캐시 정리 + 허용 모드 재기동

```sh
docker compose down && find cache/ -type f -name "*.json" -delete && docker compose up -d
```

## 캐시 정리 + 차단 모드 재기동

```sh
docker compose down && find cache/ -type f -name "*.json" -delete && MITM_CACHE_MODE=block docker compose up -d
```

---

## 상태 확인

```sh
docker compose ps
```

## 현재 모드

```sh
docker compose logs mitmproxy 2>&1 | grep "\[INIT\] mode=" | tail -1
```

## 캐시 크기

```sh
echo "$(ls cache/ | wc -l) files, $(du -sh cache/ | cut -f1)"
```

---

## 로그

```sh
# 최근 50줄
docker compose logs --tail=50 mitmproxy

# 실시간
docker compose logs -f mitmproxy

# 태그 카운트
docker compose logs mitmproxy 2>&1 | grep -oE '\[(HIT|MISS|SAVE|SKIP|BLOCK)\]' | sort | uniq -c
```

---

## 컨테이너 제어

```sh
# 재시작
docker compose restart mitmproxy

# 정지
docker compose down

# 기동
docker compose up -d
```

## 캐시 권한 복구

```sh
sudo chown -R 1000:1000 cache
```

---

## 외부 검증 (홈 네트워크 밖에서도 가능)

```sh
# 엔드포인트 생존 확인
curl -sS -o /dev/null -w "%{http_code} %{time_connect}s\n" http://proxy.example.invalid:8889/

# 캐시 히트 테스트
curl -x http://proxy.example.invalid:8889 -k https://www.engadget.com/ -o /dev/null -s -w "%{http_code} %{time_total}s\n"
```

---

## 원격 실행 (홈 네트워크 안에서)

SSH로 감싸서 로컬에서 한 줄로:

```sh
ssh -i ~/.ssh/example_key demo@192.0.2.10 'cd ~/mitm-proxy-example && <위 명령>'
```

예:

```sh
ssh -i ~/.ssh/example_key demo@192.0.2.10 'cd ~/mitm-proxy-example && docker compose down && MITM_CACHE_MODE=block docker compose up -d'
```

---

## 로그 태그

- `[HIT]` 캐시 재생
- `[MISS]` 실서버 통과 중
- `[SAVE]` 디스크 저장 완료
- `[BLOCK]` 504 차단
- `[SKIP]` 화이트리스트 밖
