#!/usr/bin/env bash
# mitmdump 실행 스크립트
#
# 옵션 설명:
#   -s cache_addon.py
#       캐시 addon 로드. MISS 응답은 디스크에 저장하고, HIT 면 캐시에서 즉시 응답.
#
#   --set connection_strategy=lazy
#       업스트림 서버로의 사전 연결을 막는다. 이게 없으면 mitmproxy 가
#       addon 호출 전에 실제 서버에 먼저 TCP 연결을 시도하기 때문에,
#       오프라인 재생 시 캐시 HIT 인데도 요청이 죽는다.
#
#   --ignore-hosts '...'
#       이 정규식에 매칭되는 호스트는 TLS 가로채기 자체를 하지 않고 그대로
#       흘려보낸다. 두 가지 목적:
#       (1) Claude Code (anthropic.com) 같은 자체 도구가 캐시에 잡히는 것을 방지.
#       (2) certificate pinning 을 쓰는 OS/앱들이 mitmproxy 인증서를 거부하면서
#           TLS handshake 실패 로그를 폭주시키는 것을 차단 (gateway.icloud.com 등).
#
#   --set termlog_verbosity=warn
#       mitmproxy 자체 로그 레벨을 warn 으로 올려서 다음과 같은 잡음을 차단:
#         - client/server connect/disconnect
#         - Client TLS handshake failed (cert pinning 앱들)
#       우리 addon 의 print() 출력 ([HIT]/[MISS]/[SAVE])은 stdout 직접 출력이라
#       이 옵션의 영향을 받지 않고 그대로 보인다.
#
#   --set flow_detail=0
#       요청별로 찍히는 한 줄짜리 flow 요약(`GET https://... HTTP/2.0 << 200 OK`)
#       을 생략. addon 로그만 깔끔하게 남기고 싶을 때 유용.
#
#   2>&1 | tee log.log
#       표준출력 + 표준에러를 모두 log.log 에 기록하면서 동시에 화면에도 출력.

cd "$(dirname "$0")"

mitmdump \
  -s cache_addon.py \
  --set connection_strategy=lazy \
  --set termlog_verbosity=warn \
  --set flow_detail=0 \
  --ignore-hosts '(^|\.)(anthropic\.com|icloud\.com|apple\.com|discord\.com|github\.com|googleapis\.com|gvt1\.com|gvt2\.com)$' \
  2>&1 | tee log.log
