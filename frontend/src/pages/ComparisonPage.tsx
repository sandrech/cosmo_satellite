import { MetricsComparison } from "../features/comparison/MetricsComparison";
import { ParameterDiff } from "../features/comparison/ParameterDiff";
import { RecommendationCard } from "../features/comparison/RecommendationCard";
import { VariantSelector } from "../features/comparison/VariantSelector";

export function ComparisonPage() {
  return (
    <main className="page content-page">
      <header className="page-title"><div><span className="eyebrow">A/B-анализ</span><h1>Сравнение вариантов</h1></div></header>
      <VariantSelector />
      <div className="two-column"><ParameterDiff /><MetricsComparison /></div>
      <RecommendationCard />
    </main>
  );
}
