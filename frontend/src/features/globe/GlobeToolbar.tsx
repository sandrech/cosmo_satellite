import { useState } from "react";
import { useAppState } from "../../shared/model/store";
import type { LayerVisibility } from "../../shared/model/types";

const LAYER_LABELS: Record<keyof LayerVisibility, string> = {
  satellites: "Спутники",
  groundSites: "Наземные пункты",
  orbits: "Орбиты",
  network: "Все ISL",
  route: "Активный маршрут",
  labels: "Подписи",
};

export function GlobeToolbar() {
  const {
    viewMode,
    setViewMode,
    clientId,
    setClientId,
    layers,
    toggleLayer,
  } = useAppState();
  const [open, setOpen] = useState(false);

  return (
    <div className="globe-toolbar">
      <div className="segmented" aria-label="Режим карты">
        <button
          className={viewMode === "3d" ? "active" : ""}
          onClick={() => setViewMode("3d")}
        >
          ◉ 3D
        </button>
        <button
          className={viewMode === "2d" ? "active" : ""}
          onClick={() => setViewMode("2d")}
        >
          ◫ 2D
        </button>
      </div>

      <select
        className="control"
        value={clientId}
        onChange={(event) => setClientId(event.target.value)}
        aria-label="Наземный пункт"
      >
        <option value="C65">C65</option>
        <option value="C70">C70</option>
        <option value="C72">C72</option>
      </select>

      <div className="layer-control">
        <button className="control" onClick={() => setOpen((value) => !value)}>
          ☼ Слои
        </button>
        {open && (
          <div className="layer-menu">
            <strong>Отображение</strong>
            {(Object.keys(layers) as Array<keyof LayerVisibility>).map((key) => (
              <label key={key}>
                <input
                  type="checkbox"
                  checked={layers[key]}
                  onChange={() => toggleLayer(key)}
                />
                {LAYER_LABELS[key]}
              </label>
            ))}
          </div>
        )}
      </div>
    </div>
  );
}
