# 01 Architecture

## MVP Architecture

```text
IP Camera / RTSP Stream
        |
Camera Ingestion Service
        |
Frame Processing Pipeline
        |
Object Detection Module
        |
Face Detection Module
        |
Face Recognition Module
        |
Event Engine
        |
Database + Local Storage
        |
API Server
        |
Web Dashboard + Telegram Bot
```

## Local-First Principle

The MVP must run on a customer-owned PC, mini-PC, or local server. Video, events, consent documents, and future biometric data stay local unless a later phase explicitly approves another deployment model.

## Backend Modules

- `camera-service`: RTSP connection, availability checks, frame reading, reconnect, analytics FPS limits.
- `detection-service`: person, vehicle, and motion detection with zones and false-positive filtering.
- `face-service`: face detection, quality checks, consent-safe embeddings, known/unknown/low_quality result.
- `event-service`: event creation, snapshot and clip persistence, database record creation.
- `notification-service`: future Telegram notifications, cooldown, anti-spam, message templates.
- `api-server`: REST API, admin management, cameras, events, persons, settings.
- `storage`: local files for events, clips, consents, face enrollment, and logs.

## Phase 0 Backend

Phase 0 includes only:

- FastAPI application factory in `backend/app/main.py`.
- Health route in `backend/app/api/routes_health.py`.
- Basic configuration in `backend/app/config.py`.

No camera, detection, face, event, or notification workers are active in Phase 0.

## Future Data Storage

Initial MVP storage will use SQLite. PostgreSQL can be introduced after the local MVP proves the workflow.

Media and sensitive files are separated:

- `storage/events`: event snapshots.
- `storage/clips`: short event clips.
- `storage/consents`: consent documents or references.
- `storage/face_enrollment`: approved enrollment images only.
- `storage/logs`: application logs.
