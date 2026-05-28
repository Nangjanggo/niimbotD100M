#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=== Niimbot D110 초기 세팅 ==="

# 1. 패키지 설치
echo "[1/7] 패키지 설치..."
sudo apt update -qq && sudo apt install -y git python3 python3-pip bluetooth bluez

# 2. cloudflared 설치
echo "[2/7] cloudflared 설치..."
if ! command -v cloudflared &>/dev/null; then
    sudo curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 \
         -o /usr/local/bin/cloudflared
    sudo chmod +x /usr/local/bin/cloudflared
else
    echo "  cloudflared 이미 설치됨, 건너뜀"
fi

# 3. Python 의존성 설치
echo "[3/7] Python 의존성 설치..."
pip3 install -q -r niimprint/requirements.txt

# 4. Go 설치 및 바이너리 빌드
echo "[4/7] Go 설치 및 바이너리 빌드..."
if ! command -v go &>/dev/null; then
    echo "  Go 설치 중..."
    GO_VERSION="1.22.3"
    curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-arm64.tar.gz" -o /tmp/go.tar.gz
    sudo rm -rf /usr/local/go
    sudo tar -C /usr/local -xzf /tmp/go.tar.gz
    rm /tmp/go.tar.gz
    export PATH=$PATH:/usr/local/go/bin
    echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
fi
go build -o niimbot_server .

# 5. 니임봇 블루투스 MAC 확인 및 페어링
echo "[5/7] 니임봇 블루투스 설정..."
echo "  니임봇 프린터 전원을 켜고 페어링 모드로 진입시켜 주세요."
echo "  스캔을 시작합니다. 'D110'이 뜨면 MAC 주소를 복사 후 Ctrl+C로 종료하세요."
read -p "  준비되면 Enter..."
bluetoothctl scan on &
SCAN_PID=$!
read -p "  D110의 MAC 주소 입력: " PRINTER_MAC
kill $SCAN_PID 2>/dev/null || true

echo "  페어링 중..."
bluetoothctl pair "$PRINTER_MAC"
bluetoothctl trust "$PRINTER_MAC"

# 6. .env 작성
echo "[6/7] .env 파일 생성..."
if [ -f .env ]; then
    echo "  기존 .env 파일이 있습니다."
    read -p "  덮어쓰시겠습니까? (y/N): " OVERWRITE
    [[ "$OVERWRITE" != "y" && "$OVERWRITE" != "Y" ]] && echo "  .env 유지, 건너뜀" || WRITE_ENV=1
else
    WRITE_ENV=1
fi

if [ "${WRITE_ENV}" = "1" ]; then
    cat > .env <<EOF
USERNAME=admin
PASSWORD=admin
PRINTER_MAC=${PRINTER_MAC}
FRIDGE_ID=
DEVICE_ID=
EC2_URL=
EOF
    echo "  .env 생성 완료 (FRIDGE_ID, DEVICE_ID, EC2_URL은 앱에서 /setup 호출로 채워집니다)"
fi

# 7. systemd 서비스 등록
echo "[7/7] systemd 서비스 등록..."
SERVICE_FILE=/etc/systemd/system/niimbot.service
WORK_DIR="$(pwd)"
USER_NAME="$(whoami)"

sudo tee "$SERVICE_FILE" > /dev/null <<EOF
[Unit]
Description=Niimbot Server
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=${WORK_DIR}
ExecStartPre=${WORK_DIR}/scripts/register.sh
ExecStart=${WORK_DIR}/niimbot_server
Restart=always
User=${USER_NAME}

[Install]
WantedBy=multi-user.target
EOF

sudo systemctl daemon-reload
sudo systemctl enable niimbot
sudo systemctl start niimbot

echo ""
echo "=== 세팅 완료 ==="
echo "서버 상태: sudo systemctl status niimbot"
echo "로그 확인: sudo journalctl -u niimbot -f"
echo ""
echo "다음 단계: 앱에서 Pi의 IP($(hostname -I | awk '{print $1}'):8769)로 /setup 호출"
