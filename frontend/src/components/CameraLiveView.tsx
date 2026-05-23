import { useMemo, useState } from "react";
import { Camera, PauseCircle, PlayCircle } from "lucide-react";

import {
  VisionWorkerStatus,
  getAnnotatedFrameUrl,
  getVisionStreamUrl,
} from "../api/client";

interface CameraLiveViewProps {
  channel: string;
  workerStatus: VisionWorkerStatus;
}

function CameraLiveView({ channel, workerStatus }: CameraLiveViewProps) {
  const [useFallbackFrame, setUseFallbackFrame] = useState(false);
  const [fallbackKey, setFallbackKey] = useState(0);
  const imageUrl = useMemo(() => {
    if (useFallbackFrame) {
      return `${getAnnotatedFrameUrl(channel)}?t=${fallbackKey}`;
    }
    return getVisionStreamUrl(channel);
  }, [channel, fallbackKey, useFallbackFrame]);

  return (
    <section className="panel live-panel">
      <div className="panel-heading live-heading">
        <div>
          <span className="eyebrow">Live camera</span>
          <h2>Channel {channel}</h2>
        </div>
        <div
          className={`live-state ${
            workerStatus.running ? "state-running" : "state-offline"
          }`}
        >
          {workerStatus.running ? (
            <PlayCircle size={16} />
          ) : (
            <PauseCircle size={16} />
          )}
          <span>{workerStatus.running ? "Worker running" : "Worker offline"}</span>
        </div>
      </div>

      <div className="video-frame">
        <img
          key={imageUrl}
          src={imageUrl}
          alt={`Channel ${channel} live security view`}
          onError={() => {
            if (!useFallbackFrame) {
              setUseFallbackFrame(true);
              return;
            }
            setFallbackKey((current) => current + 1);
          }}
        />
        <div className="video-hud">
          <span>
            <Camera size={14} />
            Hikvision {channel}
          </span>
          <span>{useFallbackFrame ? "Annotated frame" : "MJPEG stream"}</span>
        </div>
      </div>
    </section>
  );
}

export default CameraLiveView;
