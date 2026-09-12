import { useAppState } from "../../shared/model/store";
import { AvailabilityTimeline } from "../metrics/AvailabilityTimeline";
import { PlaybackControls } from "./PlaybackControls";

export function Timeline() {
  const { tS, setTS, scenario, frame } = useAppState();
  return (
    <section className="timeline-panel">
      <PlaybackControls />
      <input
        className="time-slider"
        type="range"
        min={0}
        max={scenario.horizonS - scenario.stepS}
        step={scenario.stepS}
        value={tS}
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
      {frame && <AvailabilityTimeline frame={frame} />}
    </section>
  );
}
