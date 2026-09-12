import { describe, expect, it } from "vitest";
import { scenarioFromJson } from "../src/shared/api/scenarios";
import { formatTime } from "../src/features/timeline/PlaybackControls";

describe("MVP application contracts", () => {
  it("adapts an uploaded scenario without coupling components to raw JSON", () => {
    const scenario = scenarioFromJson({
      meta: { id: "demo", title: "Demo" },
      environment: {
        altitude_km: 600,
        inclination_deg: 88,
        isl_range_km: 2500,
        step_s: 120,
        horizon_s: 86400,
        target_availability: 0.9,
      },
      design: { launch_stage: 2 },
    });
    expect(scenario.id).toBe("demo");
    expect(scenario.launchStage).toBe(2);
    expect(scenario.altitudeKm).toBe(600);
  });

  it("formats simulation time for the reusable timeline", () => {
    expect(formatTime(34680)).toBe("09:38:00");
  });
});
