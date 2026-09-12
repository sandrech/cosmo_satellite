import { DEMO_COMPARISON } from "../../shared/api/comparisons";

export function ParameterDiff() {
  return (
    <section className="content-card">
      <h3>Изменения проекта</h3>
      <div className="diff-table">
        {DEMO_COMPARISON.changes.map((change) => (
          <div key={change.parameter}>
            <strong>{change.parameter}</strong>
            <span>{change.before}</span>
            <span className="arrow">→</span>
            <span className="after">{change.after}</span>
          </div>
        ))}
      </div>
    </section>
  );
}
