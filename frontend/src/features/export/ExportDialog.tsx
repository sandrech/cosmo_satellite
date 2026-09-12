import { useState } from "react";
import { useAppState } from "../../shared/model/store";

function download(name: string, value: unknown) {
  const url = URL.createObjectURL(
    new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }),
  );
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  URL.revokeObjectURL(url);
}

export function ExportDialog() {
  const [open, setOpen] = useState(false);
  const { scenario, frame } = useAppState();
  return (
    <div className="export-control">
      <button className="top-action" onClick={() => setOpen(!open)}>Экспорт</button>
      {open && (
        <div className="export-menu">
          <strong>Выгрузить JSON</strong>
          <button onClick={() => download("scenario.json", scenario)}>Сценарий</button>
          <button
            disabled={!frame}
            onClick={() =>
              frame &&
              download("result-demo.json", {
                schema_version: "cosmo-A-result-1.0",
                effective_scenario: scenario,
                demo_frame: frame,
              })
            }
          >
            Демо-результат
          </button>
        </div>
      )}
    </div>
  );
}
