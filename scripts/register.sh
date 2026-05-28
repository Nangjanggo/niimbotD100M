#!/bin/bash
cd "$(dirname "$0")/.."
set -a; source .env; set +a

if [ -z "$FRIDGE_ID" ] || [ -z "$DEVICE_ID" ] || [ -z "$EC2_URL" ]; then
    echo "[register] 미설정 상태 — 기기 연동을 먼저 해주세요"
    exit 0
fi

# 기존 cloudflared 종료
pkill -f 'cloudflared tunnel' 2>/dev/null || true
sleep 1

# cloudflared 시작 및 URL 캡처
cloudflared tunnel --url http://localhost:8769 > /tmp/cf.log 2>&1 &

CLOUDFLARE_URL=""
for i in $(seq 1 30); do
    CLOUDFLARE_URL=$(grep -o 'https://[a-z0-9-]*\.trycloudflare\.com' /tmp/cf.log 2>/dev/null | head -1)
    [ -n "$CLOUDFLARE_URL" ] && break
    sleep 1
done

if [ -z "$CLOUDFLARE_URL" ]; then
    echo "[register] Cloudflare URL 획득 실패 — 로컬 IP로 대체"
    MY_IP=$(ip route get 1.1.1.1 2>/dev/null | awk '{for(i=1;i<=NF;i++) if($i=="src") print $(i+1); exit}')
    CLOUDFLARE_URL="http://${MY_IP}:8769"
fi

echo "[register] URL: $CLOUDFLARE_URL"

for i in 1 2 3 4 5; do
    CODE=$(curl -s -o /dev/null -w "%{http_code}" -X PATCH \
        "${EC2_URL}/hardware/fridges/${FRIDGE_ID}/devices/${DEVICE_ID}" \
        -H 'Content-Type: application/json' \
        -d "{\"printerUrl\": \"${CLOUDFLARE_URL}\"}" \
        --connect-timeout 5)
    [ "$CODE" = "200" ] && echo "[register] 등록 완료" && exit 0
    echo "[register] 시도 $i 실패 (HTTP $CODE)"
    sleep 3
done

echo "[register] EC2 등록 실패"
exit 0
