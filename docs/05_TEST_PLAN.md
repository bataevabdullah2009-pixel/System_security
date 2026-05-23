# 05 Test Plan

## Phase 0 Tests

Goal: verify the backend starts and exposes a stable health endpoint.

### Automated

Run:

```powershell
cd backend
pytest
```

Expected:

- `GET /health` returns HTTP 200.
- Response contains `status = ok`.
- Response contains service name and version.

### Manual

Run:

```powershell
cd backend
uvicorn app.main:app --reload
```

Then call:

```powershell
Invoke-RestMethod http://127.0.0.1:8000/health
```

Expected JSON:

```json
{
  "status": "ok",
  "service": "smartguard-ai-backend",
  "version": "0.1.0"
}
```

## Later Phase Test Areas

- RTSP diagnostics with `scripts/test_camera.py`.
- Camera connection status.
- RTSP reconnect.
- Test video mode.
- Person and vehicle event creation.
- Snapshot and clip persistence.
- Notification cooldown.
- Consent validation before face enrollment.
- Consent revocation and biometric deletion.
- Unknown face non-enrollment.
- Audit log coverage.
