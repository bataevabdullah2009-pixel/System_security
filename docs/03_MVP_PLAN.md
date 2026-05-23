# 03 MVP Plan

## Phase 0 - Audit / Setup / Specs

Goal: create documentation, clean repository structure, and a minimal backend.

Deliverables:

- Product spec.
- Architecture spec.
- Privacy and biometry spec.
- MVP plan.
- Test plan.
- `.env.example`.
- `AGENTS.md`.
- `README.md`.
- FastAPI `GET /health`.
- Basic health test.

Stop condition:

- Do not continue to camera, detection, Telegram, face recognition, or dashboard until the user reviews Phase 0.

## Phase 1 - Camera MVP

Goal: connect a test video source or RTSP camera.

Deliverables:

- Camera model.
- Camera API.
- RTSP or `video.mp4` source.
- Camera worker.
- Reconnect and status online/offline.

## Phase 2 - Object Detection MVP

Goal: detect people and vehicles locally.

Deliverables:

- Local object detection backend.
- Person and vehicle detections.
- Event creation.
- Snapshot persistence.
- Events API.

## Phase 3 - Telegram Notifications

Goal: send event notifications to the owner.

Deliverables:

- Telegram settings from `.env`.
- Notification service.
- Cooldown and anti-spam.
- Snapshot sending.
- Error logging.

## Phase 4 - Face Recognition With Consent

Goal: recognize only approved known people.

Deliverables:

- Person, Consent, FaceEmbedding models.
- Person and consent APIs.
- Face enrollment only with active consent.
- Unknown faces not saved as embeddings.
- Consent revocation and face data deletion.

## Phase 5 - Web Dashboard

Goal: provide a simple admin dashboard.

Deliverables:

- Dashboard, Cameras, Events, Faces, Settings pages.
- Snapshot viewer.
- Person enrollment flow.
- Consent revocation flow.

## Phase 6 - Hardening

Goal: make MVP ready for first real pilot site.

Deliverables:

- Admin auth.
- Logs and health checks.
- Worker restart strategy.
- RTSP error handling.
- Storage limits and cleanup.
- SQLite backup.
- Local deployment guide.
