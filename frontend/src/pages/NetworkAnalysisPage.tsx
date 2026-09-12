import { GlobeToolbar } from "../features/globe/GlobeToolbar";
import { GlobeView } from "../features/globe/GlobeView";
import { PropertiesPanel } from "../features/inspector/PropertiesPanel";
import { KpiCards } from "../features/metrics/KpiCards";
import { Outliner } from "../features/outliner/Outliner";
import { Timeline } from "../features/timeline/Timeline";
import { useAppState } from "../shared/model/store";

export function NetworkAnalysisPage() {
  const { frame, clientId } = useAppState();
  return (
    <main className="analysis-page">
      <section className="analysis-workspace">
        <div className="globe-area">
          <GlobeView />
          <GlobeToolbar />
          {frame && <KpiCards frame={frame} clientId={clientId} />}
        </div>
        <Timeline />
      </section>
      <aside className="right-sidebar">
        <Outliner />
        <PropertiesPanel />
      </aside>
    </main>
  );
}
