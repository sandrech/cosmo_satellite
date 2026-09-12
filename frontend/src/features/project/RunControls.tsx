import { useAppState } from "../../shared/model/store";

export function RunControls() {
  const { setPage, setTS, setPlaying, runDynamicAnalysis, dynamicLoading, dynamicError } = useAppState();
  return (
    <div className="run-controls">
      <button className="secondary-button" onClick={() => setTS(0)}>Сбросить время</button>
      <button className="primary-button" disabled={dynamicLoading} onClick={async () => {
        setTS(0);
        setPlaying(false);
        await runDynamicAnalysis();
        setPage("analysis");
      }}>{dynamicLoading ? "Расчёт…" : "▶ Рассчитать период"}</button>
      {dynamicError ? <span className="error-text">{dynamicError}</span> : null}
    </div>
  );
}
