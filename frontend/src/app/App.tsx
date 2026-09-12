import { ExportDialog } from "../features/export/ExportDialog";
import { useAppState } from "../shared/model/store";
import type { PageId } from "../shared/model/types";
import { PAGE_COMPONENTS, PAGE_LABELS } from "./router";

export default function App() {
  const { page, setPage, scenario, frame } = useAppState();
  const Page = PAGE_COMPONENTS[page];
  return (
    <div className="app-shell">
      <header className="topbar">
        <div className="brand"><span className="brand-mark">C</span><strong>COSMO</strong></div>
        <nav>
          {(Object.keys(PAGE_LABELS) as PageId[]).map((id) => (
            <button
              key={id}
              className={page === id ? "active" : ""}
              onClick={() => setPage(id)}
            >
              {PAGE_LABELS[id]}
            </button>
          ))}
        </nav>
        <div className="topbar-actions">
          <span className="source-indicator"><i />{frame?.source === "mock" ? "Mock gateway" : "Backend"}</span>
          <span className="scenario-name">◈ {scenario.title}</span>
          <ExportDialog />
        </div>
      </header>
      <Page />
    </div>
  );
}
