import { Crosshair, Route } from "lucide-react";

import { TrackedObject } from "../api/client";
import { useTranslation } from "../api/i18n";

interface VisionOverlayPanelProps {
  objects: TrackedObject[];
  statusError: string | null;
}

function VisionOverlayPanel({ objects, statusError }: VisionOverlayPanelProps) {
  const { t } = useTranslation();

  return (
    <section className="panel overlay-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">{t("visionOverlay")}</span>
          <h2>{t("activeObjectsTitle")}</h2>
        </div>
        <div className="count-pill">{objects.length}</div>
      </div>

      <div className="object-list">
        {statusError ? (
          <div className="inline-warning">{statusError}</div>
        ) : null}
        {objects.length === 0 ? (
          <div className="empty-state">{t("noTrackedObjects")}</div>
        ) : (
          objects.map((object) => {
            const dwellSeconds = Math.max(
              0,
              ...Object.values(object.dwell ?? {}),
            );
            return (
              <article className="object-row" key={object.track_id}>
                <div className="object-main">
                  <div className="track-badge">#{object.track_id}</div>
                  <div>
                    <strong className="uppercase">{object.class_name}</strong>
                    <span>{t("confidenceText")}: {Math.round(object.confidence * 100)}%</span>
                  </div>
                </div>
                <div className="object-meta">
                  <span>
                    <Crosshair size={14} />
                    {object.zone_ids.length ? object.zone_ids.join(", ") : t("noZone")}
                  </span>
                  <span>
                    <Route size={14} />
                    {t("dwellText")}: {dwellSeconds.toFixed(1)}s
                  </span>
                  <span className={`mini-status ${object.status}`}>
                    {object.status === "active" ? t("statusOnline") : object.status}
                  </span>
                </div>
              </article>
            );
          })
        )}
      </div>
    </section>
  );
}

export default VisionOverlayPanel;
