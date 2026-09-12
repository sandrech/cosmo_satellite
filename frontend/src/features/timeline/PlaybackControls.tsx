import { useAppState } from "../../shared/model/store";

export function formatTime(totalSeconds: number) {
  const hours = Math.floor(totalSeconds / 3600);
  const minutes = Math.floor((totalSeconds % 3600) / 60);
  const seconds = totalSeconds % 60;
  return [hours, minutes, seconds]
    .map((value) => String(value).padStart(2, "0"))
    .join(":");
}

export function PlaybackControls() {
  const { modelRun, playing, setPlaying, tS, setTS, scenario } = useAppState();
  const disabled = !modelRun;

  const step = (direction: -1 | 1) => {
    if (disabled) return;
    const next = tS + scenario.stepS * direction;
    setTS(Math.min(Math.max(next, 0), scenario.horizonS - scenario.stepS));
  };

  return (
    <div className="playback-controls">
      <div className="playback-transport">
        <button className="icon-button" type="button" disabled={disabled} onClick={() => setPlaying(!playing)} aria-label={playing ? "Пауза" : "Воспроизвести"} title={disabled ? "Сначала выполните полный расчёт модели" : undefined}>
          {playing ? "Ⅱ" : "▶"}
        </button>
        <button className="icon-button" type="button" disabled={disabled} onClick={() => step(-1)} aria-label="Шаг назад">◀</button>
        <button className="icon-button" type="button" disabled={disabled} onClick={() => step(1)} aria-label="Шаг вперёд">▶</button>
      </div>

      <button className="playback-time" type="button" title="Текущее модельное время">
        <span aria-hidden="true">▣</span>
        {formatTime(tS)}
        <small>(T+ {formatTime(tS)})</small>
        <span aria-hidden="true">⌄</span>
      </button>
    </div>
  );
}
