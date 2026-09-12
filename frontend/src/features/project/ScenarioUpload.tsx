import { useRef, useState } from "react";
import { scenarioFromJson } from "../../shared/api/scenarios";
import { useAppState } from "../../shared/model/store";

export function ScenarioUpload() {
  const inputRef = useRef<HTMLInputElement>(null);
  const { setScenario, setTS } = useAppState();
  const [message, setMessage] = useState("Можно загрузить JSON формата cosmo-A-1.0");

  async function load(file?: File) {
    if (!file) return;
    try {
      const parsed = JSON.parse(await file.text());
      setScenario(scenarioFromJson(parsed));
      setTS(0);
      setMessage(`Загружен: ${file.name}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "Не удалось прочитать файл");
    }
  }

  return (
    <div className="upload-card">
      <div>
        <strong>Сценарий JSON</strong>
        <p>{message}</p>
      </div>
      <button className="primary-button" onClick={() => inputRef.current?.click()}>
        Выбрать файл
      </button>
      <input
        ref={inputRef}
        hidden
        type="file"
        accept=".json,application/json"
        onChange={(event) => load(event.target.files?.[0])}
      />
    </div>
  );
}
