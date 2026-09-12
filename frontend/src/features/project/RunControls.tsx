import { useAppState } from "../../shared/model/store";

export function RunControls() {
  const { setPage, setTS, setPlaying } = useAppState();
  return (
    <div className="run-controls">
      <button className="secondary-button" onClick={() => setTS(0)}>
        Сбросить время
      </button>
      <button
        className="primary-button"
        onClick={() => {
          setTS(0);
          setPlaying(false);
          setPage("analysis");
        }}
      >
        ▶ Рассчитать в демо
      </button>
    </div>
  );
}
