import { useAppState } from "../../shared/model/store";
import { ErrorState } from "../../shared/ui/ErrorState";
import { LoadingState } from "../../shared/ui/LoadingState";
import { GlobeCanvas3D } from "./GlobeCanvas3D";
import { GlobeCesiumTexture } from "./GlobeCesiumTexture";
import { GlobeMap2D } from "./GlobeMap2D";

export function GlobeView() {
  const { frame, loading, error, viewMode, earthStyle } = useAppState();

  if (error && !frame) return <ErrorState message={error} />;
  if (!frame && loading) return <LoadingState label="Формируем первый кадр…" />;
  if (!frame) {
    return (
      <div className="state-message">
        <strong>Кадр ещё не рассчитан</strong>
        <span>Вернитесь в «Проект» и запустите расчёт модели.</span>
      </div>
    );
  }

  return (
    <div
      className={`globe-view reference-viewport is-${viewMode} is-${earthStyle}`}
    >
      {loading ? <div className="frame-loading">Считаем полную временную сетку…</div> : null}

      {earthStyle === "imagery" ? (
        <GlobeCesiumTexture />
      ) : viewMode === "2d" ? (
        <GlobeMap2D />
      ) : (
        <GlobeCanvas3D />
      )}

      <div className="globe-legend" aria-label="Легенда">
        <div><i className="legend-line legend-line-orbit" />Орбиты</div>
        <div><i className="legend-line legend-line-link" />ISL</div>
        <div><i className="legend-line legend-line-route" />Активный маршрут</div>
      </div>
    </div>
  );
}
