import { useEffect, useRef, useState } from "react";
import { scenarioFromJson } from "../../shared/api/scenarios";
import { useAppState } from "../../shared/model/store";

export function ScenarioUpload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const {
    availableModels,
    loadModel,
    loading,
    scenario,
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
      const parsed = JSON.parse(await file.text());
      const next = scenarioFromJson(parsed);
      setScenario(next);
      setTS(0);
      setSelectedModelId(next.id);
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
      setMessage("Модель загружена из backend и полностью рассчитана на всей временной сетке.");
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