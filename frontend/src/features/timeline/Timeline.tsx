import { useState } from "react";
import { useAppState } from "../../shared/model/store";
import { PlaybackControls } from "./PlaybackControls";

const SPEEDS = ["1×", "5×", "20×", "60×"];

export function Timeline() {
  const { modelRun, tS, setTS, scenario } = useAppState();
  const [speed, setSpeed] = useState("1×");

  return (
    <section className="timeline-panel">
      <PlaybackControls />

      <div className="timeline-track-wrap">
        <input
          className="time-slider"
          type="range"
          min={0}
          max={scenario.horizonS - scenario.stepS}
          step={scenario.stepS}
          value={tS}
          disabled={!modelRun}
          onChange={(event) => setTS(Number(event.target.value))}
          aria-label="Момент расчёта"
        />
        <div className="time-scale">
          <span>00:00</span>
          <span>06:00</span>
          <span>12:00</span>
          <span>18:00</span>
          <span>24:00</span>
        </div>
      </div>

      <span className="playback-speed-label">Скорость:</span>
      <div className="playback-speeds" aria-label="Скорость воспроизведения">
        {SPEEDS.map((item) => (
          <button
            key={item}
            type="button"
            className={speed === item ? "is-active" : ""}
            onClick={() => setSpeed(item)}
          >
            {item}
          </button>
        ))}
      </div>
    </section>
  );
}
