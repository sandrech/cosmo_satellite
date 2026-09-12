import type { SimulationFrame } from "../../shared/model/types";

export function KpiCards({
  frame,
  clientId,
}: {
  frame: SimulationFrame;
  clientId: string;
}) {
  const metric = frame.metrics.find((item) => item.clientId === clientId);
  if (!metric) return null;
  const active = frame.satellites.filter((item) => item.active).length;
  return (
    <div className="kpi-strip">
      <div><span>Доступность</span><strong>{metric.availability.toFixed(1)}%</strong></div>
      <div><span>Макс. перерыв</span><strong>{metric.maxOutageMinutes} мин</strong></div>
      <div><span>Активные</span><strong>{active}/48</strong></div>
      <div><span>Маршрут</span><strong>{frame.route.length ? `${frame.route.length - 1} перехода` : "нет"}</strong></div>
    </div>
  );
}
