import type { SimulationFrame } from "../../shared/model/types";

export function AvailabilityTimeline({ frame }: { frame: SimulationFrame }) {
  if (!frame.metrics.length) {
    return <div className="availability-chart"><p>Периодовая аналитика ещё не рассчитана. Нажмите «Рассчитать период».</p></div>;
  }
  return (
    <div className="availability-chart">
      <div className="availability-legend">
        <span><i className="legend-path" />есть путь</span>
        <span><i className="legend-visible" />виден, нет пути</span>
        <span><i className="legend-none" />нет спутника</span>
      </div>
      {frame.metrics.map((metric) => (
        <div className="availability-row" key={metric.clientId}>
          <span>{metric.clientId}</span>
          <div className="availability-track">
            {(frame.availability[metric.clientId] ?? []).map((segment, index) => (
              <i key={index} className={`segment ${segment.state}`} style={{ left: `${(segment.from / frame.horizonS) * 100}%`, width: `${((segment.to - segment.from) / frame.horizonS) * 100}%` }} />
            ))}
            <i className="time-cursor" style={{ left: `${(frame.tS / frame.horizonS) * 100}%` }} />
          </div>
          <strong>{metric.availability.toFixed(1)}%</strong>
        </div>
      ))}
    </div>
  );
}
