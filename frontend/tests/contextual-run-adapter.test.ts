import { describe, expect, it } from "vitest";
import { hasModelRunFrame } from "../src/shared/api/modelRunAdapter";
import type { ModelRunData } from "../src/shared/model/types";

describe("contextual model trace", () => {
  it("treats out-of-order partial traces as sparse instead of contiguous prefixes", () => {
    const run = {
      trace: {
        schema_version: "model-trace-2.0",
        sampling: { start_s: 0, end_s: 600, step_s: 120 },
        frames: [
          { t_s: 360 },
          { t_s: 480 },
        ],
      },
    } as unknown as ModelRunData;

    expect(hasModelRunFrame(run, 360)).toBe(true);
    expect(hasModelRunFrame(run, 480)).toBe(true);
    expect(hasModelRunFrame(run, 0)).toBe(false);
    expect(hasModelRunFrame(run, 120)).toBe(false);
  });
});
