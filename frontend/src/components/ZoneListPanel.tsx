import { MapPinned } from "lucide-react";

import { TrackedObject } from "../api/client";

interface ZoneListPanelProps {
  objects: TrackedObject[];
}

interface ZoneSummary {
  id: string;
  activeCount: number;
  maxDwellSeconds: number;
}

function ZoneListPanel({ objects }: ZoneListPanelProps) {
  const zones = buildZoneSummary(objects);

  return (
    <section className="panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Zones</span>
          <h2>Observed zones</h2>
        </div>
        <MapPinned size={18} />
      </div>

      <div className="zone-list">
        {zones.length === 0 ? (
          <div className="empty-state">No zone activity</div>
        ) : (
          zones.map((zone) => (
            <div className="zone-row" key={zone.id}>
              <div>
                <strong>{zone.id}</strong>
                <span>{zone.activeCount} active tracks</span>
              </div>
              <span>{zone.maxDwellSeconds.toFixed(1)}s</span>
            </div>
          ))
        )}
      </div>
    </section>
  );
}

function buildZoneSummary(objects: TrackedObject[]): ZoneSummary[] {
  const zones = new Map<string, ZoneSummary>();
  for (const object of objects) {
    for (const zoneId of object.zone_ids) {
      const summary =
        zones.get(zoneId) ??
        zones
          .set(zoneId, {
            id: zoneId,
            activeCount: 0,
            maxDwellSeconds: 0,
          })
          .get(zoneId);
      if (!summary) {
        continue;
      }
      if (object.status === "active") {
        summary.activeCount += 1;
      }
      summary.maxDwellSeconds = Math.max(
        summary.maxDwellSeconds,
        object.dwell?.[zoneId] ?? 0,
      );
    }
  }
  return Array.from(zones.values()).sort((first, second) =>
    first.id.localeCompare(second.id),
  );
}

export default ZoneListPanel;
