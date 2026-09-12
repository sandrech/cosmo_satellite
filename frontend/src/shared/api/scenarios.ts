import type { CosmoScenario, ScenarioDraft } from "../model/types";

function object(value: unknown, path: string): Record<string, unknown> {
  if (!value || typeof value !== "object" || Array.isArray(value)) {
    throw new Error(`${path} должен быть JSON-объектом`);
  }
  return value as Record<string, unknown>;
}

function array(value: unknown, path: string): unknown[] {
  if (!Array.isArray(value)) throw new Error(`${path} должен быть массивом`);
  return value;
}

function string(value: unknown, path: string) {
  if (typeof value !== "string" || !value.trim()) throw new Error(`${path} должен быть непустой строкой`);
  return value;
}

function number(value: unknown, path: string) {
  if (typeof value !== "number" || !Number.isFinite(value)) throw new Error(`${path} должен быть конечным числом`);
  return value;
}

function integer(value: unknown, path: string) {
  const result = number(value, path);
  if (!Number.isInteger(result)) throw new Error(`${path} должен быть целым числом`);
  return result;
}

function validateScenario(value: unknown): CosmoScenario {
  const root = object(value, "scenario");
  if (root.schema_version !== "cosmo-A-1.0") throw new Error("schema_version должен быть cosmo-A-1.0");
  const meta = object(root.meta, "meta");
  const environment = object(root.environment, "environment");
  const design = object(root.design, "design");

  const horizon = integer(environment.horizon_s, "environment.horizon_s");
  const step = integer(environment.step_s, "environment.step_s");
  if (!(step > 0 && horizon >= step && horizon <= 172800 && horizon % step === 0)) {
    throw new Error("environment: некорректная расчётная сетка");
  }
  const altitude = number(environment.altitude_km, "environment.altitude_km");
  const inclination = number(environment.inclination_deg, "environment.inclination_deg");
  const minElevation = number(environment.min_elevation_deg, "environment.min_elevation_deg");
  const islRange = number(environment.isl_range_km, "environment.isl_range_km");
  const target = number(environment.target_availability, "environment.target_availability");
  if (altitude < 200 || altitude > 1200) throw new Error("altitude_km должен быть в [200, 1200]");
  if (!(inclination > 0 && inclination <= 180)) throw new Error("inclination_deg должен быть в (0, 180]");
  if (!(minElevation >= 0 && minElevation < 90)) throw new Error("min_elevation_deg должен быть в [0, 90)");
  if (!(islRange > 0 && islRange <= 10000)) throw new Error("isl_range_km должен быть в (0, 10000]");
  if (!(target >= 0 && target <= 1)) throw new Error("target_availability должен быть в [0, 1]");

  const launchStage = integer(design.launch_stage, "design.launch_stage");
  if (![1, 2, 3].includes(launchStage)) throw new Error("design.launch_stage должен быть 1, 2 или 3");

  const planes = array(design.planes, "design.planes").map((raw, index) => {
    const item = object(raw, `design.planes[${index}]`);
    const raan = number(item.raan_deg, `design.planes[${index}].raan_deg`);
    const phase = number(item.phase_deg, `design.planes[${index}].phase_deg`);
    if (!(raan >= 0 && raan < 360 && phase >= 0 && phase < 360)) throw new Error("углы плоскости должны быть в [0, 360)");
    return { id: string(item.id, `design.planes[${index}].id`), raan_deg: raan, phase_deg: phase };
  });
  if (!planes.length || new Set(planes.map((item) => item.id)).size !== planes.length) throw new Error("ID плоскостей должны быть уникальны");
  const planeIds = new Set(planes.map((item) => item.id));

  const satellites = array(design.satellites, "design.satellites").map((raw, index) => {
    const item = object(raw, `design.satellites[${index}]`);
    const planeId = string(item.plane_id, `design.satellites[${index}].plane_id`);
    const batch = integer(item.launch_batch, `design.satellites[${index}].launch_batch`);
    if (!planeIds.has(planeId)) throw new Error(`неизвестная плоскость ${planeId}`);
    if (![1, 2, 3].includes(batch)) throw new Error("launch_batch должен быть 1, 2 или 3");
    return {
      id: string(item.id, `design.satellites[${index}].id`),
      plane_id: planeId,
      slot_deg: number(item.slot_deg, `design.satellites[${index}].slot_deg`),
      launch_batch: batch as 1 | 2 | 3,
    };
  });
  if (!satellites.length || new Set(satellites.map((item) => item.id)).size !== satellites.length) throw new Error("ID спутников должны быть уникальны");
  const satelliteIds = new Set(satellites.map((item) => item.id));

  const groundSites = array(root.ground_sites, "ground_sites").map((raw, index) => {
    const item = object(raw, `ground_sites[${index}]`);
    const role = string(item.role, `ground_sites[${index}].role`);
    if (role !== "client" && role !== "gateway") throw new Error(`ground_sites[${index}].role должен быть client или gateway`);
    const lat = number(item.lat_deg, `ground_sites[${index}].lat_deg`);
    const lon = number(item.lon_deg, `ground_sites[${index}].lon_deg`);
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) throw new Error(`ground_sites[${index}] имеет некорректные координаты`);
    return {
      id: string(item.id, `ground_sites[${index}].id`),
      name: string(item.name, `ground_sites[${index}].name`),
      role: role as "client" | "gateway",
      lat_deg: lat,
      lon_deg: lon,
    };
  });
  const groundIds = new Set(groundSites.map((item) => item.id));
  if (groundIds.size !== groundSites.length) throw new Error("ID наземных пунктов должны быть уникальны");
  if (!groundSites.some((item) => item.role === "client") || !groundSites.some((item) => item.role === "gateway")) throw new Error("нужен хотя бы один client и gateway");

  const failures = array(root.failures, "failures").map((raw, index) => {
    const item = object(raw, `failures[${index}]`);
    const id = string(item.satellite_id, `failures[${index}].satellite_id`);
    const start = number(item.start_s, `failures[${index}].start_s`);
    const end = number(item.end_s, `failures[${index}].end_s`);
    if (!satelliteIds.has(id) || !(0 <= start && start < end && end <= horizon)) throw new Error(`failures[${index}] некорректен`);
    return { satellite_id: id, start_s: start, end_s: end };
  });
  const gatewayIds = new Set(groundSites.filter((item) => item.role === "gateway").map((item) => item.id));
  const gatewayOutages = array(root.gateway_outages, "gateway_outages").map((raw, index) => {
    const item = object(raw, `gateway_outages[${index}]`);
    const id = string(item.gateway_id, `gateway_outages[${index}].gateway_id`);
    const start = number(item.start_s, `gateway_outages[${index}].start_s`);
    const end = number(item.end_s, `gateway_outages[${index}].end_s`);
    if (!gatewayIds.has(id) || !(0 <= start && start < end && end <= horizon)) throw new Error(`gateway_outages[${index}] некорректен`);
    return { gateway_id: id, start_s: start, end_s: end };
  });

  return {
    schema_version: "cosmo-A-1.0",
    meta: { id: string(meta.id, "meta.id"), title: string(meta.title, "meta.title") },
    environment: {
      altitude_km: altitude,
      inclination_deg: inclination,
      earth_angle0_deg: number(environment.earth_angle0_deg, "environment.earth_angle0_deg"),
      horizon_s: horizon,
      step_s: step,
      min_elevation_deg: minElevation,
      isl_range_km: islRange,
      target_availability: target,
    },
    design: { launch_stage: launchStage as 1 | 2 | 3, planes, satellites },
    ground_sites: groundSites,
    failures,
    gateway_outages: gatewayOutages,
  };
}

function draft(canonical: CosmoScenario): ScenarioDraft {
  return {
    id: canonical.meta.id,
    title: canonical.meta.title,
    altitudeKm: canonical.environment.altitude_km,
    inclinationDeg: canonical.environment.inclination_deg,
    earthAngle0Deg: canonical.environment.earth_angle0_deg,
    launchStage: canonical.design.launch_stage,
    islRangeKm: canonical.environment.isl_range_km,
    minElevationDeg: canonical.environment.min_elevation_deg,
    stepS: canonical.environment.step_s,
    horizonS: canonical.environment.horizon_s,
    targetAvailability: canonical.environment.target_availability,
    canonical,
  };
}

const defaultCanonical: CosmoScenario = {
  schema_version: "cosmo-A-1.0",
  meta: { id: "01_full_constellation", title: "Полная группировка" },
  environment: {
    altitude_km: 550,
    inclination_deg: 87,
    earth_angle0_deg: 12,
    horizon_s: 86400,
    step_s: 120,
    min_elevation_deg: 10,
    isl_range_km: 3000,
    target_availability: 0.9,
  },
  design: {
    launch_stage: 3,
    planes: [
      { id: "P1", raan_deg: 0, phase_deg: 0 },
      { id: "P2", raan_deg: 60, phase_deg: 7.5 },
      { id: "P3", raan_deg: 120, phase_deg: 15 },
    ],
    satellites: Array.from({ length: 48 }, (_, index) => ({
      id: `S${String(index + 1).padStart(2, "0")}`,
      plane_id: `P${Math.floor(index / 16) + 1}`,
      slot_deg: (index % 16) * 22.5,
      launch_batch: (Math.floor(index / 16) + 1) as 1 | 2 | 3,
    })),
  },
  ground_sites: [
    { id: "C65", name: "Client 65", role: "client", lat_deg: 65, lon_deg: 60 },
    { id: "C70", name: "Client 70", role: "client", lat_deg: 70, lon_deg: 90 },
    { id: "C72", name: "Client 72", role: "client", lat_deg: 72, lon_deg: 130 },
    { id: "G_MUR", name: "Gateway Murmansk", role: "gateway", lat_deg: 68.97, lon_deg: 33.07 },
  ],
  failures: [],
  gateway_outages: [],
};

export const DEFAULT_SCENARIO: ScenarioDraft = draft(defaultCanonical);

export function scenarioFromJson(value: unknown): ScenarioDraft {
  return draft(validateScenario(value));
}

export function patchScenario<K extends keyof Omit<ScenarioDraft, "canonical">>(
  scenario: ScenarioDraft,
  key: K,
  value: ScenarioDraft[K],
): ScenarioDraft {
  const canonical: CosmoScenario = structuredClone(scenario.canonical);
  if (key === "id") canonical.meta.id = String(value);
  else if (key === "title") canonical.meta.title = String(value);
  else if (key === "altitudeKm") canonical.environment.altitude_km = Number(value);
  else if (key === "inclinationDeg") canonical.environment.inclination_deg = Number(value);
  else if (key === "earthAngle0Deg") canonical.environment.earth_angle0_deg = Number(value);
  else if (key === "launchStage") canonical.design.launch_stage = value as 1 | 2 | 3;
  else if (key === "islRangeKm") canonical.environment.isl_range_km = Number(value);
  else if (key === "minElevationDeg") canonical.environment.min_elevation_deg = Number(value);
  else if (key === "stepS") canonical.environment.step_s = Number(value);
  else if (key === "horizonS") canonical.environment.horizon_s = Number(value);
  else if (key === "targetAvailability") canonical.environment.target_availability = Number(value);
  return draft(validateScenario(canonical));
}

export function withFailures(
  scenario: ScenarioDraft,
  failures: CosmoScenario["failures"],
): ScenarioDraft {
  return draft(validateScenario({ ...structuredClone(scenario.canonical), failures }));
}
