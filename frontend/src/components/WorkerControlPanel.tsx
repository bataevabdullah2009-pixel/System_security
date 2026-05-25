import { Pause, Play, RefreshCw, ChevronDown } from "lucide-react";
import { VisionWorkerStatus } from "../api/client";
import { useTranslation } from "../api/i18n";

interface WorkerControlPanelProps {
  status: VisionWorkerStatus;
  statusError: string | null;
  loadingAction: string | null;
  onStart: () => void;
  onStop: () => void;
  onRefresh: () => void;
}

function WorkerControlPanel({
  status,
  statusError,
  loadingAction,
  onStart,
  onStop,
  onRefresh,
}: WorkerControlPanelProps) {
  const { t } = useTranslation();

  return (
    <section className="panel worker-control-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{t("workerManagement")}</span>
          <h2>{t("workerControl")}</h2>
        </div>
        <span className={`mini-status ${status.running ? "active" : "lost"}`}>
          {status.running ? t("statusOnline") : t("statusOffline")}
        </span>
      </div>

      <div className="control-grid" style={{ paddingBottom: "14px" }}>
        <button
          type="button"
          onClick={onStart}
          disabled={loadingAction === "start"}
          title={t("btnStart")}
        >
          <Play size={16} />
          <span>{t("btnStart")}</span>
        </button>
        <button
          type="button"
          onClick={onStop}
          disabled={loadingAction === "stop"}
          title={t("btnStop")}
        >
          <Pause size={16} />
          <span>{t("btnStop")}</span>
        </button>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loadingAction === "refresh"}
          title={t("btnRefresh")}
        >
          <RefreshCw size={16} />
          <span>{t("btnRefresh")}</span>
        </button>
      </div>

      {/* Diagnostics block (Operator Mode) */}
      <details className="diagnostics-details" style={{ borderTop: "1px solid rgba(157, 180, 190, 0.12)", padding: "12px 14px" }}>
        <summary style={{ display: "flex", alignItems: "center", gap: "6px", cursor: "pointer", color: "#8fa7b0", fontSize: "0.82rem", fontWeight: 700, userSelect: "none" }}>
          <ChevronDown size={14} className="details-chevron" />
          <span>{t("diagnosticsTitle")}</span>
        </summary>
        <dl className="metric-list" style={{ marginTop: "10px", padding: 0 }}>
          <div>
            <dt>{t("updatesCount")}</dt>
            <dd>{status.updates_count}</dd>
          </div>
          <div>
            <dt>{t("measuredFPS")}</dt>
            <dd>{status.measured_fps ? `${status.measured_fps.toFixed(1)} FPS` : "--"}</dd>
          </div>
          <div>
            <dt>{t("lastUpdate")}</dt>
            <dd>{status.last_update_at ? formatDateTime(status.last_update_at) : "--"}</dd>
          </div>
          <div>
            <dt>{t("lastError")}</dt>
            <dd style={{ color: (statusError || status.last_error) ? "#ff7850" : undefined }}>
              {statusError ?? status.last_error ?? "--"}
            </dd>
          </div>
        </dl>
      </details>
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

export default WorkerControlPanel;
