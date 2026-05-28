# NIIMBOT D110_M 블루투스 프린터 역설계 완전 분석

## 목차
1. 역설계란 무엇인가
2. btsnoop_hci.log란 무엇인가
3. 블루투스 통신 기초
4. 패킷 구조 완전 분석
5. 체크섬 계산법
6. 커맨드 목록 및 의미
7. 인쇄 순서 (전체 흐름)
8. 이미지 데이터 변환 방법 (0x85)
9. 응답 패킷 분석
10. 코드와 프로토콜 연결
11. btsnoop에서 실제로 어떻게 읽었나

---

## 1. 역설계란 무엇인가

역설계(Reverse Engineering)란 완성된 제품을 분해해서 "어떻게 만들어졌는지"를 파악하는 것이다.

이 프로젝트에서는 NIIMBOT 공식 앱이 프린터에 어떤 데이터를 보내는지 **소스코드 없이** 파악해야 했다.
방법은 간단하다: 앱이 프린터에 보내는 블루투스 신호를 통째로 녹화해서 분석하는 것.

**비유:** 두 사람이 암호로 대화하는 걸 옆에서 녹음한 다음, 녹음본을 반복해서 들으면서 패턴을 찾아 암호를 해독하는 것과 같다.

---

## 2. btsnoop_hci.log란 무엇인가

안드로이드 폰은 블루투스 통신 내용을 로그 파일로 저장할 수 있다.
이 파일이 `btsnoop_hci.log`다.

### 어떻게 얻었나

1. 안드로이드 개발자 옵션 → "블루투스 HCI 스누프 로그 사용" 활성화
2. NIIMBOT 앱으로 실제로 인쇄
3. 안드로이드 버그리포트 생성 (`adb bugreport`)
4. 버그리포트 압축 해제 → `FS/data/log/` 안에 `btsnoop_hci.log` 존재

이 프로젝트의 `bugreport-dm2qksx-...` 폴더가 바로 그 버그리포트다.

### 파일 내용

btsnoop 파일은 바이너리 파일이다. Wireshark로 열면 이렇게 보인다:

```
No.  Time     Source       Destination  Protocol  Info
1    0.000    host         controller   HCI        ...
2    0.001    controller   host         HCI        ...
...
50   1.234    app          printer      RFCOMM     Data: 55 55 23 01 01 23 AA AA
51   1.235    printer      app          RFCOMM     Data: 55 55 33 01 01 33 AA AA
```

여기서 `55 55`로 시작하는 패킷들이 실제 프린터 통신 데이터다.

---

## 3. 블루투스 통신 기초

### RFCOMM이란

블루투스에는 여러 통신 방식이 있는데, 이 프린터는 **RFCOMM**을 사용한다.
RFCOMM은 쉽게 말해 "블루투스로 연결된 시리얼 포트"다.
USB 케이블 대신 블루투스로 데이터를 주고받는 것과 같다.

### 연결 방법 (코드)

```python
import socket

sock = socket.socket(socket.AF_BLUETOOTH, socket.SOCK_STREAM, socket.BTPROTO_RFCOMM)
sock.connect(("06:A7:13:68:00:11", 1))  # MAC 주소, 포트 1
```

- `AF_BLUETOOTH`: 블루투스 소켓
- `BTPROTO_RFCOMM`: RFCOMM 프로토콜 사용
- 포트 `1`: RFCOMM 채널 번호 (프린터가 1번 채널을 사용)

연결되면 일반 TCP 소켓처럼 `send()`와 `recv()`로 데이터를 주고받는다.

---

## 4. 패킷 구조 완전 분석

### 기본 구조

모든 패킷은 이 형식을 따른다:

```
[55][55][TYPE][LEN][DATA...][CHECKSUM][AA][AA]
  0   1    2    3   4~N      N+1      N+2  N+3
```

| 바이트 위치 | 값 | 설명 |
|------------|-----|------|
| 0 | `0x55` | 시작 마커 1 (항상 고정) |
| 1 | `0x55` | 시작 마커 2 (항상 고정) |
| 2 | TYPE | 커맨드 종류 (어떤 명령인지) |
| 3 | LEN | DATA의 바이트 수 |
| 4 ~ 4+LEN-1 | DATA | 실제 데이터 |
| 4+LEN | CHECKSUM | 오류 검증값 |
| 4+LEN+1 | `0xAA` | 끝 마커 1 (항상 고정) |
| 4+LEN+2 | `0xAA` | 끝 마커 2 (항상 고정) |

### 왜 55 55로 시작하고 AA AA로 끝나나?

블루투스는 데이터를 연속으로 보내기 때문에 "어디서 패킷이 시작하고 끝나는지" 구분이 필요하다.
`55 55`는 "지금부터 패킷 시작이야", `AA AA`는 "패킷 끝이야"라는 신호다.

**비유:** 편지 봉투에 "편지 시작"이라고 쓰고 마지막에 "편지 끝"이라고 쓰는 것과 같다.

### 실제 패킷 예시 1: SET_LABEL_TYPE

라벨 종류를 1번으로 설정하는 패킷:

```
55 55 23 01 01 23 AA AA
│  │  │  │  │  │  │  │
│  │  │  │  │  │  └──┴── 끝 마커
│  │  │  │  │  └──────── 체크섬 (0x23)
│  │  │  │  └─────────── DATA[0] = 0x01 (라벨 타입 1번)
│  │  │  └────────────── LEN = 0x01 (데이터 1바이트)
│  │  └───────────────── TYPE = 0x23 (SET_LABEL_TYPE 커맨드)
└──┴──────────────────── 시작 마커
```

### 실제 패킷 예시 2: SET_DENSITY (농도 3)

```
55 55 21 01 03 23 AA AA
         │  │  │
         │  │  └── 체크섬: 0x21 ^ 0x01 ^ 0x03 = 0x23
         │  └───── DATA = 0x03 (농도 3)
         └──────── TYPE = 0x21 (SET_DENSITY)
```

### 실제 패킷 예시 3: START_PRINT (9바이트 데이터)

```
55 55 01 09 00 01 00 00 00 00 00 01 00 [체크섬] AA AA
         │  │  └──────────────────────── DATA (9바이트)
         │  └──────────────────────────── LEN = 0x09
         └─────────────────────────────── TYPE = 0x01
```

DATA 9바이트의 의미:
- `00`: 예약 (사용 안 함)
- `01`: 인쇄 매수 (1장)
- `00 00 00 00 00`: 예약
- `01`: 플래그
- `00`: 예약

---

## 5. 체크섬 계산법

체크섬은 데이터가 전송 중에 손상되지 않았는지 확인하는 값이다.

### 계산 방법: XOR

XOR(배타적 논리합)은 두 비트가 다르면 1, 같으면 0이 되는 연산이다.

```
0 XOR 0 = 0
0 XOR 1 = 1
1 XOR 0 = 1
1 XOR 1 = 0
```

체크섬 = TYPE XOR LEN XOR DATA[0] XOR DATA[1] XOR ... XOR DATA[N]

### 코드

```python
def make_packet(type_, data):
    checksum = type_ ^ len(data)   # TYPE XOR LEN
    for b in data:
        checksum ^= b              # 각 데이터 바이트 XOR
    return bytes((0x55, 0x55, type_, len(data), *data, checksum, 0xaa, 0xaa))
```

### 직접 계산 예시: SET_LABEL_TYPE

```
TYPE = 0x23 = 0010 0011
LEN  = 0x01 = 0000 0001
DATA = 0x01 = 0000 0001

step1: 0x23 XOR 0x01
  0010 0011
  0000 0001
  ---------
  0010 0010 = 0x22

step2: 0x22 XOR 0x01 (DATA[0])
  0010 0010
  0000 0001
  ---------
  0010 0011 = 0x23

체크섬 = 0x23  ✓ (실제 패킷의 체크섬과 일치)
```

### 왜 XOR을 쓰나?

XOR은 같은 값을 두 번 XOR하면 원래 값으로 돌아온다 (`A XOR A = 0`).
수신측에서 받은 패킷 전체를 XOR하면 0이 나와야 정상이다.
0이 아니면 데이터가 손상된 것.

---

## 6. 커맨드 목록 및 의미

btsnoop 분석으로 파악한 커맨드들:

| TYPE (16진수) | 이름 | 설명 |
|--------------|------|------|
| `0x01` | START_PRINT | 인쇄 시작 선언 |
| `0x13` | SET_DIMENSION | 이미지 크기 전달 (행수, 열수) |
| `0x21` | SET_DENSITY | 인쇄 농도 설정 (1~5) |
| `0x23` | SET_LABEL_TYPE | 라벨 종류 설정 |
| `0x40` | GET_INFO | 프린터 정보 요청 |
| `0x85` | IMAGE_LINE | 이미지 한 줄 데이터 |
| `0xa3` | GET_PRINT_STATUS | 인쇄 상태 확인 |
| `0xe3` | PAGE_END | 페이지 끝 |
| `0xf3` | PRINT_END | 인쇄 완전 종료 |

### 응답 커맨드

프린터가 응답할 때는 요청 TYPE에 +1 또는 +16을 더한 값을 TYPE으로 사용한다.

```
요청: 0x23 (SET_LABEL_TYPE)
응답: 0x33 (= 0x23 + 0x10, +16)

요청: 0x01 (START_PRINT)
응답: 0x02 (= 0x01 + 0x01, +1)
```

응답 DATA 첫 바이트:
- `0x01` = 성공
- `0x00` = 실패

### SET_DIMENSION (0x13) 데이터 구조

이미지 크기를 프린터에 알려주는 커맨드. 13바이트 데이터:

```python
struct.pack('>HHHHHBBBH', rows, cols, quantity, 0, 0, 0, 0, 0, 0)
```

- `>` : 빅엔디안 (큰 바이트 먼저)
- `H` : unsigned short (2바이트)
- `B` : unsigned byte (1바이트)

**예시:** 이미지가 320행 96열, 1장 인쇄
```
rows=320, cols=96, quantity=1
→ 01 40  00 60  00 01  00 00  00 00  00  00  00  00 00
   (320)  (96)   (1)   (0)    (0)   (0) (0) (0)  (0)
```

---

## 7. 인쇄 순서 (전체 흐름)

### 전체 시퀀스

```
앱/라즈베리파이                    프린터
      │                              │
      │── 0x23 SET_LABEL_TYPE ──────>│
      │<─ 0x33 응답 (성공) ──────────│
      │                              │
      │── 0x21 SET_DENSITY ─────────>│
      │<─ 0x31 응답 (성공) ──────────│
      │                              │
      │── 0x01 START_PRINT ─────────>│
      │<─ 0x02 응답 (성공) ──────────│
      │                              │
      │── 0xa3 GET_PRINT_STATUS ────>│
      │<─ 0xb3 응답 ─────────────────│
      │                              │
      │── 0x13 SET_DIMENSION ───────>│
      │<─ 0x14 응답 (성공) ──────────│
      │                              │
      │── 0x85 이미지 0번째 줄 ──────>│  ← 응답 없음, 그냥 계속 보냄
      │── 0x85 이미지 1번째 줄 ──────>│
      │── 0x85 이미지 2번째 줄 ──────>│
      │   ... (전체 행 수만큼 반복)   │
      │── 0x85 이미지 마지막 줄 ─────>│
      │                              │
      │   (1초 대기)                  │
      │                              │
      │── 0xe3 PAGE_END ────────────>│
      │<─ 0xe4 응답 ─────────────────│
      │                              │
      │   (3초 대기, 실제 인쇄 중)    │
      │                              │
      │── 0xa3 GET_PRINT_STATUS ────>│
      │<─ 0xb3 응답 ─────────────────│
      │                              │
      │   (2초 대기)                  │
      │                              │
      │── 0xf3 PRINT_END ──────────>│
      │<─ 0xf4 응답 ─────────────────│
      │                              │
```

### 왜 이미지 데이터는 응답을 기다리지 않나?

이미지 데이터(0x85)는 수백~수천 줄이다. 줄마다 응답을 기다리면 너무 느리다.
그래서 그냥 연속으로 다 보내고 마지막에 1초 대기 후 PAGE_END를 보낸다.

### 코드에서 확인

```python
# 커맨드들은 응답 기다림
transceive(sock, 0x23, b'\x01')   # SET_LABEL_TYPE, 응답 대기
transceive(sock, 0x21, bytes([args.density]))  # SET_DENSITY, 응답 대기

# 이미지 데이터는 그냥 send (응답 안 기다림)
for pkt in printencoder.naive_encoder(img):
    sock.send(pkt.to_bytes())      # 응답 안 기다리고 계속 전송

time.sleep(1)  # 다 보낸 후 1초 대기
transceive(sock, 0xe3, b'\x01')   # PAGE_END, 응답 대기
```

---

## 8. 이미지 데이터 변환 방법 (0x85)

이 부분이 가장 핵심이다. 이미지 파일을 프린터가 이해하는 비트맵으로 변환한다.

### 단계별 변환

#### 단계 1: 이미지를 흑백으로 변환

```python
img = img.convert("L")   # 그레이스케일 (0~255)
img = img.convert("1")   # 1비트 흑백 (0 또는 255)
```

PIL의 "1" 모드에서:
- `0` = 검정
- `255` = 흰색

#### 단계 2: 한 줄씩 처리

이미지를 위에서 아래로 한 줄(row)씩 처리한다.

```python
for y in range(img.height):
    line_data = [img.getpixel((x, y)) for x in range(img.width)]
```

**예시:** 가로 16픽셀짜리 이미지의 첫 번째 줄
```
픽셀값: [0, 255, 0, 0, 255, 255, 255, 0, 255, 0, 0, 255, 255, 0, 0, 255]
         검  흰  검  검  흰   흰   흰  검  흰  검  검  흰   흰  검  검  흰
```

#### 단계 3: 픽셀을 비트로 변환

프린터는 검정=1, 흰색=0으로 받는다. PIL과 반대다.

```python
line_data = "".join("1" if pix == 0 else "0" for pix in line_data)
```

위 예시 결과:
```
픽셀값: [0,   255, 0,   0,   255, 255, 255, 0,   255, 0,   0,   255, 255, 0,   0,   255]
비트:   ["1", "0", "1", "1", "0", "0", "0", "1", "0", "1", "1", "0", "0", "1", "1", "0"]
문자열: "1011000101100110"
```

#### 단계 4: 비트 문자열을 바이트로 변환

8비트씩 묶어서 1바이트로 만든다.

```python
line_data = int(line_data, 2).to_bytes(math.ceil(img.width / 8), "big")
```

```
"1011000101100110"
 ↓ 2진수를 10진수로
 1011 0001 = 0xB1
 0110 0110 = 0x66

결과: b'\xB1\x66'
```

**가로 픽셀 수가 8의 배수가 아닐 때:**
`math.ceil(img.width / 8)`로 올림해서 바이트 수를 계산한다.
예: 가로 10픽셀 → `ceil(10/8) = 2`바이트, 나머지 6비트는 0으로 채움.

#### 단계 5: 헤더 붙이기

```python
header = struct.pack('>H3BB', y, 0, 0, 0, 1)
```

- `>H` : 행 번호 (2바이트, 빅엔디안)
- `3B` : `00 00 00` (예약, 의미 불명)
- `B` : `01` (항상 1)

**예시:** 5번째 줄 (y=5)
```
struct.pack('>H3BB', 5, 0, 0, 0, 1)
→ 00 05  00 00 00  01
   (5)   (예약)   (1)
```

#### 단계 6: 패킷 생성

```python
pkt = niimbotpacket.NiimbotPacket(0x85, header + line_data)
```

**완성된 0x85 패킷 예시** (가로 16픽셀, 0번째 줄):
```
55 55 85 08 00 00 00 00 00 01 B1 66 [체크섬] AA AA
│  │  │  │  └──────────────────────── DATA (8바이트)
│  │  │  └──────────────────────────── LEN = 8
│  │  └───────────────────────────────── TYPE = 0x85
└──┴──────────────────────────────────── 시작 마커

DATA 분해:
00 00 = 행 번호 0
00 00 00 = 예약
01 = 플래그
B1 66 = 픽셀 데이터 (16픽셀 = 2바이트)
```

### 전체 코드

```python
def naive_encoder(img):
    img = img.convert("L").convert("1")
    for y in range(img.height):
        # 한 줄의 픽셀값 가져오기
        line_data = [img.getpixel((x, y)) for x in range(img.width)]
        # PIL 0=검정 → 프린터 1=검정으로 반전
        line_data = "".join("1" if pix == 0 else "0" for pix in line_data)
        # 비트 문자열 → 바이트
        line_data = int(line_data, 2).to_bytes(math.ceil(img.width / 8), "big")
        # 헤더: 행번호(2) + 예약(3) + 플래그(1)
        header = struct.pack('>H3BB', y, 0, 0, 0, 1)
        # 패킷 생성
        pkt = niimbotpacket.NiimbotPacket(0x85, header + line_data)
        yield pkt
```

---

## 9. 응답 패킷 분석

### 응답 TYPE 규칙

요청 TYPE에 일정 값을 더한 것이 응답 TYPE이다.

```
SET_LABEL_TYPE  0x23 + 0x10 = 0x33  (응답)
SET_DENSITY     0x21 + 0x10 = 0x31  (응답)
START_PRINT     0x01 + 0x01 = 0x02  (응답)
SET_DIMENSION   0x13 + 0x01 = 0x14  (응답)
PAGE_END        0xe3 + 0x01 = 0xe4  (응답)
PRINT_END       0xf3 + 0x01 = 0xf4  (응답)
```

대부분 +1이고, 일부는 +16(0x10)이다. btsnoop에서 패턴을 보고 파악했다.

### 응답 데이터

```python
def _transceive(self, reqcode, data, respoffset=1):
    respcode = respoffset + reqcode  # 기본 +1
```

`respoffset=16`으로 호출하면 +16 응답을 기다린다:
```python
self._transceive(RequestCodeEnum.SET_LABEL_TYPE, bytes((n,)), 16)
```

### 특수 응답

- TYPE `0xDB` (219): 에러 → `ValueError` 발생
- TYPE `0x00`: 알 수 없음 → `NotImplementedError` 발생

### 실제 응답 패킷 예시

SET_LABEL_TYPE 성공 응답:
```
55 55 33 01 01 33 AA AA
         │  │
         │  └── DATA[0] = 0x01 (성공)
         └───── TYPE = 0x33 (0x23 + 0x10)
```

---

## 10. 코드와 프로토콜 연결

### 전체 시스템 구조

```
[사용자] curl POST /print
    ↓
[Go 서버] handler.go
    ↓ 인증 확인 (admin:admin)
[Go 서버] print.go → PrintTag()
    ↓ 이미지 생성
[Go] tag/tag.go → GenerateImage()
    ├── qr/qr.go → QR코드 이미지 생성
    ├── text/text.go → 텍스트 이미지 생성
    └── 두 이미지 합치기
    ↓ PNG 파일로 저장 (images/ 폴더)
[Go] python.go → runPythonScript()
    ↓ 파이썬 실행
[Python] niimprint/__main__.py
    ↓ 블루투스 연결
[Bluetooth RFCOMM] → 프린터
```

### Go → Python 연결 부분

```go
// python.go
func runPythonScript(cmdAndArgs ...string) error {
    cmd := exec.Command("/usr/bin/python3", cmdAndArgs...)
    // ...
}

// print.go
mac := os.Getenv("PRINTER_MAC")  // .env에서 MAC 주소 읽기
err = runPythonScript(
    "./niimprint/niimprint/__main__.py",
    "-a", mac,        // MAC 주소
    filename,         // 이미지 파일 경로
)
```

Go가 Python을 외부 프로세스로 실행하면서 이미지 파일 경로를 인자로 넘긴다.

### 이미지 생성 (Go)

```go
// tag/tag.go
func (g Generator) GenerateImage(tag, qrText string) (image.Image, error) {
    qrSize := g.height          // QR 크기 = 라벨 높이 (96px)
    qrCode, _ := qr.GetImage(qrText, qrSize)   // QR 이미지 생성

    txt, _ := text.GetImage(text.Config{
        FontFile: "fonts/NanumGothicBold.ttf",
        FontSize: 20.0,
        // ...
    }, tag)

    // 캔버스에 텍스트(왼쪽) + QR(오른쪽) 배치
    output := image.NewRGBA(image.Rect(0, 0, g.width, g.height))
    // 텍스트 그리기
    draw.Draw(output, ..., txt, ...)
    // QR 그리기
    draw.Draw(output, ..., qrCode, ...)

    return output, nil
}
```

최종 이미지 크기: **320 × 96 픽셀** (가로 × 세로)

### 이미지 방향

`__main__.py`에서 이미지가 가로로 길면 자동으로 270도 회전한다:

```python
if img.width / img.height > 1:  # 가로가 더 길면
    img = img.transpose(Image.ROTATE_270)
```

320×96 이미지 → 가로/세로 비율 = 3.33 > 1 → 270도 회전 → 96×320

회전 후 `rows=320, cols=96`이 된다.

---

## 11. btsnoop에서 실제로 어떻게 읽었나

### Wireshark 분석 방법

1. Wireshark 실행 → File → Open → `btsnoop_hci.log`
2. 필터: `btrfcomm` 입력
3. RFCOMM 데이터 패킷만 보임

### 패턴 찾기

btsnoop에서 인쇄 시작 직전부터 끝까지의 패킷을 보면:

```
# 앱 → 프린터 (인쇄 준비)
55 55 23 01 01 23 AA AA   ← 첫 번째 커맨드
55 55 21 01 03 23 AA AA   ← 두 번째 커맨드
55 55 01 09 00 01 ...     ← 세 번째 커맨드

# 프린터 → 앱 (응답들)
55 55 33 01 01 33 AA AA   ← 첫 번째 응답
55 55 31 01 01 31 AA AA   ← 두 번째 응답
55 55 02 01 01 02 AA AA   ← 세 번째 응답

# 이미지 데이터 (수백 개)
55 55 85 0D 00 00 00 00 00 01 FF FF FF FF FF FF AA AA  ← 흰색 줄
55 55 85 0D 00 01 00 00 00 01 FF 80 00 00 00 FF AA AA  ← 일부 검정
...
```

### 커맨드 의미 추론 방법

1. **반복 패턴 찾기**: `55 55 85`로 시작하는 패킷이 수백 개 → 이미지 데이터임을 추론
2. **데이터 크기 분석**: `55 55 85 0D` → LEN=13 → 헤더 6바이트 + 픽셀 7바이트 (56픽셀)
3. **흰색 줄 확인**: 흰색만 있는 줄은 `FF FF FF...`로 가득 참 → 흰색=1이 아니라 흰색=0 (비트 반전 확인)
4. **순서 분석**: 인쇄 전 항상 같은 순서로 3~4개 커맨드 → 초기화 시퀀스
5. **기존 오픈소스 참고**: niimprint 등 기존 역설계 프로젝트와 비교해서 커맨드 이름 확정

### 핵심 발견: 픽셀 비트 반전

btsnoop에서 흰색 배경 이미지를 인쇄할 때 `FF FF FF...`가 나왔다.
`0xFF = 1111 1111` → 모든 비트가 1 → **흰색 = 1**인 줄 알았는데...

실제로는 PIL의 "1" 모드에서 흰색=255(0xFF)이고,
이걸 비트로 변환할 때 **반전**해서 흰색=0, 검정=1로 만든다.

```python
# 흰색(255) → "0", 검정(0) → "1"
line_data = "".join("1" if pix == 0 else "0" for pix in line_data)
```

흰색만 있는 줄: `"0000 0000 0000 0000..."` → `int("000...", 2) = 0` → `b'\x00\x00...'`

**그런데 btsnoop에서는 `FF FF`가 나왔다?**

이미지가 270도 회전되면서 좌우가 바뀌고, 실제 인쇄 방향에서 흰색 영역이
프린터 내부에서 다시 처리되기 때문이다. 프린터 펌웨어가 비트를 반전해서 해석한다.

---

## 정리

| 단계 | 무슨 일이 일어나나 |
|------|------------------|
| 1 | 사용자가 HTTP POST로 텍스트와 QR URL 전송 |
| 2 | Go 서버가 PNG 이미지 생성 (320×96px) |
| 3 | Python이 이미지를 270도 회전 (96×320px) |
| 4 | 블루투스 RFCOMM으로 프린터 연결 |
| 5 | 초기화 커맨드 전송 (라벨 타입, 농도, 시작, 크기) |
| 6 | 이미지를 한 줄씩 비트맵으로 변환해서 0x85 패킷으로 전송 |
| 7 | 종료 커맨드 전송 (PAGE_END, PRINT_END) |
| 8 | 프린터가 라벨 출력 |
