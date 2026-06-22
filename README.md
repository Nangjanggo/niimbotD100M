# niimbotD100M

Niimbot D110M 라벨 프린터를 라즈베리파이에서 HTTP API로 제어하는 서버입니다.

---

## 핵심 기능

- `POST /print` 요청을 받으면 텍스트 + QR 라벨 이미지를 생성하고 블루투스로 인쇄
- 부팅 시 Cloudflare Tunnel을 열고 퍼블릭 URL을 백엔드 서버에 자동 등록
- `POST /setup`으로 원격에서 기기 설정 업데이트 가능
- systemd 서비스로 부팅 시 자동 시작

---

## 아키텍처

```
백엔드 / 앱
     │  HTTPS (Cloudflare Tunnel)
     ▼
Go HTTP 서버 :8769
     │  96×320 PNG 생성 (텍스트 좌측, QR 우측)
     ▼
Python 서브프로세스 (niimprint/__main__.py)
     │  RFCOMM 블루투스
     ▼
Niimbot D110M
```

---

## API

모든 엔드포인트는 HTTP Basic Auth 필요 (`/health` 제외).

### `POST /print`
```json
{ "text": "두부\n2024-06-22", "qr_text": "https://example.com/item/42" }
```

### `POST /setup`
```json
{ "fridgeId": 13, "deviceId": "uuid", "ec2Url": "https://your-backend.example.com" }
```

### `GET /health`
`200 OK`

---

## Getting Started

> Raspberry Pi OS 64비트(Bookworm 이상) 기준

### 1. 저장소 클론

```bash
git clone https://github.com/Nangjanggo/Nangjanggo.git
cd Nangjanggo
```

### 2. setup.sh 실행

니임봇 프린터를 켜고 블루투스 페어링 모드 상태로 둔 뒤 스크립트를 실행합니다.

```bash
chmod +x setup.sh
./setup.sh
```

스크립트가 아래를 순서대로 처리합니다.

1. 시스템 패키지 설치 (`python3`, `pip`, `bluetooth`, `bluez`)
2. cloudflared 설치
3. Python 의존성 설치 (`Pillow`)
4. Go 1.22.3 다운로드 + 서버 바이너리 빌드
5. 블루투스 스캔 → `D110` 항목의 MAC 주소 확인 후 Ctrl+C → MAC 주소 입력
6. `.env` 파일 생성
7. systemd 서비스 등록 (`niimbot.service`) + 자동 시작

### 3. 동작 확인

```bash
sudo systemctl status niimbot
sudo journalctl -u niimbot -f
```

정상 시작 시 아래 로그가 출력됩니다.

```
[register] URL: https://xxxx.trycloudflare.com
[register] 등록 완료
listening at port 0.0.0.0:8769
```

### 4. 최초 온보딩

Pi와 같은 네트워크에서 `/setup`을 호출하면 `.env`에 기기 정보가 저장됩니다. 이후 재부팅 시 EC2에 자동 등록됩니다.

```bash
curl -u admin:admin \
     -X POST http://<Pi 로컬 IP>:8769/setup \
     -H "Content-Type: application/json" \
     -d '{"fridgeId": 1, "deviceId": "uuid", "ec2Url": "https://your-backend.example.com"}'
```

---

## 환경 변수

`.env`는 `setup.sh`가 자동 생성합니다. 이후 `/setup` 호출로 백엔드가 나머지 항목을 채워 넣습니다.

| 키 | 설명 |
|---|---|
| `USERNAME` | Basic Auth 아이디 (기본값: `admin`) |
| `PASSWORD` | Basic Auth 비밀번호 (기본값: `admin`) |
| `PRINTER_MAC` | 니임봇 블루투스 MAC 주소 |
| `FRIDGE_ID` | 백엔드 냉장고 ID |
| `DEVICE_ID` | 백엔드 기기 UUID |
| `EC2_URL` | 백엔드 서버 URL |

---

## 저장소 구조

```
├── main.go / handler.go / models.go   # HTTP 서버
├── print.go                           # 라벨 이미지 생성 + Python 호출
├── tag/ text/ qr/                     # 이미지 합성 (텍스트, QR)
├── niimprint/niimprint/__main__.py    # 블루투스 인쇄 클라이언트
├── scripts/register.sh                # Cloudflare Tunnel + EC2 등록
├── setup.sh                           # 초기 세팅 스크립트
└── fonts/                             # NanumGothicBold 등
```

---

## 라이선스

[LICENSE](LICENSE)
