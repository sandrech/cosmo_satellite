import { useState } from "react";
import { useAppState } from "../../shared/model/store";

export function RunControls() {
  const {
    dirty,
    loading,
    recalculate,
    setPage,
    setPlaying,
    setTS,
  } = useAppState();
  const [localError, setLocalError] = useState<string | null>(null);

  async function run() {
    setLocalError(null);
    setPlaying(false);
    try {
      await recalculate();
      setTS(0);
      setPage("analysis");
    } catch (reason: unknown) {
      setLocalError(reason instanceof Error ? reason.message : "Расчёт не выполнен");
    }
  }

  return (
    <div className="run-controls-wrap">
      <div className={`calculation-status ${dirty ? "is-dirty" : "is-ready"}`}>
        <i />
        {dirty
          ? "Параметры изменены — требуется пересчитать модель"
          : "Текущий полный расчёт соответствует параметрам"}
        {localError ? <strong>{localError}</strong> : null}
      </div>
      <div className="run-controls">
        <button className="secondary-button" type="button" onClick={() => setTS(0)} disabled={loading}>
          Сбросить время
        </button>
        <button className="primary-button" type="button" onClick={() => void run()} disabled={loading}>
          {loading ? "Расчёт всей модели…" : "▶ Рассчитать всю модель"}
        </button>
      </div>
    </div>
  );
}