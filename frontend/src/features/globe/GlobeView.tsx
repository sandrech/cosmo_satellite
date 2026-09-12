import { useAppState } from "../../shared/model/store";
import { ErrorState } from "../../shared/ui/ErrorState";
import { LoadingState } from "../../shared/ui/LoadingState";
import { GlobeCanvas3D } from "./GlobeCanvas3D";
import { GlobeCesiumTexture } from "./GlobeCesiumTexture";
import { GlobeMap2D } from "./GlobeMap2D";

export function GlobeView() {
  const { frame, loading, runProgress, error, viewMode, earthStyle } = useAppState();

  if (error && !frame) return <ErrorState message={error} />;
  if (!frame && loading) {
    const focusLabel = runProgress?.focusTS !== undefined
      ? `Приоритетно считаем кадры вокруг T+${Math.round(runProgress.focusTS)} c…`
      : "Формируем первый кадр…";
    return <LoadingState label={focusLabel} />;
  }
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
      {loading ? (
        <div className="frame-loading">
          {runProgress?.phase === "aggregating"
            ? "Кадры готовы, считаем итоговую аналитику…"
            : runProgress
              ? runProgress.focusReady === false && runProgress.focusTS !== undefined
                ? `Считаем выбранный момент T+${Math.round(runProgress.focusTS)} c · готово ${runProgress.completedFrames}/${runProgress.totalFrames}`
                : `Рассчитано ${runProgress.completedFrames}/${runProgress.totalFrames} кадров`
              : "Запускаем расчёт временной сетки…"}
        </div>
      ) : null}

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
