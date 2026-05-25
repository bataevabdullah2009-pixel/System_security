import { useState, useMemo } from "react";
import { Check, EyeOff, RotateCcw, Trash2 } from "lucide-react";

import { EventActionStatus, SecurityEvent } from "../api/client";
import { useTranslation } from "../api/i18n";

interface EventsPanelProps {
  events: SecurityEvent[];
  statusError: string | null;
  loadingAction: string | null;
  onStatusChange: (eventId: number, status: EventActionStatus) => void;
  onClearEvents?: () => Promise<void>;
}

function EventsPanel({
  events,
  statusError,
  loadingAction,
  onStatusChange,
  onClearEvents,
}: EventsPanelProps) {
  const { t } = useTranslation();
  const [filter, setFilter] = useState<"all" | "new" | "acknowledged" | "resolved" | "ignored">("all");
  const [loadingClear, setLoadingClear] = useState(false);

  const filteredEvents = useMemo(() => {
    let list = events;
    if (filter !== "all") {
      list = events.filter((e) => e.status === filter);
    }
    // Sort descending (newest first)
    const sorted = [...list].sort(
      (a, b) => new Date(b.created_at).getTime() - new Date(a.created_at).getTime()
    );
    // Cap at 20 items
    return sorted.slice(0, 20);
  }, [events, filter]);

  const handleClear = async () => {
    if (!onClearEvents) return;
    setLoadingClear(true);
    try {
      await onClearEvents();
    } catch (err) {
      console.error("Failed to clear events:", err);
    } finally {
      setLoadingClear(false);
    }
  };

  const getStatusLabel = (status: string) => {
    switch (status) {
      case "new":
        return t("filterNew");
      case "acknowledged":
        return t("filterAccepted");
      case "resolved":
        return t("filterClosed");
      case "ignored":
        return t("filterIgnored");
      default:
        return status;
    }
  };

  return (
    <section className="panel events-panel" style={{ display: "flex", flexDirection: "column", height: "100%" }}>
      <div className="panel-heading" style={{ flexShrink: 0 }}>
        <div>
          <span className="eyebrow">{t("eventsTitle")}</span>
          <h2>{t("eventsTitle")}</h2>
        </div>
        <div className="count-pill">{events.filter(e => e.status === "new").length}</div>
      </div>

      {/* Filter Tabs */}
      <div className="filter-tabs" style={{ display: "flex", gap: "6px", padding: "8px 12px", borderBottom: "1px solid rgba(157, 180, 190, 0.08)", overflowX: "auto", flexShrink: 0 }}>
        {(["all", "new", "acknowledged", "resolved", "ignored"] as const).map((f) => (
          <button
            key={f}
            type="button"
            onClick={() => setFilter(f)}
            style={{
              padding: "4px 8px",
              borderRadius: "4px",
              border: "1px solid",
              borderColor: filter === f ? "rgba(80, 220, 50, 0.3)" : "rgba(157, 180, 190, 0.12)",
              background: filter === f ? "rgba(80, 220, 50, 0.08)" : "transparent",
              color: filter === f ? "#50dc32" : "#8fa7b0",
              fontSize: "0.75rem",
              fontWeight: 700,
              cursor: "pointer",
              whiteSpace: "nowrap",
              transition: "all 0.15s ease"
            }}
          >
            {f === "all" ? t("filterAll") : f === "new" ? t("filterNew") : f === "acknowledged" ? t("filterAccepted") : f === "resolved" ? t("filterClosed") : t("filterIgnored")}
          </button>
        ))}
      </div>

      <div className="event-list" style={{ flexGrow: 1, overflowY: "auto", minHeight: 0 }}>
        {statusError ? (
          <div className="inline-warning">{statusError}</div>
        ) : null}
        {filteredEvents.length === 0 ? (
          <div className="empty-state">{t("noEvents")}</div>
        ) : (
          filteredEvents.map((event) => (
            <article className="event-card" key={event.id}>
              <div className="event-card-top">
                <span className={`event-status status-${event.status}`}>
                  {getStatusLabel(event.status)}
                </span>
                <time>{formatDateTime(event.created_at)}</time>
              </div>
              <h3>{event.title}</h3>
              <p>{event.description}</p>
              <div className="event-meta">
                <span>{t("channelLabel", { channel: event.channel })}</span>
                <span>{event.event_type}</span>
                <span>
                  {event.confidence === null
                    ? "confidence n/a"
                    : `${Math.round(event.confidence * 100)}%`}
                </span>
              </div>
              <div className="event-actions">
                <button
                  type="button"
                  disabled={isLoading(loadingAction, event.id, "acknowledged")}
                  onClick={() => onStatusChange(event.id, "acknowledged")}
                  title={t("btnAcknowledge")}
                >
                  <Check size={15} />
                  <span>{t("btnAcknowledge")}</span>
                </button>
                <button
                  type="button"
                  disabled={isLoading(loadingAction, event.id, "ignored")}
                  onClick={() => onStatusChange(event.id, "ignored")}
                  title={t("btnIgnore")}
                >
                  <EyeOff size={15} />
                  <span>{t("btnIgnore")}</span>
                </button>
                <button
                  type="button"
                  disabled={isLoading(loadingAction, event.id, "resolved")}
                  onClick={() => onStatusChange(event.id, "resolved")}
                  title={t("btnResolve")}
                >
                  <RotateCcw size={15} />
                  <span>{t("btnResolve")}</span>
                </button>
              </div>
            </article>
          ))
        )}
      </div>

      {/* Clear Test Events Button */}
      {onClearEvents && (
        <div style={{ padding: "10px 14px", borderTop: "1px solid rgba(157, 180, 190, 0.08)", display: "flex", justifyContent: "flex-end", flexShrink: 0 }}>
          <button
            type="button"
            onClick={handleClear}
            disabled={loadingClear}
            style={{
              display: "flex",
              alignItems: "center",
              gap: "6px",
              padding: "6px 12px",
              borderRadius: "4px",
              border: "1px solid rgba(255, 120, 80, 0.2)",
              background: "rgba(255, 120, 80, 0.05)",
              color: "#ff7850",
              fontSize: "0.78rem",
              fontWeight: 700,
              cursor: "pointer",
              transition: "all 0.15s ease"
            }}
          >
            <Trash2 size={14} />
            <span>{loadingClear ? "..." : t("btnClearTestEvents")}</span>
          </button>
        </div>
      )}
    </section>
  );
}

function isLoading(
  loadingAction: string | null,
  eventId: number,
  status: EventActionStatus,
): boolean {
  return loadingAction === `event-${eventId}-${status}`;
}

function formatDateTime(value: string): string {
  try {
    return new Intl.DateTimeFormat(undefined, {
      month: "short",
      day: "2-digit",
      hour: "2-digit",
      minute: "2-digit",
    }).format(new Date(value));
  } catch {
    return value;
  }
}

export default EventsPanel;
