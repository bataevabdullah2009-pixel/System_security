# SmartGuard AI MVP

Локальная MVP-система AI-видеонаблюдения и умного домофона для малого бизнеса, частных домов и небольших объектов.

## Цель MVP

SmartGuard AI MVP подключается к локальным IP-камерам или тестовому видео, анализирует события безопасности, сохраняет их в локальное хранилище и показывает состояние системы через API и будущую web-панель.

Текущий шаг: Camera MVP diagnostic script для проверки RTSP-потока. YOLO, face recognition и Telegram не добавлены.

## Важно по privacy

- Распознавание лиц разрешено только для людей, добавленных в базу с согласием.
- Unknown faces не сохраняются как embedding и не используются для обучения.
- Биометрические данные не отправляются в Telegram, облачные AI API или внешние сервисы.
- На текущем этапе распознавание лиц, YOLO и Telegram не реализованы.

## Текущая структура

```text
backend/
  app/
    main.py
    config.py
    api/
      routes_health.py
  tests/
    test_health.py
  requirements.txt
docs/
  00_PRODUCT_SPEC.md
  01_ARCHITECTURE.md
  02_PRIVACY_AND_BIOMETRY.md
  03_MVP_PLAN.md
  05_TEST_PLAN.md
scripts/
  test_camera.py
  diagnose_rtsp.py
  diagnose_hikvision_snapshot.py
storage/
  events/
  clips/
  consents/
  face_enrollment/
  logs/
```

## Локальный запуск backend

```powershell
cd c:\System_security\System_security\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Проверка:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Ожидаемый ответ:

```json
{
  "status": "ok",
  "service": "smartguard-ai-backend",
  "version": "0.1.0"
}
```

## Проверка RTSP-камеры

1. Создайте локальный `.env` из примера:

```powershell
cd c:\System_security\System_security
Copy-Item .env.example .env
```

2. В `.env` укажите реальный `RTSP_URL`.

Для Hikvision/HiWatch обычно:

```env
RTSP_URL=rtsp://username:password@192.168.0.102:554/Streaming/Channels/101
```

Sub Stream:

```env
RTSP_URL=rtsp://username:password@192.168.0.102:554/Streaming/Channels/102
```

3. Установите зависимости:

```powershell
cd c:\System_security\System_security\backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

4. Запустите проверку камеры:

```powershell
cd c:\System_security\System_security
.\backend\.venv\Scripts\python.exe .\scripts\test_camera.py
```

Скрипт использует OpenCV `CAP_FFMPEG`, делает ограниченное число попыток чтения кадра и сохраняет snapshot только если `frame is not None`.

Snapshot сохраняется в:

```text
storage/events/
```

## Hikvision / HiWatch и HEVC

Если VLC или OpenCV показывают ошибки вида:

```text
Waiting for VPS/SPS/PPS
Failed decoding SPS
```

значит камера может отдавать H.265/HEVC или Smart Codec поток, который локальный декодер не читает стабильно.

Рекомендуемые настройки камеры:

- Main Stream: включить H.264.
- Sub Stream: включить H.264.
- Отключить H.265.
- Отключить H.265+.
- Отключить Smart Codec, Smart Video Coding или аналогичные vendor codec features.
- После изменения настроек перезапустить поток или камеру.

## Hikvision ISAPI HTTP snapshot

На некоторых Hikvision/HiWatch NVR RTSP-авторизация работает, но поток через VLC/OpenCV/FFmpeg декодируется серыми, зелёными или битыми кадрами даже при H.264. Для MVP можно использовать HTTP snapshot через Hikvision ISAPI.

Путь snapshot:

```text
/ISAPI/Streaming/channels/101/picture
```

Проверяемые каналы:

```text
http://HOST:80/ISAPI/Streaming/channels/101/picture
http://HOST:80/ISAPI/Streaming/channels/102/picture
http://HOST:80/ISAPI/Streaming/channels/201/picture
http://HOST:80/ISAPI/Streaming/channels/202/picture
```

Настройки `.env`:

```env
HIKVISION_HOST=192.168.0.102
HIKVISION_USER=admin
HIKVISION_PASSWORD=your_password_here
HIKVISION_HTTP_PORT=80
```

Запуск:

```powershell
cd c:\System_security\System_security
.\backend\.venv\Scripts\python.exe .\scripts\diagnose_hikvision_snapshot.py
```

Скрипт пробует Digest Auth и Basic Auth, сохраняет только ответы `image/jpeg` в `storage/snapshots/`, а пароль в логах маскирует.

## Camera Source Strategy

RTSP у некоторых Hikvision/HiWatch NVR может отдавать битые, серые или зелёные кадры через VLC/OpenCV/FFmpeg даже при включённом H.264. В этом MVP основным стабильным источником кадров выбран Hikvision ISAPI HTTP snapshot.

ISAPI snapshot используется как стабильный источник кадров для будущей AI detection pipeline. Позже можно добавить RTSP через более управляемый FFmpeg/GStreamer pipeline или Hikvision SDK, но это отдельный этап.

Основной путь:

```text
/ISAPI/Streaming/channels/101/picture
```

Backend endpoints:

```text
GET /api/cameras/hikvision/diagnose
GET /api/cameras/hikvision/{channel}/snapshot
GET /api/cameras/hikvision/{channel}/latest
GET /api/cameras/hikvision/{channel}/stream.mjpg
```

HTML для быстрой проверки snapshot:

```html
<img src="http://127.0.0.1:8000/api/cameras/hikvision/101/snapshot" />
```

HTML для быстрой проверки MJPEG:

```html
<img src="http://127.0.0.1:8000/api/cameras/hikvision/101/stream.mjpg" />
```

## Manual check

Browser напрямую к NVR:

```text
http://192.168.0.102/ISAPI/Streaming/channels/101/picture
```

Backend snapshot:

```text
http://127.0.0.1:8000/api/cameras/hikvision/101/snapshot
```

Backend MJPEG:

```text
http://127.0.0.1:8000/api/cameras/hikvision/101/stream.mjpg
```

Диагностика всех каналов:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/cameras/hikvision/diagnose
```

## Phase 2 — Object Detection MVP

Фаза 2 добавляет локальное object detection на snapshot-кадрах Hikvision ISAPI. Система ищет только MVP-классы:

- `person`
- `car`
- `truck`
- `motorcycle`
- `bicycle`

Telegram, face recognition, age detection и height estimation в эту фазу не входят.

Модель по умолчанию:

```env
DETECTION_MODEL=yolo11n.pt
DETECTION_CONFIDENCE_THRESHOLD=0.45
DETECTION_ALLOWED_CLASSES=person,car,truck,motorcycle,bicycle
DETECTION_IMAGE_SIZE=640
```

Ultralytics может автоматически скачать `yolo11n.pt` при первом запуске detection endpoint. Если модель или пакет недоступны, API вернёт понятную ошибку, а backend продолжит работать.

Установка и запуск:

```powershell
cd c:\System_security\System_security\backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Проверки:

```text
http://127.0.0.1:8000/api/detection/hikvision/101
http://127.0.0.1:8000/api/detection/hikvision/101/annotated
http://127.0.0.1:8000/api/detection/hikvision/diagnose
```

Annotated snapshots сохраняются локально:

```text
storage/detections/
```

## Тесты

```powershell
cd c:\System_security\System_security\backend
pytest
```

## Репозиторий

GitHub: https://github.com/bataevabdullah2009-pixel/System_security.git

## Detection Backend Strategy

Phase 2.5 separates object detection from a single YOLO implementation into backend adapters. The API routes stay the same, but `DETECTION_BACKEND` controls which inference backend is used.

Supported values:

- `ultralytics_yolo`: development backend based on Ultralytics YOLO. It is accurate and convenient, but heavy because it requires Torch. Install it only for AI development.
- `mock`: test/demo backend without AI dependencies. It returns fixed detections and works on weak PCs.
- `onnxruntime`: future lightweight CPU backend.
- `openvino`: future Intel CPU/NPU backend.
- `ncnn`: future edge/mobile backend.
- `camera_ai`: future integration with cameras where analytics runs inside the camera.
- `disabled`: returns no detections.

Minimal backend without YOLO/Torch:

```powershell
cd c:\System_security\System_security\backend
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

AI dev mode with YOLO:

```powershell
cd c:\System_security\System_security\backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
pip install -r requirements-ai-dev.txt
```

Example `.env` for lightweight mock mode:

```env
DETECTION_ENABLED=true
DETECTION_BACKEND=mock
```

Example `.env` for YOLO development:

```env
DETECTION_ENABLED=true
DETECTION_BACKEND=ultralytics_yolo
DETECTION_MODEL=yolo11n.pt
```

The `yolo11n.pt` model is not committed to Git. In YOLO development mode Ultralytics can download it automatically on first use. Production clients should not need a powerful PC at the first stage: the intended path is model export to ONNX/OpenVINO/NCNN, or using AI cameras / edge boxes that perform inference outside the main backend.

## Phase 3 — Event Engine MVP

Detection finds objects on camera snapshots. Event Engine turns those detections into security events and stores them in SQLite.

Current event types:

- `person_detected`
- `vehicle_detected`
- `camera_snapshot_error`
- `detection_error`

Each event has a status:

- `new`
- `acknowledged`
- `resolved`
- `ignored`

Cooldown protects the system from creating the same event every second. The key is built from channel and event type, for example `101:vehicle_detected`. If the latest event with the same key is newer than `EVENT_COOLDOWN_SECONDS`, the new event is skipped.

Telegram and face recognition are still not added in this phase.

Run backend:

```powershell
cd c:\System_security\System_security\backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

After Phase 3, reinstall minimal backend dependencies so SQLAlchemy is available:

```powershell
cd c:\System_security\System_security\backend
.\.venv\Scripts\python.exe -m pip install -r requirements.txt
```

If PowerShell blocks `Activate.ps1`, allow activation only for the current shell process:

```powershell
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass
.\.venv\Scripts\Activate.ps1
```

You can also run tests without activating the venv:

```powershell
cd c:\System_security\System_security\backend
.\.venv\Scripts\python.exe -m pytest
```

Mock mode for weak PCs and tests:

```env
DETECTION_BACKEND=mock
EVENT_ENABLED=true
EVENT_COOLDOWN_SECONDS=60
DATABASE_URL=sqlite:///./smartguard.db
```

Checks:

```text
GET  http://127.0.0.1:8000/api/events
POST http://127.0.0.1:8000/api/events/process/hikvision/101
GET  http://127.0.0.1:8000/api/events/diagnose/hikvision
GET  http://127.0.0.1:8000/api/events/{event_id}
PATCH http://127.0.0.1:8000/api/events/{event_id}/status
```

Status update body:

```json
{
  "status": "acknowledged"
}
```

## Phase 4 — Telegram Alerts MVP

Telegram Alerts sends outbound notifications when Event Engine creates a new `new` event. The alert includes event id, event type, channel, title, confidence when available, created time, inline status buttons, and the annotated snapshot image when it exists.

This phase does not add face recognition, age detection, height estimation, dashboard, SaaS, or payments.

Create a Telegram bot:

1. Open Telegram and start `@BotFather`.
2. Run `/newbot`.
3. Follow BotFather prompts and copy the bot token.
4. Put the token into `.env` as `TELEGRAM_BOT_TOKEN`.

Find `TELEGRAM_CHAT_ID`:

1. Send any message to your new bot.
2. Open this URL in a browser, replacing the token:

```text
https://api.telegram.org/botYOUR_TOKEN/getUpdates
```

3. Find `chat.id` in the response and put it into `.env` as `TELEGRAM_CHAT_ID`.

Telegram `.env` example:

```env
TELEGRAM_ALERTS_ENABLED=true
TELEGRAM_BOT_TOKEN=CHANGE_ME
TELEGRAM_CHAT_ID=CHANGE_ME
TELEGRAM_SEND_PHOTOS=true
TELEGRAM_ALERT_COOLDOWN_SECONDS=5
```

Do not commit real Telegram tokens or chat ids. `.env` is ignored by Git.

Run backend:

```powershell
cd c:\System_security\System_security\backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Checks:

```text
GET  http://127.0.0.1:8000/api/telegram/diagnose
POST http://127.0.0.1:8000/api/telegram/test
POST http://127.0.0.1:8000/api/events/process/hikvision/101
POST http://127.0.0.1:8000/api/telegram/callback
```

## Phase 5 — Real Live Vision Tracking MVP

Phase 5 moves SmartGuard AI from single snapshot detection to a lazy live vision tracking loop:

```text
Hikvision ISAPI snapshot -> detection backend -> tracker -> track_id -> path -> zones -> live state
```

The first MVP does not run an unmanaged infinite daemon. `POST /api/vision/hikvision/{channel}/update` performs one controlled update: it fetches a fresh camera frame, runs the configured detection backend, updates in-memory tracked objects, assigns zone ids, creates safe Event Engine candidates through cooldown, and saves the latest annotated frame.

Tracking is not face recognition. A `track_id` is temporary runtime state for one moving object and does not establish a person's identity. Unknown people are not stored as biometric profiles, no face embeddings are created, and no age detection or height estimation is performed. Face recognition must be a separate consent-based phase.

The system does not accuse anyone of theft or crime. Phase 5 only creates neutral security alerts such as `tracked_person_detected`, `tracked_vehicle_detected`, `person_entered_zone`, and `vehicle_entered_zone` for human review.

New environment values:

```env
TRACKING_ENABLED=true
TRACK_TTL_SECONDS=10
TRACK_MAX_PATH_POINTS=30
TRACK_IOU_THRESHOLD=0.3
TRACK_DISTANCE_THRESHOLD=120
```

Zones are configured locally in:

```text
storage/config/zones.json
```

Example:

```json
{
  "101": [
    {
      "id": "entrance",
      "name": "Entrance",
      "polygon": [[10, 10], [300, 10], [300, 300], [10, 300]]
    }
  ]
}
```

New endpoints:

```text
GET  /api/vision/hikvision/{channel}/state
POST /api/vision/hikvision/{channel}/update
GET  /api/vision/hikvision/{channel}/annotated
GET  /api/vision/hikvision/{channel}/stream.mjpg
```

Quick check:

```powershell
cd c:\System_security\System_security\backend
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
uvicorn app.main:app --reload
```

Then:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:8000/api/vision/hikvision/101/update
Invoke-RestMethod http://127.0.0.1:8000/api/vision/hikvision/101/state
```

Open the annotated frame:

```text
http://127.0.0.1:8000/api/vision/hikvision/101/annotated
```

Run tests:

```powershell
cd c:\System_security\System_security\backend
pytest
```

Manual callback body:

```json
{
  "callback_data": "event:1:acknowledged"
}
```

### Telegram webhook

`POST /api/telegram/webhook` accepts real Telegram Update JSON and handles `callback_query` button presses. When a user taps an inline button in Telegram, the backend parses callback data like `event:1:acknowledged`, updates the event status, and answers the callback query through Telegram API.

Localhost cannot receive Telegram webhooks directly because Telegram needs a public HTTPS URL. For local testing, expose the backend with ngrok or cloudflared, then point Telegram to:

```text
https://YOUR_PUBLIC_URL/api/telegram/webhook
```

Production webhook setup should use a real public domain with HTTPS. Manual local callback testing remains available through:

```text
POST http://127.0.0.1:8000/api/telegram/callback
```
