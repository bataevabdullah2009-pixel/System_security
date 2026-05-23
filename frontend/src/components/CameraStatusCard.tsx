import { Clock3, Server, Video } from "lucide-react";

import { VisionState, VisionWorkerStatus } from "../api/client";

interface CameraStatusCardProps {
  channel: string;
  state: VisionState | null;
  workerStatus: VisionWorkerStatus;
  backendOnline: boolean;
}

function CameraStatusCard({
  channel,
  state,
  workerStatus,
  backendOnline,
}: CameraStatusCardProps) {
  const online = backendOnline && Boolean(state?.updated_at ?? workerStatus.running);

  return (
    <section className="panel camera-card">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Camera</span>
          <h2>Hikvision {channel}</h2>
        </div>
        <span className={`mini-status ${online ? "active" : "lost"}`}>
          {online ? "online" : "offline"}
        </span>
      </div>

      <div className="camera-metrics">
        <div>
          <Video size={17} />
          <span>Channel</span>
          <strong>{channel}</strong>
        </div>
        <div>
          <Server size={17} />
          <span>Worker</span>
          <strong>{workerStatus.running ? "running" : "offline"}</strong>
        </div>
        <div>
          <Clock3 size={17} />
          <span>Last frame</span>
          <strong>{state?.updated_at ? formatDateTime(state.updated_at) : "n/a"}</strong>
        </div>
      </div>
    </section>
  );
}

function formatDateTime(value: string): string {
  return new Intl.DateTimeFormat(undefined, {
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
  }).format(new Date(value));
}

export default CameraStatusCard;
