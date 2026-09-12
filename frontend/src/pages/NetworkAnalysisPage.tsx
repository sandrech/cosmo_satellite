import { GlobeToolbar } from "../features/globe/GlobeToolbar";
import { GlobeView } from "../features/globe/GlobeView";
import { PropertiesPanel } from "../features/inspector/PropertiesPanel";
import { Outliner } from "../features/outliner/Outliner";
import { Timeline } from "../features/timeline/Timeline";
import { useAppState } from "../shared/model/store";

export function NetworkAnalysisPage() {
  const { selectedId } = useAppState();

  return (
    <main className={`analysis-page ${selectedId ? "has-selection" : ""}`}>
      <section className="analysis-workspace">
        <div className="globe-area">
          <GlobeView />
          <GlobeToolbar />
        </div>
        <Timeline />
      </section>

      <aside className="right-sidebar">
        <Outliner />
        {selectedId ? <PropertiesPanel /> : null}
      </aside>
    </main>
  );
}
