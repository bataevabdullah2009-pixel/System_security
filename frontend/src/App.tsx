import { useCallback, useEffect, useMemo, useState } from "react";
import { Activity, AlertTriangle, RadioTower, ShieldCheck } from "lucide-react";

import {
  EventActionStatus,
  SecurityEvent,
  VisionState,
  VisionWorkerStatus,
  getEvents,
  getVisionState,
  getVisionWorkerStatus,
  startVisionWorker,
  stopVisionWorker,
  updateEventStatus,
} from "./api/client";
import CameraLiveView from "./components/CameraLiveView";
import CameraStatusCard from "./components/CameraStatusCard";
import EventsPanel from "./components/EventsPanel";
import Layout from "./components/Layout";
import VisionOverlayPanel from "./components/VisionOverlayPanel";
import WorkerControlPanel from "./components/WorkerControlPanel";
import ZoneListPanel from "./components/ZoneListPanel";

const CHANNEL = "101";

function App() {
  const [visionState, setVisionState] = useState<VisionState | null>(null);
  const [workerStatus, setWorkerStatus] = useState<VisionWorkerStatus | null>(
    null,
  );
  const [events, setEvents] = useState<SecurityEvent[]>([]);
  const [loadingAction, setLoadingAction] = useState<string | null>(null);
  const [lastError, setLastError] = useState<string | null>(null);

  const refreshDashboard = useCallback(async () => {
    try {
      const [stateResult, workerResult, eventsResult] = await Promise.all([
        getVisionState(CHANNEL),
        getVisionWorkerStatus(CHANNEL),
        getEvents(),
      ]);
      setVisionState(stateResult);
      setWorkerStatus(workerResult);
      setEvents(eventsResult);
      setLastError(null);
    } catch (error) {
      setLastError(error instanceof Error ? error.message : String(error));
    }
  }, []);

  useEffect(() => {
    refreshDashboard();
    const intervalId = window.setInterval(refreshDashboard, 3000);
    return () => window.clearInterval(intervalId);
  }, [refreshDashboard]);

  const runWorkerAction = async (action: "start" | "stop" | "refresh") => {
    setLoadingAction(action);
    try {
      if (action === "start") {
        setWorkerStatus(await startVisionWorker(CHANNEL));
      }
      if (action === "stop") {
        setWorkerStatus(await stopVisionWorker(CHANNEL));
      }
      await refreshDashboard();
    } catch (error) {
      setLastError(error instanceof Error ? error.message : String(error));
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
      setLastError(null);
    } catch (error) {
      setLastError(error instanceof Error ? error.message : String(error));
    } finally {
      setLoadingAction(null);
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
  const backendOnline = lastError === null;

  return (
    <Layout
      header={
        <header className="topbar">
          <div className="brand-lockup">
            <div className="brand-mark">
              <ShieldCheck size={21} strokeWidth={2.2} />
            </div>
            <div>
              <span className="eyebrow">SmartGuard AI</span>
              <h1>Security Operations</h1>
            </div>
          </div>
          <div className="system-strip">
            <div className="status-chip">
              <RadioTower size={16} />
              <span>{backendOnline ? "Backend online" : "Backend offline"}</span>
            </div>
            <div className="status-chip">
              <Activity size={16} />
              <span>{activeObjects.length} active objects</span>
            </div>
            <div className="status-chip status-chip-alert">
              <AlertTriangle size={16} />
              <span>{newEvents} new events</span>
            </div>
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
          <WorkerControlPanel
            status={mergedWorkerStatus}
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
          <CameraLiveView channel={CHANNEL} workerStatus={mergedWorkerStatus} />
          <VisionOverlayPanel objects={visionState?.objects ?? []} />
        </>
      }
      right={
        <EventsPanel
          events={events}
          loadingAction={loadingAction}
          onStatusChange={handleEventStatus}
        />
      }
      footer={
        lastError ? <div className="error-banner">{lastError}</div> : undefined
      }
    />
  );
}

export default App;
