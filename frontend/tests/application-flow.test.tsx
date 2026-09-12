import { describe, expect, it } from "vitest";
import { scenarioFromJson } from "../src/shared/api/scenarios";
import { formatTime } from "../src/features/timeline/PlaybackControls";

const validScenario = {
  schema_version: "cosmo-A-1.0",
  meta: { id: "demo", title: "Demo" },
  environment: {
    altitude_km: 600,
    inclination_deg: 88,
    earth_angle0_deg: 12,
    isl_range_km: 2500,
    min_elevation_deg: 10,
    step_s: 120,
    horizon_s: 86400,
    target_availability: 0.9,
  },
  design: {
    launch_stage: 2,
    planes: [{ id: "P1", raan_deg: 0, phase_deg: 0 }],
    satellites: [{ id: "S01", plane_id: "P1", slot_deg: 0, launch_batch: 1 }],
  },
  ground_sites: [
    { id: "C", name: "Client", role: "client", lat_deg: 65, lon_deg: 60 },
    { id: "G", name: "Gateway", role: "gateway", lat_deg: 69, lon_deg: 33 },
  ],
  failures: [],
  gateway_outages: [],
};

describe("application contracts", () => {
  it("preserves the complete canonical scenario", () => {
    const scenario = scenarioFromJson(validScenario);
    expect(scenario.id).toBe("demo");
    expect(scenario.launchStage).toBe(2);
    expect(scenario.altitudeKm).toBe(600);
    expect(scenario.canonical.environment.earth_angle0_deg).toBe(12);
    expect(scenario.canonical.design.satellites).toHaveLength(1);
    expect(scenario.canonical.ground_sites[0].lon_deg).toBe(60);
  });

  it("rejects malformed scenario input instead of silently defaulting", () => {
    expect(() => scenarioFromJson([])).toThrow();
    expect(() => scenarioFromJson({ ...validScenario, environment: { ...validScenario.environment, step_s: 0 } })).toThrow();
  });

  it("formats simulation time for the reusable timeline", () => {
    expect(formatTime(34680)).toBe("09:38:00");
  });
});
