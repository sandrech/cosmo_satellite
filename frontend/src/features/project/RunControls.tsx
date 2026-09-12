import { useState } from "react";
import { useAppState } from "../../shared/model/store";

export function RunControls() {
  const {
    dirty,
    loading,
    modelRun,
    runProgress,
    recalculate,
    setPage,
    setPlaying,
    setTS,
  } = useAppState();
  const [localError, setLocalError] = useState<string | null>(null);
  const progressPercent = runProgress && runProgress.totalFrames > 0
    ? Math.round((runProgress.completedFrames / runProgress.totalFrames) * 100)
    : 0;

  async function run() {
    setLocalError(null);
    setPlaying(false);
    const calculation = recalculate();
    // Open the analysis workspace immediately. The timeline is fully navigable:
    // moving it reprioritizes backend work around the selected model time.
    setPage("analysis");
    try {
      await calculation;
    } catch (reason: unknown) {
      setLocalError(reason instanceof Error ? reason.message : "Расчёт не выполнен");
    }
  }

  return (
    <div className="run-controls-wrap">
      <div className={`calculation-status ${dirty ? "is-dirty" : "is-ready"}`}>
        <i />
        {loading
          ? runProgress?.phase === "aggregating"
            ? `Все ${runProgress.totalFrames} кадров готовы — считаем итоговую аналитику`
            : runProgress
              ? `Фоновый расчёт: ${runProgress.completedFrames}/${runProgress.totalFrames} кадров (${progressPercent}%). Выбранная область имеет приоритет`
              : "Запускаем потоковый расчёт — стартовый кадр уже доступен"
          : dirty
            ? "Параметры изменены — требуется пересчитать модель"
            : modelRun
              ? "Текущий полный расчёт соответствует параметрам"
              : "Стартовый кадр готов — timeline уже доступен; полный расчёт нужен для периодовой аналитики"}
        {localError ? <strong>{localError}</strong> : null}
      </div>
      <div className="run-controls">
        <button className="secondary-button" type="button" onClick={() => setTS(0)} disabled={loading}>
          Сбросить время
        </button>
        <button className="primary-button" type="button" onClick={() => void run()} disabled={loading}>
          {loading && runProgress
            ? `Расчёт ${progressPercent}%…`
            : loading
              ? "Запуск расчёта…"
              : "▶ Рассчитать всю модель"}
        </button>
      </div>
    </div>
  );
}