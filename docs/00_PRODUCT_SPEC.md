# 00 Product Spec

## Product

SmartGuard AI MVP is a local AI video surveillance and smart intercom MVP for private homes, small businesses, warehouses, car washes, cafes, offices, and similar small sites.

## Primary Goal

Help an owner avoid watching cameras 24/7 by detecting important security events, storing evidence locally, and sending notifications in later phases.

## MVP Scope

Planned MVP capabilities:

1. Connect one or more IP cameras through RTSP.
2. Show camera status.
3. Detect people.
4. Detect vehicles.
5. Detect motion in selected zones.
6. Create events after detections.
7. Save event snapshots.
8. Save short event clips.
9. Send Telegram notifications.
10. Provide a simple web dashboard.
11. Recognize only consented known people.
12. Keep an audit log for sensitive actions.

## Phase 0 Scope

Implemented in this phase:

- Repository documentation.
- Privacy and architecture specs.
- Minimal FastAPI backend.
- `GET /health`.
- Basic health test.

Explicitly not implemented in this phase:

- Camera ingestion.
- Object detection.
- Face detection or recognition.
- Telegram notifications.
- Event storage.
- Web dashboard.

## Non-MVP

- Mobile app.
- Complex cloud architecture.
- License plate recognition.
- Lock integration.
- Multi-tenant SaaS.
- Billing.
- City or government cameras.
- Face recognition without consent.
