# SmartGuard AI MVP

Локальная MVP-система AI-видеонаблюдения и умного домофона для малого бизнеса, частных домов и небольших объектов.

## Цель MVP

SmartGuard AI MVP подключается к локальным IP-камерам или тестовому видео, анализирует события безопасности, сохраняет их в локальное хранилище и показывает состояние системы через API и будущую web-панель.

Фаза 0 содержит только базовую структуру, документацию и минимальный backend с `GET /health`.

## Важно по privacy

- Распознавание лиц разрешено только для людей, добавленных в базу с согласием.
- Unknown faces не сохраняются как embedding и не используются для обучения.
- Биометрические данные не отправляются в Telegram, облачные AI API или внешние сервисы.
- В Фазе 0 распознавание лиц, YOLO и Telegram не реализованы.

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
storage/
  events/
  clips/
  consents/
  face_enrollment/
  logs/
```

## Локальный запуск backend

```powershell
cd backend
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

## Тесты

```powershell
cd backend
pytest
```

## Репозиторий

GitHub: https://github.com/bataevabdullah2009-pixel/System_security.git
