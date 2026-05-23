export type EventStatus = "new" | "acknowledged" | "ignored" | "resolved";
export type EventActionStatus = Exclude<EventStatus, "new">;

export interface HealthStatus {
  status: string;
  service: string;
  version: string;
}

export interface VisionWorkerStatus {
  channel: string;
  running: boolean;
  interval_seconds?: number;
  last_update_at?: string | null;
  last_error?: string | null;
  updates_count: number;
}

export interface TrackedObject {
  track_id: number;
  channel: string;
  class_name: string;
  confidence: number;
  bbox: number[];
  center: number[];
  path: number[][];
  first_seen_at: string;
  last_seen_at: string;
  status: "active" | "lost" | string;
  zone_ids: string[];
  dwell: Record<string, number>;
}

export interface VisionState {
  channel: string;
  updated_at: string | null;
  worker: Partial<VisionWorkerStatus>;
  objects: TrackedObject[];
  snapshot_path?: string;
  annotated_frame_path?: string;
  events?: {
    created_events: SecurityEvent[];
    skipped_events: Array<Record<string, unknown>>;
  };
}

export interface SecurityEvent {
  id: number;
  event_type: string;
  status: EventStatus;
  channel: string;
  source: string;
  title: string;
  description: string;
  confidence: number | null;
  snapshot_path: string | null;
  annotated_snapshot_path: string | null;
  detections: Array<Record<string, unknown>>;
  event_key: string;
  created_at: string;
  updated_at: string;
  acknowledged_at: string | null;
  resolved_at: string | null;
}

export const API_BASE_URL =
  import.meta.env.VITE_API_BASE_URL ?? "http://127.0.0.1:8000";

if (import.meta.env.DEV) {
  console.info(`[SmartGuard] API base URL: ${API_BASE_URL}`);
}

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const headers = new Headers(init.headers);
  if (init.body !== undefined) {
    headers.set("Content-Type", "application/json");
  }

  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers,
    ...init,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getHealth(): Promise<HealthStatus> {
  return requestJson<HealthStatus>("/health");
}

export function getVisionState(channel: string): Promise<VisionState> {
  return requestJson<Record<string, unknown>>(
    `/api/vision/hikvision/${channel}/state`,
  ).then(normalizeVisionState);
}

export function startVisionWorker(
  channel: string,
): Promise<VisionWorkerStatus> {
  return requestJson<VisionWorkerStatus>(
    `/api/vision/hikvision/${channel}/worker/start`,
    { method: "POST" },
  );
}

export function stopVisionWorker(channel: string): Promise<VisionWorkerStatus> {
  return requestJson<VisionWorkerStatus>(
    `/api/vision/hikvision/${channel}/worker/stop`,
    { method: "POST" },
  );
}

export function getVisionWorkerStatus(
  channel: string,
): Promise<VisionWorkerStatus> {
  return requestJson<VisionWorkerStatus>(
    `/api/vision/hikvision/${channel}/worker/status`,
  );
}

export function getEvents(): Promise<SecurityEvent[]> {
  return requestJson<SecurityEvent[]>("/api/events?limit=50");
}

export function updateEventStatus(
  eventId: number,
  status: EventActionStatus,
): Promise<SecurityEvent> {
  return requestJson<SecurityEvent>(`/api/events/${eventId}/status`, {
    method: "PATCH",
    body: JSON.stringify({ status }),
  });
}

export function getVisionStreamUrl(channel: string): string {
  return `${API_BASE_URL}/api/vision/hikvision/${channel}/stream.mjpg`;
}

export function getAnnotatedFrameUrl(channel: string): string {
  return `${API_BASE_URL}/api/vision/hikvision/${channel}/annotated`;
}

function normalizeVisionState(payload: Record<string, unknown>): VisionState {
  const rawObjects = Array.isArray(payload.objects)
    ? payload.objects
    : Array.isArray(payload.tracks)
      ? payload.tracks
      : [];

  return {
    channel: String(payload.channel ?? ""),
    updated_at:
      typeof payload.updated_at === "string" ? payload.updated_at : null,
    worker: isRecord(payload.worker) ? payload.worker : {},
    objects: rawObjects.filter(isRecord).map(normalizeTrackedObject),
    snapshot_path:
      typeof payload.snapshot_path === "string" ? payload.snapshot_path : undefined,
    annotated_frame_path:
      typeof payload.annotated_frame_path === "string"
        ? payload.annotated_frame_path
        : undefined,
    events: isRecord(payload.events)
      ? {
          created_events: Array.isArray(payload.events.created_events)
            ? payload.events.created_events.filter(isRecord).map(normalizeEvent)
            : [],
          skipped_events: Array.isArray(payload.events.skipped_events)
            ? payload.events.skipped_events.filter(isRecord)
            : [],
        }
      : undefined,
  };
}

function normalizeTrackedObject(payload: Record<string, unknown>): TrackedObject {
  return {
    track_id: Number(payload.track_id ?? 0),
    channel: String(payload.channel ?? ""),
    class_name: String(payload.class_name ?? "object"),
    confidence: Number(payload.confidence ?? 0),
    bbox: toNumberArray(payload.bbox),
    center: toNumberArray(payload.center),
    path: Array.isArray(payload.path)
      ? payload.path.map(toNumberArray).filter((point) => point.length > 0)
      : [],
    first_seen_at: String(payload.first_seen_at ?? ""),
    last_seen_at: String(payload.last_seen_at ?? ""),
    status: String(payload.status ?? "active"),
    zone_ids: Array.isArray(payload.zone_ids)
      ? payload.zone_ids.map(String)
      : [],
    dwell: isRecord(payload.dwell) ? toNumberRecord(payload.dwell) : {},
  };
}

function normalizeEvent(payload: Record<string, unknown>): SecurityEvent {
  return {
    id: Number(payload.id ?? 0),
    event_type: String(payload.event_type ?? ""),
    status: normalizeEventStatus(payload.status),
    channel: String(payload.channel ?? ""),
    source: String(payload.source ?? ""),
    title: String(payload.title ?? "Security event"),
    description: String(payload.description ?? ""),
    confidence:
      typeof payload.confidence === "number" ? payload.confidence : null,
    snapshot_path:
      typeof payload.snapshot_path === "string" ? payload.snapshot_path : null,
    annotated_snapshot_path:
      typeof payload.annotated_snapshot_path === "string"
        ? payload.annotated_snapshot_path
        : null,
    detections: Array.isArray(payload.detections)
      ? payload.detections.filter(isRecord)
      : [],
    event_key: String(payload.event_key ?? ""),
    created_at: String(payload.created_at ?? new Date().toISOString()),
    updated_at: String(payload.updated_at ?? new Date().toISOString()),
    acknowledged_at:
      typeof payload.acknowledged_at === "string"
        ? payload.acknowledged_at
        : null,
    resolved_at:
      typeof payload.resolved_at === "string" ? payload.resolved_at : null,
  };
}

function normalizeEventStatus(value: unknown): EventStatus {
  if (
    value === "new" ||
    value === "acknowledged" ||
    value === "ignored" ||
    value === "resolved"
  ) {
    return value;
  }
  return "new";
}

function toNumberArray(value: unknown): number[] {
  if (!Array.isArray(value)) {
    return [];
  }
  return value.map(Number).filter((item) => Number.isFinite(item));
}

function toNumberRecord(value: Record<string, unknown>): Record<string, number> {
  return Object.fromEntries(
    Object.entries(value)
      .map(([key, item]) => [key, Number(item)] as const)
      .filter(([, item]) => Number.isFinite(item)),
  );
}

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}
