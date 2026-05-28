# NIIMBOT D110 Label Printer API

<img align="right" src="https://github.com/datumbrain/niimbot-d110-api/raw/master/docs/niimbot.png" width="120">

An API server to create a tag image for a text and print it through the NIIMBOT D110 label printer.

## Requirements

- Python `>=3.10`
- Golang
- Linux (macOS doesn't support Bluetooth sockets, not tested on Windows)
- `cloudflared` (for tunnel registration on boot)

## Getting started

- In the `niimprint` directory, run

    ```shell
    pip3 install -r requirements.txt
    ```

- Run golang server

    ```shell
    go run .
    ```

- POST request on `http://localhost:8769/print` with payload in the following JSON format

    ```json
    {
        "text" : "MYLABEL",
        "qr_text" : "https://www.example.com/MYLABEL"
    }
    ```

## cURL

```shell
curl -d '{"text": "MYLABEL", "qr_text": "https://www.example.com/MYLABEL"}' \
     -H "Content-Type: application/json" \
     -X POST \
     http://localhost:8769/print
```

## 새 라즈베리파이 세팅 방법

### 1. 기본 패키지 설치

```bash
sudo apt update && sudo apt install -y git python3 python3-pip bluetooth bluez
```

### 2. cloudflared 설치

```bash
curl -L https://github.com/cloudflare/cloudflared/releases/latest/download/cloudflared-linux-arm64 \
     -o /usr/local/bin/cloudflared
chmod +x /usr/local/bin/cloudflared
```

### 3. 코드 클론

```bash
git clone https://github.com/datumbrain/niimbot-d110-api.git
cd niimbot-d110-api
```

### 4. Python 의존성 설치

```bash
pip3 install -r niimprint/requirements.txt
```

### 5. 니임봇 블루투스 MAC 확인

니임봇 프린터의 전원을 켠 뒤 아래 명령어로 MAC 주소를 확인합니다.

```bash
bluetoothctl
```

```
[bluetooth]# scan on
# 잠시 기다리면 주변 기기 목록이 출력됨
# [NEW] Device XX:XX:XX:XX:XX:XX D110  ← 이름이 "D110"인 항목의 MAC 주소를 복사
[bluetooth]# scan off
[bluetooth]# exit
```

확인한 MAC 주소를 다음 단계의 `PRINTER_MAC`에 입력합니다.

### 6. 니임봇 블루투스 페어링

```bash
bluetoothctl
```

```
[bluetooth]# pair XX:XX:XX:XX:XX:XX
[bluetooth]# trust XX:XX:XX:XX:XX:XX
[bluetooth]# exit
```

### 7. .env 작성

프로젝트 루트에 `.env` 파일을 생성합니다. 서버가 이 파일 없이는 시작되지 않으므로 반드시 먼저 만들어야 합니다.

`FRIDGE_ID`, `DEVICE_ID`, `EC2_URL`은 나중에 앱의 `/setup` 호출로 채워지므로 일단 비워둬도 됩니다.

```env
USERNAME=admin
PASSWORD=admin
PRINTER_MAC=XX:XX:XX:XX:XX:XX
FRIDGE_ID=
DEVICE_ID=
EC2_URL=
```

### 8. 바이너리 빌드

```bash
go build -o niimbot_server .
```

> 동일한 ARM64 환경이라면 기존 라즈베리파이의 `niimbot_server` 바이너리를 복사해도 됩니다.

### 9. 폰트 확인

`fonts/NanumGothicBold.ttf` 파일이 있어야 합니다. 없으면 기존 라즈베리파이에서 복사하세요.

### 10. systemd 서비스 등록

```bash
sudo cp scripts/niimbot.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable niimbot
sudo systemctl start niimbot
```

서비스 파일 (`/etc/systemd/system/niimbot.service`):

```ini
[Unit]
Description=Niimbot Server
After=network-online.target
Wants=network-online.target

[Service]
WorkingDirectory=/home/yangsimfridge/niimbot-d110-api
ExecStartPre=/home/yangsimfridge/niimbot-d110-api/scripts/register.sh
ExecStart=/home/yangsimfridge/niimbot-d110-api/niimbot_server
Restart=always
User=yangsimfridge

[Install]
WantedBy=multi-user.target
```

### 부팅 시 동작 흐름

```
부팅
└─ niimbot.service 시작
   ├─ register.sh 실행
   │   ├─ cloudflared 터널 열기
   │   └─ EC2에 printerUrl PATCH 등록
   └─ niimbot_server 실행 (:8769 포트 리슨)
```

### 11. 앱에서 /setup 호출

서버가 실행된 뒤, 앱에서 Pi와 같은 와이파이 상태로 아래 요청을 보냅니다.

```bash
curl -u admin:admin \
     -X POST http://<Pi의 로컬 IP>:8769/setup \
     -H "Content-Type: application/json" \
     -d '{"fridgeId": 5, "deviceId": "deec5a91-...", "ec2Url": "http://<EC2 Elastic IP>:8080"}'
```

성공하면 `.env`가 자동으로 업데이트되고, 이후 재부팅 시 `register.sh`가 EC2에 자동 등록합니다.

### 체크리스트

- [ ] 니임봇 전원 켜고 블루투스 MAC 확인 (`bluetoothctl scan on`)
- [ ] 니임봇 블루투스 페어링 (`bluetoothctl pair` / `trust`)
- [ ] `.env`에 `USERNAME`, `PASSWORD`, `PRINTER_MAC` 작성
- [ ] `fonts/NanumGothicBold.ttf` 존재 여부
- [ ] `niimbot_server` 바이너리 빌드
- [ ] systemd 서비스 등록 및 시작
- [ ] 앱에서 `/setup` 호출하여 `FRIDGE_ID`, `DEVICE_ID`, `EC2_URL` 등록

## Authors

- [Faizan Khalid](https://github.com/IamFaizanKhalid)
- [Usman Tahir](https://github.com/UsmanT2000)
