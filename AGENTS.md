# AGENTS.md

## Project Name

SmartGuard AI MVP

## Development Rules

- Work in small, verifiable phases: SPEC, PLAN, SMALL CODE PATCH, TEST, REPORT, NEXT STEP.
- Do not add face recognition, object detection, Telegram, Docker, or cloud integrations before the relevant phase.
- Keep the system local-first.
- Do not send or store biometric data outside the approved local storage design.
- Do not create face embeddings for unknown people.
- Do not automatically enroll unknown faces.
- Update documentation before implementation when behavior or architecture changes.
- Prefer simple dependencies and clear module boundaries.

## Current Phase

Phase 0: Audit / Setup / Specs.

Allowed in this phase:

- Documentation.
- Minimal repository structure.
- Minimal FastAPI backend.
- `GET /health`.
- Basic health test.

Not allowed in this phase:

- YOLO or object detection.
- Face recognition.
- Telegram notifications.
- Camera workers.
- Cloud storage.
- Biometric enrollment.

## Repository

Remote repository:

https://github.com/bataevabdullah2009-pixel/System_security.git
