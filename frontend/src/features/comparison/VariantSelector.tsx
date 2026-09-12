import { DEMO_COMPARISON } from "../../shared/api/comparisons";

export function VariantSelector() {
  return (
    <div className="variant-selector">
      <label>Базовый вариант<select defaultValue="a"><option value="a">{DEMO_COMPARISON.baselineName}</option></select></label>
      <span>↔</span>
      <label>Проектный вариант<select defaultValue="b"><option value="b">{DEMO_COMPARISON.variantName}</option></select></label>
    </div>
  );
}
