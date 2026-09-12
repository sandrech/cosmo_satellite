import type { SimulationFrame } from "../../shared/model/types";

export function KpiCards({ frame, clientId }: { frame: SimulationFrame; clientId: string }) {
  const metric = frame.metrics.find((item) => item.clientId === clientId);
  const active = frame.satellites.filter((item) => item.active).length;
  return (
    <div className="kpi-strip">
      <div><span>Доступность за период</span><strong>{metric ? `${metric.availability.toFixed(1)}%` : "—"}</strong></div>
      <div><span>Макс. перерыв</span><strong>{metric ? `${metric.maxOutageMinutes.toFixed(1)} мин` : "—"}</strong></div>
      <div><span>Активные</span><strong>{active}/{frame.satellites.length}</strong></div>
      <div><span>Маршрут сейчас</span><strong>{frame.route.length ? `${frame.route.length - 1} перехода` : "нет"}</strong></div>
    </div>
  );
}
