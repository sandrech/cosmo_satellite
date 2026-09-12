import { useEffect, useRef, useState } from "react";
import { scenarioFromJson, scenarioToJson } from "../../shared/api/scenarios";
import { useAppState } from "../../shared/model/store";
import type { RoutingStrategyId, ScenarioDraft } from "../../shared/model/types";

function scenarioFromUploadedJson(value: unknown): { scenario: ScenarioDraft; tS: number | null; routing: RoutingStrategyId | null } {
  if (!value || typeof value !== "object") {
    throw new Error("Файл должен содержать JSON-объект");
  }

  const root = value as Record<string, unknown>;
  if (root.schema_version !== "frontend-workspace-state-1.0") {
    return { scenario: scenarioFromJson(value), tS: null, routing: null };
  }

  const workspaceScenario = root.scenario;
  if (!workspaceScenario || typeof workspaceScenario !== "object") {
    throw new Error("Workspace не содержит сценарий");
  }

  const stored = workspaceScenario as Record<string, unknown>;
  let scenario: ScenarioDraft;
  if (stored.canonical) {
    // Backward compatibility with the old workspace envelope.
    scenario = scenarioFromJson(stored.canonical);
  } else {
    // Current workspace stores the editable ScenarioDraft. Round-trip through
    // the canonical contract so the same strict validation is applied.
    scenario = scenarioFromJson(scenarioToJson(workspaceScenario as unknown as ScenarioDraft));
  }

  const runtime = root.runtime && typeof root.runtime === "object"
    ? root.runtime as Record<string, unknown>
    : {};
  const tS = typeof runtime.t_s === "number" ? runtime.t_s : null;
  const routing = runtime.routing_strategy_id === "minimum_hops"
    || runtime.routing_strategy_id === "minimum_distance"
    || runtime.routing_strategy_id === "resilient_distance"
    ? runtime.routing_strategy_id
    : null;

  return { scenario, tS, routing };
}

export function ScenarioUpload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const {
    availableModels,
    loadModel,
    loading,
    scenario,
    setRoutingStrategyId,
    setScenario,
    setTS,
  } = useAppState();
  const [selectedModelId, setSelectedModelId] = useState(scenario.id);
  const [message, setMessage] = useState(
    "Модель загружается целиком: параметры, плоскости, аппараты, наземные пункты и интервалы отказов.",
  );

  useEffect(() => {
    setSelectedModelId(scenario.id);
  }, [scenario.id]);

  async function loadLocalFile(file?: File) {
    if (!file) return;
    try {
      const parsed: unknown = JSON.parse(await file.text());
      const loaded = scenarioFromUploadedJson(parsed);
      setScenario(loaded.scenario);
      setTS(loaded.tS ?? 0);
      if (loaded.routing) setRoutingStrategyId(loaded.routing);
      setSelectedModelId(loaded.scenario.id);
      setMessage(`Локальный JSON загружен полностью: ${file.name}. Нажмите «Рассчитать всю модель».`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Не удалось прочитать файл");
    } finally {
      if (inputRef.current) inputRef.current.value = "";
    }
  }

  async function openRepositoryModel() {
    if (!selectedModelId) return;
    try {
      await loadModel(selectedModelId);
      setMessage("Модель загружена из backend, стартовый кадр готов. Для timeline и динамической аналитики нажмите «Рассчитать всю модель».");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Не удалось загрузить модель");
    }
  }

  return (
    <div className="upload-card model-source-card">
      <div className="model-source-copy">
        <strong>Источник модели</strong>
        <p>{message}</p>
      </div>

      <div className="model-source-actions">
        <select
          value={selectedModelId}
          onChange={(event) => setSelectedModelId(event.target.value)}
          aria-label="Модель из репозитория"
          disabled={loading || availableModels.length === 0}
        >
          {availableModels.length === 0 ? (
            <option value={scenario.id}>{scenario.title}</option>
          ) : (
            availableModels.map((model) => (
              <option key={model.id} value={model.id}>
                {model.title} · {model.filename}
              </option>
            ))
          )}
        </select>
        <button
          className="primary-button"
          type="button"
          disabled={loading || !selectedModelId || availableModels.length === 0}
          onClick={() => void openRepositoryModel()}
        >
          {loading ? "Загрузка…" : "Открыть модель"}
        </button>
        <button
          className="secondary-button"
          type="button"
          onClick={() => inputRef.current?.click()}
          disabled={loading}
        >
          Импорт JSON
        </button>
        <input
          ref={inputRef}
          hidden
          type="file"
          accept=".json,application/json"
          onChange={(event) => void loadLocalFile(event.target.files?.[0])}
        />
      </div>
    </div>
  );
}
