#!/bin/bash
set -e
cd "$(dirname "$0")"

echo "=============================="
echo "  Niimbot D100M 초기 세팅"
echo "=============================="
echo ""

# 1. 패키지 설치
echo "[1/6] 패키지 설치..."
sudo apt update -qq && sudo apt install -y git python3 python3-pip bluetooth bluez
echo "  완료"

# 2. cloudflared 설치
echo "[2/6] cloudflared 설치..."
if ! command -v cloudflared &>/dev/null; then
    sudo curl -fsSL https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 \
         -o /usr/local/bin/cloudflared
    sudo chmod +x /usr/local/bin/cloudflared
    echo "  완료"
else
    echo "  이미 설치됨, 건너뜀"
fi

# 3. Python 의존성 설치
echo "[3/6] Python 의존성 설치..."
pip3 install -q --break-system-packages -r niimprint/requirements.txt
echo "  완료"

# 4. Go 설치 및 바이너리 빌드
echo "[4/6] Go 설치 및 바이너리 빌드..."
if ! command -v go &>/dev/null && [ ! -f /usr/local/go/bin/go ]; then
    echo "  Go 다운로드 중..."
    GO_VERSION="1.22.3"
    curl -fsSL "https://go.dev/dl/go${GO_VERSION}.linux-arm64.tar.gz" -o /tmp/go.tar.gz
    sudo rm -rf /usr/local/go
    sudo tar -C /usr/local -xzf /tmp/go.tar.gz
    rm /tmp/go.tar.gz
    echo "  완료"
fi
export PATH=$PATH:/usr/local/go/bin
grep -qxF 'export PATH=$PATH:/usr/local/go/bin' ~/.bashrc || echo 'export PATH=$PATH:/usr/local/go/bin' >> ~/.bashrc
echo "  빌드 중..."
/usr/local/go/bin/go build -o niimbot_server .
echo "  완료"

# 5. 니임봇 블루투스 MAC 확인
echo "[5/6] 니임봇 블루투스 설정..."
echo ""
echo "  니임봇 프린터 전원을 켜 주세요. (파란 불이 켜지면 준비 완료)"
read -p "  준비되면 Enter..."
echo ""
echo "  스캔 시작 — 'D110M'이 보이면 MAC 주소를 확인하고 Ctrl+C로 종료하세요."
echo "  -------------------------------------------------------"
bluetoothctl scan on || true
echo "  -------------------------------------------------------"
echo ""
read -p "  확인한 프린터의 MAC 주소 입력: " PRINTER_MAC
echo "  완료 (BLE 방식이므로 별도 페어링 불필요)"

# 6. .env 작성
echo "[5/6] .env 파일 생성..."
if [ -f .env ]; then
    read -p "  기존 .env가 있습니다. 덮어쓰시겠습니까? (y/N): " OVERWRITE
    [[ "$OVERWRITE" == "y" || "$OVERWRITE" == "Y" ]] && WRITE_ENV=1
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
    echo "  완료 (FRIDGE_ID, DEVICE_ID, EC2_URL은 앱의 /setup 호출로 자동 채워집니다)"
else
    echo "  기존 .env 유지"
fi

# 7. systemd 서비스 등록 (번호는 내부용으로 유지)
echo "[6/6] systemd 서비스 등록..."
WORK_DIR="$(pwd)"
USER_NAME="$(whoami)"

sudo tee /etc/systemd/system/niimbot.service > /dev/null <<EOF
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
echo "  완료"

echo ""
echo "=============================="
echo "  세팅 완료!"
echo "=============================="
echo ""
echo "서버 상태:  sudo systemctl status niimbot"
echo "로그 확인:  sudo journalctl -u niimbot -f"
echo ""
PI_IP=$(hostname -I | awk '{print $1}')
echo "다음 단계:  앱에서 아래 주소로 /setup 호출"
echo "           http://${PI_IP}:8769/setup"
echo ""
