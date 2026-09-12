import { useAppState } from "../shared/model/store";
import type { PageId } from "../shared/model/types";
import { PAGE_COMPONENTS, PAGE_LABELS } from "./router";

const PAGE_ICONS: Record<PageId, string> = {
  project: "▰",
  analysis: "◒",
  resilience: "△",
  comparison: "⇄",
};

export default function App() {
  const { page, setPage } = useAppState();
  const Page = PAGE_COMPONENTS[page];

  return (
    <div className="app-shell">
      <header className="workbench-header">
        <button
          className="workbench-app-button"
          type="button"
          title="Проект"
          aria-label="Открыть проект"
          onClick={() => setPage("project")}
        >
          ◈
        </button>

        <nav className="workbench-tabs" aria-label="Рабочие вкладки">
          {(Object.keys(PAGE_LABELS) as PageId[]).map((id) => (
            <button
              key={id}
              type="button"
              className={`workbench-tab ${page === id ? "is-active" : ""}`}
              onClick={() => setPage(id)}
            >
              <span className="workbench-tab__grip" aria-hidden="true">⠿</span>
              <span className="workbench-tab__icon" aria-hidden="true">{PAGE_ICONS[id]}</span>
              <span>{PAGE_LABELS[id]}</span>
            </button>
          ))}
          <button
            className="workbench-tab-add"
            type="button"
            title="Новая вкладка"
            aria-label="Новая вкладка"
          >
            +
          </button>
        </nav>
      </header>

      <Page />
    </div>
  );
}
