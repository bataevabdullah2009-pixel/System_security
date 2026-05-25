import { Clock3, Server, Video } from "lucide-react";
import { VisionState, VisionWorkerStatus } from "../api/client";
import { useTranslation } from "../api/i18n";

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
  const { t } = useTranslation();
  const online = backendOnline && Boolean(state?.updated_at ?? workerStatus.running);

  return (
    <section className="panel camera-card">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{t("cameraLiveView")}</span>
          <h2>{t("channelLabel", { channel })}</h2>
        </div>
        <span className={`mini-status ${online ? "active" : "lost"}`}>
          {online ? t("statusOnline") : t("statusOffline")}
        </span>
      </div>

      <div className="camera-metrics">
        <div>
          <Video size={17} />
          <span>{t("cameraLiveView")}</span>
          <strong>{channel}</strong>
        </div>
        <div>
          <Server size={17} />
          <span>{t("workerControl")}</span>
          <strong>{workerStatus.running ? t("statusRunning") : t("statusStopped")}</strong>
        </div>
        <div>
          <Clock3 size={17} />
          <span>{t("lastUpdate")}</span>
          <strong>{state?.updated_at ? formatDateTime(state.updated_at) : "--"}</strong>
        </div>
      </div>
    </section>
  );
}

function formatDateTime(value: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      hour: "2-digit",
      minute: "2-digit",
      second: "2-digit",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export default CameraStatusCard;
