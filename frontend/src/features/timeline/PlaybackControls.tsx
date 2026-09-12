import { useAppState } from "../../shared/model/store";

export function formatTime(totalSeconds: number) {
  const secondsValue = Math.max(0, Math.round(totalSeconds));
  const hours = Math.floor(secondsValue / 3600);
  const minutes = Math.floor((secondsValue % 3600) / 60);
  const seconds = secondsValue % 60;
  return [hours, minutes, seconds]
    .map((value) => String(value).padStart(2, "0"))
    .join(":");
}

export function PlaybackControls() {
  const { playing, setPlaying, tS, setTS, scenario, timelineReady } = useAppState();
  const maximum = Math.max(0, scenario.horizonS - scenario.stepS);

  const step = (direction: -1 | 1) => {
    if (!timelineReady) return;
    const next = tS + scenario.stepS * direction;
    setTS(Math.min(Math.max(next, 0), maximum));
  };

  return (
    <div className="playback-controls">
      <div className="playback-transport">
        <button
          className="icon-button"
          type="button"
          disabled={!timelineReady}
          onClick={() => setPlaying(!playing)}
          aria-label={playing ? "Пауза" : "Воспроизвести"}
          title={!timelineReady ? "Сначала загрузите или пересчитайте модель" : undefined}
        >
          {playing ? "Ⅱ" : "▶"}
        </button>
        <button className="icon-button" type="button" disabled={!timelineReady} onClick={() => step(-1)} aria-label="Шаг назад">◀</button>
        <button className="icon-button" type="button" disabled={!timelineReady} onClick={() => step(1)} aria-label="Шаг вперёд">▶</button>
      </div>

      <div className="playback-time" title="Текущее модельное время">
        <span aria-hidden="true">▣</span>
        {formatTime(tS)}
        <small>(T+ {formatTime(tS)})</small>
      </div>
    </div>
  );
}
