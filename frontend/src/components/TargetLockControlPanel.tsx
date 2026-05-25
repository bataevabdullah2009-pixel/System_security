import { Layers, Target, Unlock } from "lucide-react";
import { TargetStatus } from "../api/client";
import { useTranslation } from "../api/i18n";

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
  const { t } = useTranslation();
  const isLocked = target?.locked ?? false;
  const isLost = target?.status === "lost" || target?.lock_status === "lost";

  let statusBadgeClass = "unlocked";
  let statusBadgeText = t("targetStandby");
  if (isLocked) {
    if (isLost) {
      statusBadgeClass = "lost-badge";
      statusBadgeText = t("targetLost");
    } else {
      statusBadgeClass = "locked";
      statusBadgeText = t("targetLocked");
    }
  }

  return (
    <section className="panel target-lock-panel" style={isLocked && isLost ? { borderColor: "rgba(255, 120, 80, 0.28)" } : undefined}>
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{t("tacticalLocking")}</span>
          <h2>{t("targetControlHeading")}</h2>
        </div>
        <div className={`status-badge ${statusBadgeClass}`}>
          <Target size={14} className={isLocked && !isLost ? "pulse-lock" : ""} />
          <span>{statusBadgeText}</span>
        </div>
      </div>

      <div className="panel-body">
        {isLocked && target ? (
          <div className="target-card" style={isLost ? { borderColor: "rgba(255, 120, 80, 0.3)", background: "linear-gradient(145deg, rgba(255, 120, 80, 0.08), rgba(8, 13, 18, 0.8))" } : undefined}>
            <div className="target-item">
              <span className="label">{t("targetId")}</span>
              <strong className="value track-id-value" style={isLost ? { color: "#ff8c7a" } : undefined}>#{target.track_id}</strong>
            </div>
            <div className="target-item">
              <span className="label">{t("targetClass")}</span>
              <span className="value uppercase">{target.class_name || "Unknown"}</span>
            </div>
            <div className="target-item">
              <span className="label">{t("targetStatus")}</span>
              <span className={`mini-status ${isLost ? "lost" : "active"}`}>
                {isLost ? t("targetLost") : (target.status === "active" ? t("statusRunning") : target.status)}
              </span>
            </div>
          </div>
        ) : (
          <div className="empty-target">
            <p>{t("emptyTargetDesc")}</p>
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
            <span>{t("lockStrongest")}</span>
          </button>
          <button
            type="button"
            className="btn btn-secondary"
            onClick={onClearLock}
            disabled={!isLocked || loading}
          >
            <Unlock size={15} />
            <span>{t("clearLock")}</span>
          </button>
        </div>

        <div className="style-selector">
          <label>
            <Layers size={14} />
            <span>{t("hudStyleMode")}</span>
          </label>
          <div className="button-group">
            {["clean_hud", "tactical", "basic"].map((style) => (
              <button
                type="button"
                key={style}
                className={`btn-toggle ${hudStyle === style ? "active" : ""}`}
                onClick={() => onHudStyleChange(style)}
              >
                {style === "clean_hud" ? t("styleMinimal") : style === "tactical" ? t("styleTactical") : t("styleBasic")}
              </button>
            ))}
          </div>
        </div>
      </div>
    </section>
  );
}

export default TargetLockControlPanel;
