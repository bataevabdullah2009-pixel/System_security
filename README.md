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

## Тесты

```powershell
cd c:\System_security\System_security\backend
pytest
```

## Репозиторий

GitHub: https://github.com/bataevabdullah2009-pixel/System_security.git
