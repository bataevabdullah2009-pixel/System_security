import { Layers, Target, Unlock } from "lucide-react";
import { TargetStatus } from "../api/client";

interface TargetLockControlPanelProps {
  target: TargetStatus | null;
  loading: boolean;
  hudStyle: string;
  onLockStrongest: () => void;
  onClearLock: () => void;
  onHudStyleChange: (style: string) => void;
}

function TargetLockControlPanel({
  target,
  loading,
  hudStyle,
  onLockStrongest,
  onClearLock,
  onHudStyleChange,
}: TargetLockControlPanelProps) {
  const isLocked = target?.locked ?? false;

  return (
    <section className="panel target-lock-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Tactical Locking</span>
          <h2>Target Control</h2>
        </div>
        <div className={`status-badge ${isLocked ? "locked" : "unlocked"}`}>
          <Target size={14} className={isLocked ? "pulse-lock" : ""} />
          <span>{isLocked ? "LOCKED" : "STANDBY"}</span>
        </div>
      </div>

      <div className="panel-body">
        {isLocked && target ? (
          <div className="target-card">
            <div className="target-item">
              <span className="label">Target ID</span>
              <strong className="value track-id-value">#{target.track_id}</strong>
            </div>
            <div className="target-item">
              <span className="label">Classification</span>
              <span className="value uppercase">{target.class_name || "Unknown"}</span>
            </div>
            <div className="target-item">
              <span className="label">Tracking Status</span>
              <span className={`mini-status ${target.status || "active"}`}>
                {target.status || "active"}
              </span>
            </div>
          </div>
        ) : (
          <div className="empty-target">
            <p>No active target lock. Select an object on the live view or click to lock strongest track.</p>
          </div>
        )}

        <div className="action-row">
          <button
            type="button"
            className="btn btn-primary"
            onClick={onLockStrongest}
            disabled={loading}
          >
            <Target size={15} />
            <span>Lock Strongest</span>
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onClearLock}
            disabled={!isLocked || loading}
          >
            <Unlock size={15} />
            <span>Clear Lock</span>
          </button>
        </div>

        <div className="style-selector">
          <label>
            <Layers size={14} />
            <span>HUD Style Mode</span>
          </label>
          <div className="button-group">
            {["clean_hud", "tactical", "basic"].map((style) => (
              <button
                type="button"
                key={style}
                className={`btn-toggle ${hudStyle === style ? "active" : ""}`}
                onClick={() => onHudStyleChange(style)}
              >
                {style === "clean_hud" ? "Minimal" : style === "tactical" ? "Tactical" : "Basic"}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export default TargetLockControlPanel;
