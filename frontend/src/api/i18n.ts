import { useState, useEffect } from "react";

export type Language = "ru" | "en";

export const translations = {
  ru: {
    brandName: "SmartGuard AI",
    securityOperations: "Панель безопасности",
    serverOnline: "Сервер онлайн",
    serverOffline: "Сервер офлайн",
    visionWarning: "Ошибка модуля зрения",
    eventsWarning: "Ошибка журнала событий",
    activeObjectsCount: "{count} активных объектов",
    activeObjectsZero: "Нет активных объектов",
    workerRunning: "Анализ включён",
    workerStopped: "Анализ выключен",
    workerOffline: "Анализ остановлен",
    newEventsCount: "{count} новых событий",
    newEventsZero: "Нет событий",
    
    // Left panel
    cameraLiveView: "Камера",
    targetControl: "Сопровождение цели",
    workerManagement: "Управление анализом",
    zonesList: "Зоны",
    visionOverlay: "AI-мониторинг",

    
    // TargetLockControlPanel
    tacticalLocking: "Тактический захват",
    targetControlHeading: "Сопровождение цели",
    targetStandby: "ОЖИДАНИЕ",
    targetLocked: "ЦЕЛЬ ЗАХВАЧЕНА",
    targetLost: "ЦЕЛЬ ПОТЕРЯНА",
    targetId: "ИД Цели",
    targetClass: "Класс объекта",
    targetStatus: "Статус сопровождения",
    lockStrongest: "Захватить главную цель",
    clearLock: "Сбросить захват",
    hudStyleMode: "Визуальный стиль HUD",
    styleMinimal: "Минимум",
    styleTactical: "Тактический",
    styleBasic: "Базовый",
    emptyTargetDesc: "Нет активного сопровождения. Выберите объект на видео или захватите сильнейшую цель.",
    
    // WorkerControlPanel / CameraStatusCard
    workerControl: "Управление анализом",
    visionAPI: "Vision API статус",
    visionWorker: "Vision Worker статус",
    measuredFPS: "Измеренный FPS",
    lastUpdate: "Последнее обновление",
    updatesCount: "Всего обновлений",
    lastError: "Последняя ошибка",
    statusOnline: "Онлайн",
    statusOffline: "Офлайн",
    statusRunning: "Анализ запущен",
    statusStopped: "Анализ остановлен",
    btnStart: "Запустить анализ",
    btnStop: "Остановить анализ",
    btnRefresh: "Обновить статус",
    diagnosticsTitle: "Техническая диагностика",
    
    // Active Objects list
    activeObjectsTitle: "Активные объекты",
    noTrackedObjects: "Нет активных объектов",
    confidenceText: "уверенность",
    dwellText: "время присутствия",
    noZone: "вне зон",
    
    // Events Panel
    eventsTitle: "События безопасности",
    noEvents: "Нет зарегистрированных событий",
    btnAcknowledge: "Принять",
    btnIgnore: "Игнорировать",
    btnResolve: "Закрыть",
    filterAll: "Все",
    filterNew: "Новые",
    filterAccepted: "Принятые",
    filterClosed: "Закрытые",
    filterIgnored: "Игнорированные",
    btnClearTestEvents: "Очистить тестовые события",
    
    // Camera live view
    liveCamera: "Камера в реальном времени",
    channelLabel: "Канал {channel}",
    mjpegStream: "Видеопоток",
    annotatedFrame: "AI-кадр",
    
    // Language Switcher
    langToggle: "Язык: RU",
  },
  en: {
    brandName: "SmartGuard AI",
    securityOperations: "Security Operations",
    serverOnline: "Backend online",
    serverOffline: "Backend offline",
    visionWarning: "Vision API warning",
    eventsWarning: "Events API warning",
    activeObjectsCount: "{count} active objects",
    activeObjectsZero: "No active objects",
    workerRunning: "Worker running",
    workerStopped: "Worker stopped",
    workerOffline: "Worker offline",
    newEventsCount: "{count} new events",
    newEventsZero: "No new events",
    
    // Left panel
    cameraLiveView: "Live Camera View",
    targetControl: "Target Control",
    workerManagement: "Analysis Control",
    zonesList: "Configured Zones",
    visionOverlay: "Vision overlay",
    
    // TargetLockControlPanel
    tacticalLocking: "Tactical Locking",
    targetControlHeading: "Target Control",
    targetStandby: "STANDBY",
    targetLocked: "TARGET LOCKED",
    targetLost: "TARGET LOST",
    targetId: "Target ID",
    targetClass: "Classification",
    targetStatus: "Tracking Status",
    lockStrongest: "Lock Strongest Target",
    clearLock: "Clear Target Lock",
    hudStyleMode: "HUD Visual Style",
    styleMinimal: "Minimal",
    styleTactical: "Tactical",
    styleBasic: "Basic",
    emptyTargetDesc: "No active target lock. Select an object on the live view or click to lock strongest track.",
    
    // WorkerControlPanel / CameraStatusCard
    workerControl: "Analysis Control",
    visionAPI: "Vision API status",
    visionWorker: "Vision Worker status",
    measuredFPS: "Measured FPS",
    lastUpdate: "Last update",
    updatesCount: "Updates count",
    lastError: "Last error",
    statusOnline: "Online",
    statusOffline: "Offline",
    statusRunning: "Running",
    statusStopped: "Stopped",
    btnStart: "Start Analysis",
    btnStop: "Stop Analysis",
    btnRefresh: "Refresh Status",
    diagnosticsTitle: "Technical Diagnostics",
    
    // Active Objects list
    activeObjectsTitle: "Active Objects",
    noTrackedObjects: "No tracked objects",
    confidenceText: "confidence",
    dwellText: "dwell time",
    noZone: "no zone",
    
    // Events Panel
    eventsTitle: "Security Events",
    noEvents: "No registered events",
    btnAcknowledge: "Acknowledge",
    btnIgnore: "Ignore",
    btnResolve: "Resolve",
    filterAll: "All",
    filterNew: "New",
    filterAccepted: "Accepted",
    filterClosed: "Closed",
    filterIgnored: "Ignored",
    btnClearTestEvents: "Clear Test Events",
    
    // Camera live view
    liveCamera: "Live Camera",
    channelLabel: "Channel {channel}",
    mjpegStream: "MJPEG Stream",
    annotatedFrame: "Annotated frame",
    
    // Language Switcher
    langToggle: "Language: EN",
  }
};

export function useTranslation() {
  const [lang, setLang] = useState<Language>(() => {
    const saved = localStorage.getItem("smartguard_lang");
    return (saved === "en" || saved === "ru") ? saved : "ru";
  });

  const changeLanguage = (newLang: Language) => {
    setLang(newLang);
    localStorage.setItem("smartguard_lang", newLang);
  };

  const t = (key: keyof typeof translations["ru"], params?: Record<string, string | number>): string => {
    let text = translations[lang][key] || translations["ru"][key] || String(key);
    if (params) {
      Object.entries(params).forEach(([k, v]) => {
        text = text.replace(`{${k}}`, String(v));
      });
    }
    return text;
  };

  return { t, lang, setLang: changeLanguage };
}
