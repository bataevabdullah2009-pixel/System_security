import { Check, EyeOff, RotateCcw } from "lucide-react";

import { EventActionStatus, SecurityEvent } from "../api/client";

interface EventsPanelProps {
  events: SecurityEvent[];
  statusError: string | null;
  loadingAction: string | null;
  onStatusChange: (eventId: number, status: EventActionStatus) => void;
}

const statusLabels: Record<string, string> = {
  new: "New",
  acknowledged: "Acknowledged",
  ignored: "Ignored",
  resolved: "Resolved",
};

function EventsPanel({
  events,
  statusError,
  loadingAction,
  onStatusChange,
}: EventsPanelProps) {
  return (
    <section className="panel events-panel">
      <div className="panel-heading">
        <div>
          <span className="eyebrow">Event queue</span>
          <h2>Security events</h2>
        </div>
        <div className="count-pill">{events.length}</div>
      </div>

      <div className="event-list">
        {statusError ? (
          <div className="inline-warning">{statusError}</div>
        ) : null}
        {events.length === 0 ? (
          <div className="empty-state">No events</div>
        ) : (
          events.map((event) => (
            <article className="event-card" key={event.id}>
              <div className="event-card-top">
                <span className={`event-status status-${event.status}`}>
                  {statusLabels[event.status] ?? event.status}
                </span>
                <time>{formatDateTime(event.created_at)}</time>
              </div>
              <h3>{event.title}</h3>
              <p>{event.description}</p>
              <div className="event-meta">
                <span>Channel {event.channel}</span>
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
                  title="Acknowledge event"
                >
                  <Check size={15} />
                  <span>Acknowledge</span>
                </button>
                <button
                  type="button"
                  disabled={isLoading(loadingAction, event.id, "ignored")}
                  onClick={() => onStatusChange(event.id, "ignored")}
                  title="Ignore event"
                >
                  <EyeOff size={15} />
                  <span>Ignore</span>
                </button>
                <button
                  type="button"
                  disabled={isLoading(loadingAction, event.id, "resolved")}
                  onClick={() => onStatusChange(event.id, "resolved")}
                  title="Resolve event"
                >
                  <RotateCcw size={15} />
                  <span>Resolve</span>
                </button>
              </div>
            </article>
          ))
        )}
      </div>
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
  return new Intl.DateTimeFormat(undefined, {
    month: "short",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
  }).format(new Date(value));
}

export default EventsPanel;
