import { patchScenario } from "../../shared/api/scenarios";
import { useAppState } from "../../shared/model/store";
import type { ScenarioDraft } from "../../shared/model/types";

export function ProjectForm() {
  const { scenario, setScenario } = useAppState();
  const patch = <K extends keyof Omit<ScenarioDraft, "canonical">>(key: K, value: ScenarioDraft[K]) => {
    try {
      setScenario(patchScenario(scenario, key, value));
    } catch {
      // Keep the last valid scenario while the user is editing a numeric field.
    }
  };

  return (
    <div className="form-grid">
      <label>Название проекта<input value={scenario.title} onChange={(event) => patch("title", event.target.value)} /></label>
      <label>Этап запуска<select value={scenario.launchStage} onChange={(event) => patch("launchStage", Number(event.target.value) as 1 | 2 | 3)}><option value={1}>1 · 16 аппаратов</option><option value={2}>2 · 32 аппарата</option><option value={3}>3 · 48 аппаратов</option></select></label>
      <label>Высота, км<input type="number" value={scenario.altitudeKm} onChange={(event) => patch("altitudeKm", Number(event.target.value))} /></label>
      <label>Наклонение, °<input type="number" value={scenario.inclinationDeg} onChange={(event) => patch("inclinationDeg", Number(event.target.value))} /></label>
      <label>Начальный угол Земли, °<input type="number" value={scenario.earthAngle0Deg} onChange={(event) => patch("earthAngle0Deg", Number(event.target.value))} /></label>
      <label>Мин. угол места, °<input type="number" value={scenario.minElevationDeg} onChange={(event) => patch("minElevationDeg", Number(event.target.value))} /></label>
      <label>Дальность ISL, км<input type="number" value={scenario.islRangeKm} onChange={(event) => patch("islRangeKm", Number(event.target.value))} /></label>
      <label>Шаг расчёта, с<input type="number" min={1} value={scenario.stepS} onChange={(event) => patch("stepS", Number(event.target.value))} /></label>
      <label>Целевая доступность<input type="number" min={0} max={1} step={0.01} value={scenario.targetAvailability} onChange={(event) => patch("targetAvailability", Number(event.target.value))} /></label>
    </div>
  );
}
