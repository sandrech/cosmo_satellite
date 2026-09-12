import { useAppState } from "../../shared/model/store";
import type {
  GroundSiteDraft,
  PlaneDraft,
  SatelliteDraft,
  ScenarioDraft,
} from "../../shared/model/types";

function numberValue(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function ProjectForm() {
  const { scenario, setScenario } = useAppState();

  const patch = <K extends keyof ScenarioDraft>(key: K, value: ScenarioDraft[K]) =>
    setScenario({ ...scenario, [key]: value });

  const patchPlane = (index: number, next: Partial<PlaneDraft>) => {
    patch(
      "planes",
      scenario.planes.map((plane, itemIndex) =>
        itemIndex === index ? { ...plane, ...next } : plane,
      ),
    );
  };

  const patchSatellite = (index: number, next: Partial<SatelliteDraft>) => {
    patch(
      "satellites",
      scenario.satellites.map((satellite, itemIndex) =>
        itemIndex === index ? { ...satellite, ...next } : satellite,
      ),
    );
  };

  const patchGroundSite = (index: number, next: Partial<GroundSiteDraft>) => {
    patch(
      "groundSites",
      scenario.groundSites.map((site, itemIndex) =>
        itemIndex === index ? { ...site, ...next } : site,
      ),
    );
  };

  return (
    <div className="project-model-editor">
      <div className="form-grid">
        <label>
          ID модели
          <input value={scenario.id} onChange={(event) => patch("id", event.target.value)} />
        </label>
        <label>
          Название
          <input value={scenario.title} onChange={(event) => patch("title", event.target.value)} />
        </label>
        <label>
          Этап запуска
          <select
            value={scenario.launchStage}
            onChange={(event) => patch("launchStage", Number(event.target.value) as 1 | 2 | 3)}
          >
            <option value={1}>1</option>
            <option value={2}>2</option>
            <option value={3}>3</option>
          </select>
        </label>
        <label>
          Высота орбиты, км
          <input type="number" value={scenario.altitudeKm} onChange={(event) => patch("altitudeKm", numberValue(event.target.value))} />
        </label>
        <label>
          Наклонение, °
          <input type="number" value={scenario.inclinationDeg} onChange={(event) => patch("inclinationDeg", numberValue(event.target.value))} />
        </label>
        <label>
          Начальный угол Земли, °
          <input type="number" value={scenario.earthAngle0Deg} onChange={(event) => patch("earthAngle0Deg", numberValue(event.target.value))} />
        </label>
        <label>
          Мин. угол места, °
          <input type="number" value={scenario.minElevationDeg} onChange={(event) => patch("minElevationDeg", numberValue(event.target.value))} />
        </label>
        <label>
          Дальность ISL, км
          <input type="number" value={scenario.islRangeKm} onChange={(event) => patch("islRangeKm", numberValue(event.target.value))} />
        </label>
        <label>
          Горизонт расчёта, с
          <input type="number" value={scenario.horizonS} onChange={(event) => patch("horizonS", numberValue(event.target.value))} />
        </label>
        <label>
          Шаг расчёта, с
          <input type="number" value={scenario.stepS} onChange={(event) => patch("stepS", numberValue(event.target.value))} />
        </label>
        <label>
          Целевая доступность
          <input type="number" min="0" max="1" step="0.01" value={scenario.targetAvailability} onChange={(event) => patch("targetAvailability", numberValue(event.target.value))} />
        </label>
        <label>
          Версия схемы
          <input value={scenario.schemaVersion} readOnly />
        </label>
      </div>

      <section className="model-subsection planes-editor">
        <div className="section-heading compact-heading">
          <div>
            <h3>Орбитальные плоскости</h3>
            <p>RAAN и фазовый сдвиг берутся напрямую из design.planes; наклонение задаётся выше в environment.</p>
          </div>
        </div>
        <div className="plane-card-grid">
          {scenario.planes.map((plane, index) => (
            <article className="plane-card" key={`${plane.id}-${index}`}>
              <strong>{plane.id || `P${index + 1}`}</strong>
              <label>
                ID
                <input value={plane.id} onChange={(event) => patchPlane(index, { id: event.target.value })} />
              </label>
              <label>
                RAAN, °
                <input type="number" min="0" max="359.999" step="0.1" value={plane.raanDeg} onChange={(event) => patchPlane(index, { raanDeg: numberValue(event.target.value) })} />
              </label>
              <label>
                Фазовый сдвиг, °
                <input type="number" min="0" max="359.999" step="0.1" value={plane.phaseDeg} onChange={(event) => patchPlane(index, { phaseDeg: numberValue(event.target.value) })} />
              </label>
            </article>
          ))}
        </div>
      </section>

      <details className="model-details">
        <summary>Спутники ({scenario.satellites.length})</summary>
        <div className="model-table satellite-parameter-table">
          <div className="model-table-head"><span>ID</span><span>Плоскость</span><span>Слот, °</span><span>Партия запуска</span></div>
          {scenario.satellites.map((satellite, index) => (
            <div className="model-table-row" key={`${satellite.id}-${index}`}>
              <input value={satellite.id} onChange={(event) => patchSatellite(index, { id: event.target.value })} />
              <select value={satellite.planeId} onChange={(event) => patchSatellite(index, { planeId: event.target.value })}>
                {scenario.planes.map((plane) => <option key={plane.id} value={plane.id}>{plane.id}</option>)}
              </select>
              <input type="number" value={satellite.slotDeg} onChange={(event) => patchSatellite(index, { slotDeg: numberValue(event.target.value) })} />
              <select value={satellite.launchBatch} onChange={(event) => patchSatellite(index, { launchBatch: Number(event.target.value) as 1 | 2 | 3 })}>
                <option value={1}>1</option><option value={2}>2</option><option value={3}>3</option>
              </select>
            </div>
          ))}
        </div>
      </details>

      <details className="model-details">
        <summary>Наземные пункты ({scenario.groundSites.length})</summary>
        <div className="model-table ground-parameter-table">
          <div className="model-table-head"><span>ID</span><span>Название</span><span>Роль</span><span>Широта</span><span>Долгота</span></div>
          {scenario.groundSites.map((site, index) => (
            <div className="model-table-row" key={`${site.id}-${index}`}>
              <input value={site.id} onChange={(event) => patchGroundSite(index, { id: event.target.value })} />
              <input value={site.name} onChange={(event) => patchGroundSite(index, { name: event.target.value })} />
              <select value={site.role} onChange={(event) => patchGroundSite(index, { role: event.target.value as GroundSiteDraft["role"] })}>
                <option value="client">client</option><option value="gateway">gateway</option>
              </select>
              <input type="number" step="0.01" value={site.latDeg} onChange={(event) => patchGroundSite(index, { latDeg: numberValue(event.target.value) })} />
              <input type="number" step="0.01" value={site.lonDeg} onChange={(event) => patchGroundSite(index, { lonDeg: numberValue(event.target.value) })} />
            </div>
          ))}
        </div>
      </details>
    </div>
  );
}
