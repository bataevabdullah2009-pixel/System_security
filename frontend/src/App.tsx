import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, RadioTower, ShieldCheck, Camera } from "lucide-react";

import {
  EventActionStatus,
  SecurityEvent,
  VisionState,
  VisionWorkerStatus,
  getEvents,
  getHealth,
  getVisionState,
  getVisionWorkerStatus,
  startVisionWorker,
  stopVisionWorker,
  updateEventStatus,
  lockTarget,
  lockTargetByCoordinates,
  clearTarget,
  setHudStyle as apiSetHudStyle,
  clearEvents,
} from "./api/client";
import CameraLiveView from "./components/CameraLiveView";
import CameraStatusCard from "./components/CameraStatusCard";
import EventsPanel from "./components/EventsPanel";
import Layout from "./components/Layout";
import VisionOverlayPanel from "./components/VisionOverlayPanel";
import WorkerControlPanel from "./components/WorkerControlPanel";
import ZoneListPanel from "./components/ZoneListPanel";
import TargetLockControlPanel from "./components/TargetLockControlPanel";
import { useTranslation } from "./api/i18n";



const CHANNEL = "101";

function App() {
  const { t, lang, setLang } = useTranslation();
  const [visionState, setVisionState] = useState<VisionState | null>(null);
  const [workerStatus, setWorkerStatus] = useState<VisionWorkerStatus | null>(
    null,
  );
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [backendHealthError, setBackendHealthError] = useState<string | null>(
    null,
  );
  const [visionStateError, setVisionStateError] = useState<string | null>(null);
  const [workerStatusError, setWorkerStatusError] = useState<string | null>(
    null,
  );
  const [eventsError, setEventsError] = useState<string | null>(null);
  const [hudStyle, setHudStyle] = useState<string>("clean_hud");

  const refreshDashboard = useCallback(async () => {
    const [healthResult, stateResult, workerResult, eventsResult] =
      await Promise.allSettled([
        getHealth(),
        getVisionState(CHANNEL),
        getVisionWorkerStatus(CHANNEL),
        getEvents(),
      ]);

    setBackendHealthError(
      healthResult.status === "fulfilled"
        ? null
        : formatDashboardError("Backend unavailable", healthResult.reason),
    );

    if (stateResult.status === "fulfilled") {
      setVisionState(stateResult.value);
      setVisionStateError(null);
    } else {
      setVisionStateError(
        formatDashboardError("Vision API unavailable", stateResult.reason),
      );
    }

    if (workerResult.status === "fulfilled") {
      setWorkerStatus(workerResult.value);
      setWorkerStatusError(null);
    } else {
      setWorkerStatusError(
        formatDashboardError("Worker status unavailable", workerResult.reason),
      );
    }

    if (eventsResult.status === "fulfilled") {
      setEvents(eventsResult.value);
      setEventsError(null);
    } else {
      setEventsError(
        formatDashboardError("Events API unavailable", eventsResult.reason),
      );
    }
  }, []);

  useEffect(() => {
    refreshDashboard();
    const intervalId = window.setInterval(refreshDashboard, 1000);
    return () => window.clearInterval(intervalId);
  }, [refreshDashboard]);

  const runWorkerAction = async (action: "start" | "stop" | "refresh") => {
    setLoadingAction(action);
    try {
      if (action === "start") {
        setWorkerStatus(await startVisionWorker(CHANNEL));
        setWorkerStatusError(null);
      }
      if (action === "stop") {
        setWorkerStatus(await stopVisionWorker(CHANNEL));
        setWorkerStatusError(null);
      }
      await refreshDashboard();
    } catch (error) {
      setWorkerStatusError(
        formatDashboardError("Worker control unavailable", error),
      );
    } finally {
      setLoadingAction(null);
    }
  };

  const handleEventStatus = async (
    eventId: number,
    status: EventActionStatus,
  ) => {
    setLoadingAction(`event-${eventId}-${status}`);
    try {
      const updatedEvent = await updateEventStatus(eventId, status);
      setEvents((currentEvents) =>
        currentEvents.map((event) =>
          event.id === updatedEvent.id ? updatedEvent : event,
        ),
      );
      setEventsError(null);
    } catch (error) {
      setEventsError(formatDashboardError("Events API unavailable", error));
    } finally {
      setLoadingAction(null);
    }
  };

  const handleLockStrongestTarget = async () => {
    setLoadingAction("lock-strongest");
    try {
      if (visionState && visionState.objects.length > 0) {
        const sorted = [...visionState.objects]
          .filter((o) => o.status === "active")
          .sort((a, b) => b.confidence - a.confidence);
        if (sorted.length > 0) {
          const strongest = sorted[0];
          const updatedTarget = await lockTarget(CHANNEL, strongest.track_id);
          setVisionState((prev) => prev ? { ...prev, target: updatedTarget } : null);
        }
      }
    } catch (error) {
      console.error("Lock strongest failed:", error);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleClearTargetLock = async () => {
    setLoadingAction("clear-lock");
    try {
      const updatedTarget = await clearTarget(CHANNEL);
      setVisionState((prev) => prev ? { ...prev, target: updatedTarget } : null);
    } catch (error) {
      console.error("Clear target failed:", error);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleVideoClick = async (x: number, y: number) => {
    setLoadingAction("lock-coordinates");
    try {
      const updatedTarget = await lockTargetByCoordinates(CHANNEL, x, y);
      setVisionState((prev) => prev ? { ...prev, target: updatedTarget } : null);
      await refreshDashboard();
    } catch (error) {
      console.error("Coordinate lock failed:", error);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleHudStyleChange = async (style: string) => {
    setLoadingAction("hud-style");
    try {
      await apiSetHudStyle(CHANNEL, style);
      setHudStyle(style);
      await refreshDashboard();
    } catch (error) {
      console.error("HUD style change failed:", error);
    } finally {
      setLoadingAction(null);
    }
  };

  const handleClearEvents = async () => {
    try {
      await clearEvents();
      setEvents([]);
      await refreshDashboard();
    } catch (error) {
      setEventsError(formatDashboardError("Clear events failed", error));
    }
  };

  const mergedWorkerStatus = useMemo<VisionWorkerStatus>(() => {
    const stateWorker = visionState?.worker ?? {};
    return {
      channel: CHANNEL,
      running: Boolean(workerStatus?.running ?? stateWorker.running),
      interval_seconds: workerStatus?.interval_seconds,
      last_update_at:
        workerStatus?.last_update_at ??
        (typeof stateWorker.last_update_at === "string"
          ? stateWorker.last_update_at
          : null),
      last_error:
        workerStatus?.last_error ??
        (typeof stateWorker.last_error === "string"
          ? stateWorker.last_error
          : null),
      updates_count: Number(
        workerStatus?.updates_count ?? stateWorker.updates_count ?? 0,
      ),
    };
  }, [visionState, workerStatus]);

  const activeObjects =
    visionState?.objects.filter((object) => object.status === "active") ?? [];
  const newEvents = events.filter((event) => event.status === "new").length;
  const backendOnline = backendHealthError === null;
  const statusWarnings = [
    visionStateError,
    eventsError,
    workerStatusError,
  ].filter(Boolean);

  return (
    <Layout
      header={
        <header className="topbar">
          <div className="brand-lockup">
            <div className="brand-mark">
              <ShieldCheck size={21} strokeWidth={2.2} />
            </div>
            <div>
              <span className="eyebrow">{t("brandName")}</span>
              <h1>{t("securityOperations")}</h1>
            </div>
          </div>
          <div className="system-strip">
            <div className="status-chip">
              <RadioTower size={16} />
              <span>{backendOnline ? t("serverOnline") : t("serverOffline")}</span>
            </div>
            {visionStateError ? (
              <div className="status-chip status-chip-warning">
                <AlertTriangle size={16} />
                <span>{t("visionWarning")}</span>
              </div>
            ) : null}
            {eventsError ? (
              <div className="status-chip status-chip-warning">
                <AlertTriangle size={16} />
                <span>{t("eventsWarning")}</span>
              </div>
            ) : null}
            <div className="status-chip">
              <Camera size={16} />
              <span>
                {t("channelLabel", { channel: CHANNEL })} ({backendOnline && visionState?.updated_at ? t("statusOnline") : t("statusOffline")})
              </span>
            </div>
            <div className="status-chip">
              <Activity size={16} />
              <span>
                {activeObjects.length > 0
                  ? t("activeObjectsCount", { count: activeObjects.length })
                  : t("activeObjectsZero")}
              </span>
            </div>
            <div className="status-chip status-chip-alert">
              <AlertTriangle size={16} />
              <span>
                {newEvents > 0
                  ? t("newEventsCount", { count: newEvents })
                  : t("newEventsZero")}
              </span>
            </div>
            <button
              onClick={() => setLang(lang === "ru" ? "en" : "ru")}
              className="btn-toggle lang-switcher-btn"
              style={{
                background: "rgba(143, 167, 176, 0.08)",
                border: "1px solid rgba(143, 167, 176, 0.2)",
                color: "#c3d1d6",
                padding: "4px 8px",
                borderRadius: "4px",
                fontSize: "0.75rem",
                fontWeight: "bold",
                cursor: "pointer",
                marginLeft: "12px",
                textTransform: "uppercase"
              }}
            >
              {lang === "ru" ? "EN" : "RU"}
            </button>
          </div>
        </header>
      }
      left={
        <>
          <CameraStatusCard
            channel={CHANNEL}
            state={visionState}
            workerStatus={mergedWorkerStatus}
            backendOnline={backendOnline}
          />
          <TargetLockControlPanel
            target={visionState?.target ?? null}
            loading={loadingAction !== null}
            hudStyle={hudStyle}
            onLockStrongest={handleLockStrongestTarget}
            onClearLock={handleClearTargetLock}
            onHudStyleChange={handleHudStyleChange}
          />
          <WorkerControlPanel
            status={mergedWorkerStatus}
            statusError={workerStatusError}
            loadingAction={loadingAction}
            onStart={() => runWorkerAction("start")}
            onStop={() => runWorkerAction("stop")}
            onRefresh={() => runWorkerAction("refresh")}
          />
          <ZoneListPanel objects={visionState?.objects ?? []} />
        </>
      }
      center={
        <>
          <CameraLiveView
            channel={CHANNEL}
            workerStatus={mergedWorkerStatus}
            onVideoClick={handleVideoClick}
          />
          <VisionOverlayPanel
            objects={visionState?.objects ?? []}
            statusError={visionStateError}
          />
        </>
      }
      right={
        <EventsPanel
          events={events}
          statusError={eventsError}
          loadingAction={loadingAction}
          onStatusChange={handleEventStatus}
          onClearEvents={handleClearEvents}
        />
      }
      footer={
        statusWarnings.length ? (
          <div className="status-banner">{statusWarnings.join(" · ")}</div>
        ) : undefined
      }
    />
  );
}

function formatDashboardError(label: string, error: unknown): string {
  if (error instanceof Error) {
    return `${label}: ${error.message}`;
  }
  return `${label}: ${String(error)}`;
}

export default App;
