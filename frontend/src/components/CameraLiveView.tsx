import { useMemo, useState } from "react";
import { Camera, PauseCircle, PlayCircle } from "lucide-react";

import {
  VisionWorkerStatus,
  getAnnotatedFrameUrl,
  getVisionStreamUrl,
} from "../api/client";
import { useTranslation } from "../api/i18n";

interface CameraLiveViewProps {
  channel: string;
  workerStatus: VisionWorkerStatus;
  onVideoClick?: (x: number, y: number) => void;
}

function CameraLiveView({ channel, workerStatus, onVideoClick }: CameraLiveViewProps) {
  const { t } = useTranslation();
  const [useFallbackFrame, setUseFallbackFrame] = useState(false);
  const [fallbackKey, setFallbackKey] = useState(0);
  
  const imageUrl = useMemo(() => {
    if (useFallbackFrame) {
      return `${getAnnotatedFrameUrl(channel)}?t=${fallbackKey}`;
    }
    return getVisionStreamUrl(channel);
  }, [channel, fallbackKey, useFallbackFrame]);

  const handleImageClick = (event: React.MouseEvent<HTMLImageElement>) => {
    const img = event.currentTarget;
    const rect = img.getBoundingClientRect();
    const xClick = event.clientX - rect.left;
    const yClick = event.clientY - rect.top;
    
    // Scale browser coordinates to natural image dimensions
    const scaleX = img.naturalWidth / rect.width;
    const scaleY = img.naturalHeight / rect.height;
    
    const xOrig = Math.round(xClick * scaleX);
    const yOrig = Math.round(yClick * scaleY);
    
    if (onVideoClick) {
      onVideoClick(xOrig, yOrig);
    }
  };

  return (
    <section className="panel live-panel">
      <div className="panel-heading live-heading">
        <div>
          <span className="eyebrow">{t("liveCamera")}</span>
          <h2>{t("channelLabel", { channel })}</h2>
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
          <span>{workerStatus.running ? t("workerRunning") : t("workerOffline")}</span>
        </div>
      </div>

      <div className="video-frame">
        <img
          key={imageUrl}
          src={imageUrl}
          alt={`Channel ${channel} live security view`}
          style={{ cursor: "crosshair" }}
          onClick={handleImageClick}
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
          <span>{useFallbackFrame ? t("annotatedFrame") : t("mjpegStream")}</span>
        </div>
      </div>
    </section>
  );
}


export default CameraLiveView;
