import { DEMO_COMPARISON } from "../../shared/api/comparisons";

export function MetricsComparison() {
  return (
    <section className="content-card comparison-table">
      <h3>Результаты по наземным пунктам</h3>
      <div className="comparison-head"><span>Пункт</span><span>Доступность A</span><span>Доступность B</span><span>Макс. перерыв A/B</span></div>
      {DEMO_COMPARISON.clients.map((client) => (
        <div className="comparison-row" key={client.clientId}>
          <strong>{client.clientId}</strong>
          <span>{client.baselineAvailability}%</span>
          <span className="positive">{client.variantAvailability}%</span>
          <span>{client.baselineMaxOutage} / <b>{client.variantMaxOutage}</b> мин</span>
        </div>
      ))}
    </section>
  );
}
