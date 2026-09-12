import { useAppState } from "../../shared/model/store";

export function ResilienceSummary() {
  const { frame, clientId } = useAppState();
  const failed = frame?.satellites.filter((item) => item.failed) ?? [];
  const metric = frame?.metrics.find((item) => item.clientId === clientId);
  return (
    <div className="summary-grid">
      <article><span>Отказавшие аппараты</span><strong>{failed.length}</strong><small>{failed.map((item) => item.id).join(", ") || "нет"}</small></article>
      <article><span>Пункты с маршрутом</span><strong>{frame ? `${frame.reachableClients}/${frame.clientCount}` : "—"}</strong><small>на выбранном шаге</small></article>
      <article><span>Связность выбранного клиента</span><strong>{frame?.currentConnectivity ?? "—"}</strong><small>{frame?.survivesAnySingleSatelliteFailure == null ? "нет данных" : frame.survivesAnySingleSatelliteFailure ? "переживает любой N−1" : "есть критичный одиночный отказ"}</small></article>
      <article><span>Худший перерыв за период</span><strong>{metric ? `${metric.maxOutageMinutes.toFixed(1)} мин` : "—"}</strong><small>{metric ? clientId : "сначала рассчитайте период"}</small></article>
    </div>
  );
}
