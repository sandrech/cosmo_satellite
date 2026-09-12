import { useState } from "react";
import {
  saveFrontendWorkspaceState,
} from "../../shared/api/client";
import { buildFrontendWorkspaceState } from "../../shared/api/frontendJsonAdapter";
import { useAppState } from "../../shared/model/store";
import type { LayerVisibility } from "../../shared/model/types";

const LAYER_LABELS: Record<keyof LayerVisibility, string> = {
  satellites: "Спутники",
  groundSites: "Наземные пункты",
  orbits: "Орбиты",
  network: "Межспутниковые линии",
  route: "Активный маршрут",
  labels: "Подписи",
};

type GlobeCommand = "zoom-in" | "zoom-out" | "fullscreen";
type SaveStatus = "idle" | "saving" | "backend" | "download" | "error";

function emitGlobeCommand(command: GlobeCommand) {
  window.dispatchEvent(
    new CustomEvent<GlobeCommand>("cosmo:globe-command", { detail: command }),
  );
}

export function GlobeToolbar() {
  const {
    page,
    scenario,
    frame,
    tS,
    clientId,
    selectedId,
    viewMode,
    setViewMode,
    earthStyle,
    setEarthStyle,
    layers,
    toggleLayer,
    hiddenNodeIds,
  } = useAppState();
  const [open, setOpen] = useState(false);
  const [saveStatus, setSaveStatus] = useState<SaveStatus>("idle");

  const saveCurrentState = async () => {
    if (saveStatus === "saving") return;
    setSaveStatus("saving");

    const payload = buildFrontendWorkspaceState({
      page,
      scenario,
      frame,
      tS,
      clientId,
      selectedId,
      viewMode,
      earthStyle,
      layers,
      hiddenNodeIds,
    });

    try {
      const result = await saveFrontendWorkspaceState(payload);
      setSaveStatus(result.storage);
      window.setTimeout(() => setSaveStatus("idle"), 1800);
    } catch {
      setSaveStatus("error");
      window.setTimeout(() => setSaveStatus("idle"), 2200);
    }
  };

  const saveLabel =
    saveStatus === "saving"
      ? "Сохранение…"
      : saveStatus === "backend"
        ? "Сохранено"
        : saveStatus === "download"
          ? "JSON сохранён"
          : saveStatus === "error"
            ? "Ошибка"
            : "Сохранить";

  return (
    <div className="globe-toolbar" aria-label="Панель управления картой">
      <div className="globe-mode" aria-label="Режим карты">
        <button
          type="button"
          className={viewMode === "2d" ? "is-active" : ""}
          onClick={() => setViewMode("2d")}
        >
          2D
        </button>
        <button
          type="button"
          className={viewMode === "3d" ? "is-active" : ""}
          onClick={() => setViewMode("3d")}
        >
          3D
        </button>
      </div>

      <div className="globe-tools">
        <div className="layer-control">
          <button
            className="globe-tool globe-tool-layers"
            type="button"
            onClick={() => setOpen((value) => !value)}
            aria-expanded={open}
          >
            {open ? "Слои ▴" : "Слои ▾"}
          </button>

          {open && (
            <div className="layer-menu">
              {(Object.keys(layers) as Array<keyof LayerVisibility>).map((key) => (
                <label key={key}>
                  <input
                    type="checkbox"
                    checked={layers[key]}
                    onChange={() => toggleLayer(key)}
                  />
                  <span>{LAYER_LABELS[key]}</span>
                </label>
              ))}
            </div>
          )}
        </div>

        <button
          className={`globe-tool earth-texture-toggle ${earthStyle === "imagery" ? "is-active" : ""}`}
          type="button"
          aria-pressed={earthStyle === "imagery"}
          title="Включить или выключить детальную ч/б текстуру Земли"
          onClick={() => setEarthStyle(earthStyle === "imagery" ? "black" : "imagery")}
        >
          ◉ Земля
        </button>

        <button
          className={`globe-tool save-state-button save-state-${saveStatus}`}
          type="button"
          disabled={saveStatus === "saving"}
          title="Сохранить текущее состояние в frontend-workspace-state-1.0 JSON"
          onClick={saveCurrentState}
        >
          ⤓ {saveLabel}
        </button>

        <button className="globe-tool globe-tool-icon" type="button" title="Уменьшить" aria-label="Уменьшить" onClick={() => emitGlobeCommand("zoom-out")}>−</button>
        <button className="globe-tool globe-tool-icon" type="button" title="Увеличить" aria-label="Увеличить" onClick={() => emitGlobeCommand("zoom-in")}>＋</button>
        <button className="globe-tool globe-tool-icon" type="button" title="На весь экран" aria-label="На весь экран" onClick={() => emitGlobeCommand("fullscreen")}>⛶</button>
      </div>
    </div>
  );
}
