import { FailureEditor } from "../features/project/FailureEditor";
import { ProjectForm } from "../features/project/ProjectForm";
import { RunControls } from "../features/project/RunControls";
import { ScenarioUpload } from "../features/project/ScenarioUpload";
import { useAppState } from "../shared/model/store";

export function ProjectPage() {
  const { scenario } = useAppState();
  return (
    <main className="page content-page">
      <header className="page-title">
        <div><span className="eyebrow">Настройка</span><h1>Проект группировки</h1></div>
        <span className="scenario-pill">◈ {scenario.id}</span>
      </header>
      <ScenarioUpload />
      <section className="content-card">
        <div className="section-heading"><div><h2>Параметры</h2><p>Изменения применяются к демонстрационному адаптеру сразу.</p></div></div>
        <ProjectForm />
      </section>
      <section className="content-card"><FailureEditor /></section>
      <RunControls />
    </main>
  );
}
