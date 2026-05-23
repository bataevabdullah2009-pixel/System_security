import { Pause, Play, RefreshCw } from "lucide-react";

import { VisionWorkerStatus } from "../api/client";

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
  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Runtime</span>
          <h2>Worker control</h2>
        </div>
        <span className={`mini-status ${status.running ? "active" : "lost"}`}>
          {status.running ? "running" : "offline"}
        </span>
      </div>

      <div className="control-grid">
        <button
          type="button"
          onClick={onStart}
          disabled={loadingAction === "start"}
          title="Start worker"
        >
          <Play size={16} />
          <span>Start</span>
        </button>
        <button
          type="button"
          onClick={onStop}
          disabled={loadingAction === "stop"}
          title="Stop worker"
        >
          <Pause size={16} />
          <span>Stop</span>
        </button>
        <button
          type="button"
          onClick={onRefresh}
          disabled={loadingAction === "refresh"}
          title="Refresh status"
        >
          <RefreshCw size={16} />
          <span>Refresh</span>
        </button>
      </div>

      <dl className="metric-list">
        <div>
          <dt>Updates</dt>
          <dd>{status.updates_count}</dd>
        </div>
        <div>
          <dt>Last update</dt>
          <dd>{status.last_update_at ? formatDateTime(status.last_update_at) : "n/a"}</dd>
        </div>
        <div>
          <dt>Last error</dt>
          <dd>{statusError ?? status.last_error ?? "none"}</dd>
        </div>
      </dl>
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

export default WorkerControlPanel;
