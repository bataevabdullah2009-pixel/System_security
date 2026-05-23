export type EventStatus = "new" | "acknowledged" | "ignored" | "resolved";
export type EventActionStatus = Exclude<EventStatus, "new">;

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

async function requestJson<T>(
  path: string,
  init: RequestInit = {},
): Promise<T> {
  const response = await fetch(`${API_BASE_URL}${path}`, {
    headers: {
      "Content-Type": "application/json",
      ...init.headers,
    },
    ...init,
  });

  if (!response.ok) {
    const message = await response.text();
    throw new Error(message || `Request failed with ${response.status}`);
  }

  return response.json() as Promise<T>;
}

export function getVisionState(channel: string): Promise<VisionState> {
  return requestJson<VisionState>(`/api/vision/hikvision/${channel}/state`);
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
