# 로컬 실행 명령

저장소 루트에서 실행한다. 프록시 주소는 `http://127.0.0.1:8080`이다.

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

## 로컬 프록시 확인

```sh
curl --proxy http://127.0.0.1:8080 \
  --cacert ca/mitmproxy-ca-cert.pem \
  https://www.engadget.com/ -o /dev/null -s -w "%{http_code} %{time_total}s\n"
```

## 로그 태그

- `[HIT]` 캐시 재생
- `[MISS]` 실서버 통과 중
- `[SAVE]` 디스크 저장 완료
- `[BLOCK]` 504 차단
- `[SKIP]` 화이트리스트 밖
