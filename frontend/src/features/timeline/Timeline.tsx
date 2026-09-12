import type { CSSProperties } from "react";
import { useAppState } from "../../shared/model/store";
import { formatTime, PlaybackControls } from "./PlaybackControls";

const SPEEDS = [1, 5, 20, 60] as const;

function scaleLabel(totalSeconds: number) {
  const [hours, minutes] = formatTime(Math.max(0, Math.round(totalSeconds))).split(":");
  return `${hours}:${minutes}`;
}

export function Timeline() {
  const {
    runProgress,
    tS,
    setTS,
    scenario,
    timelineReady,
    playbackRate,
    setPlaybackRate,
  } = useAppState();
  const maximum = Math.max(0, scenario.horizonS - scenario.stepS);
  const marks = Array.from({ length: 5 }, (_, index) => (scenario.horizonS * index) / 4);
  const focusPending = runProgress?.focusTS === tS && runProgress.focusReady === false;
  const progress = runProgress && runProgress.totalFrames > 0
    ? Math.min(1, Math.max(0, runProgress.completedFrames / runProgress.totalFrames))
    : 0;

  return (
    <section className="timeline-panel">
      <PlaybackControls />

      <div className="timeline-track-wrap">
        <input
          className="time-slider"
          type="range"
          min={0}
          max={maximum}
          step={Math.max(1, scenario.stepS)}
          value={Math.min(tS, maximum)}
          disabled={!timelineReady}
          onChange={(event) => setTS(Number(event.target.value))}
          aria-label="Момент расчёта"
          aria-busy={focusPending}
          style={{ "--computed-ratio": `${progress * 100}%` } as CSSProperties}
        />
        <div className="time-scale">
          {marks.map((mark) => <span key={mark}>{scaleLabel(mark)}</span>)}
        </div>
        {runProgress ? (
          <div className={`timeline-status ${focusPending ? "is-pending" : ""}`}>
            {focusPending
              ? `T+${scaleLabel(tS)} в приоритете · ${runProgress.completedFrames}/${runProgress.totalFrames}`
              : runProgress.phase === "complete"
                ? `готово ${runProgress.totalFrames}/${runProgress.totalFrames}`
                : `готово ${runProgress.completedFrames}/${runProgress.totalFrames}`}
          </div>
        ) : null}
      </div>

      <span className="playback-speed-label">Скорость:</span>
      <div className="playback-speeds" aria-label="Скорость воспроизведения">
        {SPEEDS.map((rate) => (
          <button
            key={rate}
            type="button"
            className={playbackRate === rate ? "is-active" : ""}
            onClick={() => setPlaybackRate(rate)}
            aria-pressed={playbackRate === rate}
          >
            {rate}×
          </button>
        ))}
      </div>
    </section>
  );
}
