import { FailureEditor } from "../features/project/FailureEditor";
import { ProjectForm } from "../features/project/ProjectForm";
import { RunControls } from "../features/project/RunControls";
import { ScenarioUpload } from "../features/project/ScenarioUpload";
import { useAppState } from "../shared/model/store";

export function ProjectPage() {
  const { scenario, modelRun } = useAppState();
  const clients = scenario.groundSites.filter((site) => site.role === "client").length;
  const gateways = scenario.groundSites.filter((site) => site.role === "gateway").length;

  return (
    <main className="page content-page project-page">
      <header className="page-title">
        <div>
          <span className="eyebrow">Модель и расчёт</span>
          <h1>{scenario.title}</h1>
          <p className="page-subtitle">Все поля сценария доступны до запуска. Backend рассчитывает официальную временную сетку одним запросом; перемещение по timeline после этого локальное.</p>
        </div>
        <span className="scenario-pill">{scenario.id}</span>
      </header>

      <ScenarioUpload />

      <div className="model-facts" aria-label="Состав модели">
        <span><strong>{scenario.planes.length}</strong> плоскости</span>
        <span><strong>{scenario.satellites.length}</strong> спутников</span>
        <span><strong>{clients}</strong> клиентов</span>
        <span><strong>{gateways}</strong> шлюзов</span>
        <span><strong>{scenario.failures.length + scenario.gatewayOutages.length}</strong> интервалов отказа</span>
        <span><strong>{modelRun ? "готов" : "—"}</strong> полный trace</span>
      </div>

      <section className="content-card">
        <div className="section-heading">
          <div>
            <h2>Параметры модели</h2>
            <p>Поля соответствуют <code>cosmo-A-1.0</code>. Плоскости, спутники и наземные пункты не сокращаются при загрузке.</p>
          </div>
        </div>
        <ProjectForm />
      </section>

      <section className="content-card"><FailureEditor /></section>
      <RunControls />
    </main>
  );
}
