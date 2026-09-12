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
  const { playing, setPlaying, tS, scenario } = useAppState();
  return (
    <div className="playback-controls">
      <button
        className="icon-button"
        onClick={() => setPlaying(!playing)}
        aria-label={playing ? "Пауза" : "Воспроизвести"}
      >
        {playing ? "Ⅱ" : "▶"}
      </button>
      <strong>Таймлайн</strong>
      <span>{formatTime(tS)} / 24:00:00</span>
      <span className="muted">шаг {scenario.stepS} с</span>
    </div>
  );
}
