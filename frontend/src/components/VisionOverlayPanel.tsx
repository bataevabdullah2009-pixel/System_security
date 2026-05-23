import { Crosshair, Route } from "lucide-react";

import { TrackedObject } from "../api/client";

interface VisionOverlayPanelProps {
  objects: TrackedObject[];
  statusError: string | null;
}

function VisionOverlayPanel({ objects, statusError }: VisionOverlayPanelProps) {
  return (
    <section className="panel overlay-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Vision overlay</span>
          <h2>Active objects</h2>
        </div>
        <div className="count-pill">{objects.length}</div>
      </div>

      <div className="object-list">
        {statusError ? (
          <div className="inline-warning">{statusError}</div>
        ) : null}
        {objects.length === 0 ? (
          <div className="empty-state">No tracked objects</div>
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
                    <strong>{object.class_name}</strong>
                    <span>{Math.round(object.confidence * 100)}% confidence</span>
                  </div>
                </div>
                <div className="object-meta">
                  <span>
                    <Crosshair size={14} />
                    {object.zone_ids.length ? object.zone_ids.join(", ") : "no zone"}
                  </span>
                  <span>
                    <Route size={14} />
                    {dwellSeconds.toFixed(1)}s dwell
                  </span>
                  <span className={`mini-status ${object.status}`}>
                    {object.status}
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
