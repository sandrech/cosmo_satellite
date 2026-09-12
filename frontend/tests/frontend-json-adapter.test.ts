import { describe, expect, it } from "vitest";
import { adaptModelSnapshot, type ModelSnapshotDto } from "../src/shared/api/frontendJsonAdapter";
import { scenarioFromJson } from "../src/shared/api/scenarios";

const scenario = scenarioFromJson({
  schema_version: "cosmo-A-1.0",
  meta: { id: "x", title: "x" },
  environment: { altitude_km: 550, inclination_deg: 87, earth_angle0_deg: 12, horizon_s: 120, step_s: 120, min_elevation_deg: 10, isl_range_km: 3000, target_availability: 0.9 },
  design: {
    launch_stage: 1,
    planes: [{ id: "P1", raan_deg: 0, phase_deg: 0 }],
    satellites: [{ id: "S01", plane_id: "P1", slot_deg: 0, launch_batch: 2 }],
  },
  ground_sites: [
    { id: "C", name: "Client", role: "client", lat_deg: 65, lon_deg: 60 },
    { id: "G", name: "Gateway", role: "gateway", lat_deg: 69, lon_deg: 33 },
  ],
  failures: [],
  gateway_outages: [],
});

const payload = {
  schema_version: "model-snapshot-2.0",
  t_s: 0,
  scene: {
    schema_version: "spatial-scene-1.0",
    t_s: 0,
    coordinate_frame: "earth_fixed",
    body_radius_km: 6371,
    points: [
      { id: "S01", label: "S01", kind: "satellite", position: { x_km: 6900, y_km: 0, z_km: 0 }, available: false, trajectory_group_id: "P1" },
      { id: "C", label: "Client", kind: "client", position: { x_km: 1, y_km: 2, z_km: 3 }, available: true },
      { id: "G", label: "Gateway", kind: "gateway", position: { x_km: 4, y_km: 5, z_km: 6 }, available: true },
    ],
    contacts: [],
  },
  network: {
    schema_version: "spatial-network-1.0",
    t_s: 0,
    nodes: [
      { id: "S01", kind: "satellite", available: false },
      { id: "C", kind: "client", available: true },
      { id: "G", kind: "gateway", available: true },
    ],
    edges: [], ground_observations: [], ground_visibility: [],
  },
  analysis: {
    schema_version: "static-analysis-2.0",
    clients: [{
      client_id: "C",
      coverage: { visible_satellites: [], has_visibility: false },
      service: { reachable: false, valid_ingress_satellites: [], reachable_gateways: [], no_route_reason: "no_visible_satellite" },
      routing: { selected_route: null, routes: [] },
      resilience: { satellite_connectivity: { node_disjoint_path_count: 0, minimum_cut: [] }, critical_satellites: [], survives_any_single_satellite_failure: false },
    }],
  },
} as unknown as ModelSnapshotDto;

describe("frontend backend adapter", () => {
  it("distinguishes not launched satellites from failed satellites and preserves ECEF ground coordinates", () => {
    const frame = adaptModelSnapshot(payload, { scenario, tS: 0, clientId: "C" });
    expect(frame.satellites[0].active).toBe(false);
    expect(frame.satellites[0].failed).toBe(false);
    expect(frame.satellites[0].inactiveReason).toBe("not-launched");
    expect(frame.groundSites.find((site) => site.id === "C")?.position).toEqual({ xKm: 1, yKm: 2, zKm: 3 });
  });

  it("never substitutes another client when the requested client is absent", () => {
    expect(() => adaptModelSnapshot(payload, { scenario, tS: 0, clientId: "missing" })).toThrow(/requested client/);
  });
});
