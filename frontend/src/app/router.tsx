import type { ComponentType } from "react";
import { ComparisonPage } from "../pages/ComparisonPage";
import { NetworkAnalysisPage } from "../pages/NetworkAnalysisPage";
import { ProjectPage } from "../pages/ProjectPage";
import { ResiliencePage } from "../pages/ResiliencePage";
import type { PageId } from "../shared/model/types";

export const PAGE_LABELS: Record<PageId, string> = {
  project: "Проект",
  analysis: "Анализ сети",
  resilience: "Устойчивость",
  comparison: "Сравнение",
};

export const PAGE_COMPONENTS: Record<PageId, ComponentType> = {
  project: ProjectPage,
  analysis: NetworkAnalysisPage,
  resilience: ResiliencePage,
  comparison: ComparisonPage,
};
