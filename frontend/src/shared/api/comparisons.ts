import type { ComparisonResult } from "../model/types";

export const DEMO_COMPARISON: ComparisonResult = {
  baselineName: "Baseline A",
  variantName: "Variant B",
  changes: [
    { parameter: "P2 · RAAN", before: "60°", after: "68°" },
    { parameter: "P3 · Phase", before: "15°", after: "22.5°" },
    { parameter: "ISL range", before: "2000 км", after: "3000 км" },
  ],
  clients: [
    {
      clientId: "C65",
      baselineAvailability: 88.2,
      variantAvailability: 92.4,
      baselineMaxOutage: 38,
      variantMaxOutage: 16,
    },
    {
      clientId: "C70",
      baselineAvailability: 94.1,
      variantAvailability: 96.8,
      baselineMaxOutage: 24,
      variantMaxOutage: 12,
    },
    {
      clientId: "C72",
      baselineAvailability: 93.4,
      variantAvailability: 95.2,
      baselineMaxOutage: 26,
      variantMaxOutage: 14,
    },
  ],
};
