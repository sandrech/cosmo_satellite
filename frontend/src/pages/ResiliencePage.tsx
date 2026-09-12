import { OutageExplanation } from "../features/resilience/OutageExplanation";
import { ResilienceSummary } from "../features/resilience/ResilienceSummary";
import { useAppState } from "../shared/model/store";

export function ResiliencePage() {
  const { frame, setPage } = useAppState();
  return (
    <main className="page content-page">
      <header className="page-title"><div><span className="eyebrow">Отказы и разрывы</span><h1>Устойчивость сети</h1></div><button className="secondary-button" onClick={() => setPage("analysis")}>Открыть на глобусе</button></header>
      <ResilienceSummary />
      <OutageExplanation />
      <section className="content-card">
        <h2>Затронутые направления</h2>
        <div className="impact-list">
          {frame?.metrics.map((metric) => (
            <div key={metric.clientId}><strong>{metric.clientId}</strong><span>Доступность {metric.availability}%</span><span>{metric.outages} перерыва</span><span>макс. {metric.maxOutageMinutes} мин</span></div>
          ))}
        </div>
      </section>
    </main>
  );
}
