import { useState } from "react";
import { HttpSimulationGateway } from "../../shared/api/client";
import { useAppState } from "../../shared/model/store";

function download(name: string, value: unknown) {
  const url = URL.createObjectURL(new Blob([JSON.stringify(value, null, 2)], { type: "application/json" }));
  const link = document.createElement("a");
  link.href = url;
  link.download = name;
  link.click();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export function ExportDialog() {
  const [open, setOpen] = useState(false);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const { scenario } = useAppState();
  return (
    <div className="export-control">
      <button className="top-action" onClick={() => setOpen(!open)}>Экспорт</button>
      {open && (
        <div className="export-menu">
          <strong>Выгрузить JSON</strong>
          <button onClick={() => download("scenario.json", scenario.canonical)}>Сценарий cosmo-A-1.0</button>
          <button disabled={busy} onClick={async () => {
            setBusy(true); setError(null);
            try {
              const result = await new HttpSimulationGateway().exportResult?.(scenario);
              download("result.json", result);
            } catch (reason) {
              setError(reason instanceof Error ? reason.message : "Ошибка экспорта");
            } finally { setBusy(false); }
          }}>{busy ? "Расчёт…" : "Результат cosmo-A-result-1.0"}</button>
          {error ? <small className="error-text">{error}</small> : null}
        </div>
      )}
    </div>
  );
}
