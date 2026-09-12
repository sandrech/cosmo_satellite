import { withFailures } from "../../shared/api/scenarios";
import { useAppState } from "../../shared/model/store";

export function FailureEditor() {
  const { scenario, setScenario } = useAppState();
  const items = scenario.canonical.failures;
  const update = (index: number, patch: Partial<(typeof items)[number]>) => {
    const next = items.map((item, itemIndex) => itemIndex === index ? { ...item, ...patch } : item);
    try { setScenario(withFailures(scenario, next)); } catch { /* retain last valid scenario */ }
  };
  return (
    <div className="failure-editor">
      <div className="section-heading">
        <div><h3>Отказы спутников</h3><p>Интервалы напрямую входят в канонический сценарий и расчёт backend.</p></div>
        <button className="secondary-button" onClick={() => {
          const id = scenario.canonical.design.satellites[0]?.id ?? "S01";
          setScenario(withFailures(scenario, [...items, { satellite_id: id, start_s: 0, end_s: scenario.horizonS }]));
        }}>+ Добавить</button>
      </div>
      {items.map((item, index) => (
        <div className="failure-row" key={`${item.satellite_id}-${index}`}>
          <select value={item.satellite_id} onChange={(event) => update(index, { satellite_id: event.target.value })}>
            {scenario.canonical.design.satellites.map((satellite) => <option key={satellite.id} value={satellite.id}>{satellite.id}</option>)}
          </select>
          <input type="number" min={0} max={scenario.horizonS} value={item.start_s} onChange={(event) => update(index, { start_s: Number(event.target.value) })} />
          <span>→</span>
          <input type="number" min={0} max={scenario.horizonS} value={item.end_s} onChange={(event) => update(index, { end_s: Number(event.target.value) })} />
          <button onClick={() => setScenario(withFailures(scenario, items.filter((_, itemIndex) => itemIndex !== index)))}>×</button>
        </div>
      ))}
    </div>
  );
}
