import type {
  CosmoScenario,
  GatewayOutageDraft,
  GroundSiteDraft,
  PlaneDraft,
  SatelliteDraft,
  SatelliteOutageDraft,
  ScenarioDraft,
} from "../model/types";

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

function stringValue(value: unknown, path: string) {
  if (typeof value !== "string" || !value.trim()) {
    throw new Error(`${path} должен быть непустой строкой`);
  }
  return value;
}

function numberValue(value: unknown, path: string) {
  if (typeof value !== "number" || !Number.isFinite(value)) {
    throw new Error(`${path} должен быть конечным числом`);
  }
  return value;
}

function integerValue(value: unknown, path: string) {
  const result = numberValue(value, path);
  if (!Number.isInteger(result)) throw new Error(`${path} должен быть целым числом`);
  return result;
}

function validateCanonicalScenario(value: unknown): CosmoScenario {
  const root = object(value, "scenario");
  if (root.schema_version !== "cosmo-A-1.0") {
    throw new Error("schema_version должен быть cosmo-A-1.0");
  }

  const meta = object(root.meta, "meta");
  const environment = object(root.environment, "environment");
  const design = object(root.design, "design");

  const horizon = integerValue(environment.horizon_s, "environment.horizon_s");
  const step = integerValue(environment.step_s, "environment.step_s");
  if (!(step > 0 && horizon >= step && horizon <= 172800 && horizon % step === 0)) {
    throw new Error("environment: некорректная расчётная сетка");
  }

  const altitude = numberValue(environment.altitude_km, "environment.altitude_km");
  const inclination = numberValue(environment.inclination_deg, "environment.inclination_deg");
  const earthAngle0 = numberValue(environment.earth_angle0_deg, "environment.earth_angle0_deg");
  const minElevation = numberValue(environment.min_elevation_deg, "environment.min_elevation_deg");
  const islRange = numberValue(environment.isl_range_km, "environment.isl_range_km");
  const targetAvailability = numberValue(environment.target_availability, "environment.target_availability");

  if (altitude < 200 || altitude > 1200) throw new Error("altitude_km должен быть в [200, 1200]");
  if (!(inclination > 0 && inclination <= 180)) throw new Error("inclination_deg должен быть в (0, 180]");
  if (!(minElevation >= 0 && minElevation < 90)) throw new Error("min_elevation_deg должен быть в [0, 90)");
  if (!(islRange > 0 && islRange <= 10000)) throw new Error("isl_range_km должен быть в (0, 10000]");
  if (!(targetAvailability >= 0 && targetAvailability <= 1)) {
    throw new Error("target_availability должен быть в [0, 1]");
  }

  const launchStage = integerValue(design.launch_stage, "design.launch_stage");
  if (launchStage !== 1 && launchStage !== 2 && launchStage !== 3) {
    throw new Error("design.launch_stage должен быть 1, 2 или 3");
  }

  const planes = array(design.planes, "design.planes").map((raw, index) => {
    const item = object(raw, `design.planes[${index}]`);
    const raan = numberValue(item.raan_deg, `design.planes[${index}].raan_deg`);
    const phase = numberValue(item.phase_deg, `design.planes[${index}].phase_deg`);
    if (!(raan >= 0 && raan < 360 && phase >= 0 && phase < 360)) {
      throw new Error(`design.planes[${index}]: углы должны быть в [0, 360)`);
    }
    return {
      id: stringValue(item.id, `design.planes[${index}].id`),
      raan_deg: raan,
      phase_deg: phase,
    };
  });
  if (!planes.length || new Set(planes.map((item) => item.id)).size !== planes.length) {
    throw new Error("ID плоскостей должны быть уникальны и список не должен быть пустым");
  }
  const planeIds = new Set(planes.map((item) => item.id));

  const satellites = array(design.satellites, "design.satellites").map((raw, index) => {
    const item = object(raw, `design.satellites[${index}]`);
    const id = stringValue(item.id, `design.satellites[${index}].id`);
    const planeId = stringValue(item.plane_id, `design.satellites[${index}].plane_id`);
    const slot = numberValue(item.slot_deg, `design.satellites[${index}].slot_deg`);
    const batch = integerValue(item.launch_batch, `design.satellites[${index}].launch_batch`);
    if (!planeIds.has(planeId)) throw new Error(`Неизвестная плоскость ${planeId} у спутника ${id}`);
    if (!(slot >= 0 && slot < 360)) throw new Error(`slot_deg спутника ${id} должен быть в [0, 360)`);
    if (batch !== 1 && batch !== 2 && batch !== 3) {
      throw new Error(`launch_batch спутника ${id} должен быть 1, 2 или 3`);
    }
    return { id, plane_id: planeId, slot_deg: slot, launch_batch: batch as 1 | 2 | 3 };
  });
  if (!satellites.length || new Set(satellites.map((item) => item.id)).size !== satellites.length) {
    throw new Error("ID спутников должны быть уникальны и список не должен быть пустым");
  }
  const satelliteIds = new Set(satellites.map((item) => item.id));

  const groundSites = array(root.ground_sites, "ground_sites").map((raw, index) => {
    const item = object(raw, `ground_sites[${index}]`);
    const role = stringValue(item.role, `ground_sites[${index}].role`);
    if (role !== "client" && role !== "gateway") {
      throw new Error(`ground_sites[${index}].role должен быть client или gateway`);
    }
    const lat = numberValue(item.lat_deg, `ground_sites[${index}].lat_deg`);
    const lon = numberValue(item.lon_deg, `ground_sites[${index}].lon_deg`);
    if (lat < -90 || lat > 90 || lon < -180 || lon > 180) {
      throw new Error(`ground_sites[${index}] имеет некорректные координаты`);
    }
    return {
      id: stringValue(item.id, `ground_sites[${index}].id`),
      name: stringValue(item.name, `ground_sites[${index}].name`),
      role: role as "client" | "gateway",
      lat_deg: lat,
      lon_deg: lon,
    };
  });
  const groundIds = new Set(groundSites.map((item) => item.id));
  if (groundIds.size !== groundSites.length) throw new Error("ID наземных пунктов должны быть уникальны");
  if (!groundSites.some((item) => item.role === "client")) throw new Error("Нужен хотя бы один client");
  if (!groundSites.some((item) => item.role === "gateway")) throw new Error("Нужен хотя бы один gateway");

  const failures = array(root.failures, "failures").map((raw, index) => {
    const item = object(raw, `failures[${index}]`);
    const satelliteId = stringValue(item.satellite_id, `failures[${index}].satellite_id`);
    const startS = numberValue(item.start_s, `failures[${index}].start_s`);
    const endS = numberValue(item.end_s, `failures[${index}].end_s`);
    if (!satelliteIds.has(satelliteId)) throw new Error(`failures[${index}]: неизвестный спутник ${satelliteId}`);
    if (!(0 <= startS && startS < endS && endS <= horizon)) throw new Error(`failures[${index}]: некорректный интервал`);
    return { satellite_id: satelliteId, start_s: startS, end_s: endS };
  });

  const gatewayIds = new Set(groundSites.filter((item) => item.role === "gateway").map((item) => item.id));
  const gatewayOutages = array(root.gateway_outages, "gateway_outages").map((raw, index) => {
    const item = object(raw, `gateway_outages[${index}]`);
    const gatewayId = stringValue(item.gateway_id, `gateway_outages[${index}].gateway_id`);
    const startS = numberValue(item.start_s, `gateway_outages[${index}].start_s`);
    const endS = numberValue(item.end_s, `gateway_outages[${index}].end_s`);
    if (!gatewayIds.has(gatewayId)) throw new Error(`gateway_outages[${index}]: неизвестный gateway ${gatewayId}`);
    if (!(0 <= startS && startS < endS && endS <= horizon)) throw new Error(`gateway_outages[${index}]: некорректный интервал`);
    return { gateway_id: gatewayId, start_s: startS, end_s: endS };
  });

  return {
    schema_version: "cosmo-A-1.0",
    meta: {
      id: stringValue(meta.id, "meta.id"),
      title: stringValue(meta.title, "meta.title"),
    },
    environment: {
      altitude_km: altitude,
      inclination_deg: inclination,
      earth_angle0_deg: earthAngle0,
      horizon_s: horizon,
      step_s: step,
      min_elevation_deg: minElevation,
      isl_range_km: islRange,
      target_availability: targetAvailability,
    },
    design: {
      launch_stage: launchStage,
      planes,
      satellites,
    },
    ground_sites: groundSites,
    failures,
    gateway_outages: gatewayOutages,
  };
}

function planeFromCanonical(value: CosmoScenario["design"]["planes"][number]): PlaneDraft {
  return { id: value.id, raanDeg: value.raan_deg, phaseDeg: value.phase_deg };
}

function satelliteFromCanonical(value: CosmoScenario["design"]["satellites"][number]): SatelliteDraft {
  return {
    id: value.id,
    planeId: value.plane_id,
    slotDeg: value.slot_deg,
    launchBatch: value.launch_batch,
  };
}

function groundFromCanonical(value: CosmoScenario["ground_sites"][number]): GroundSiteDraft {
  return {
    id: value.id,
    name: value.name,
    role: value.role,
    latDeg: value.lat_deg,
    lonDeg: value.lon_deg,
  };
}

function failureFromCanonical(value: CosmoScenario["failures"][number]): SatelliteOutageDraft {
  return { satelliteId: value.satellite_id, startS: value.start_s, endS: value.end_s };
}

function gatewayOutageFromCanonical(value: CosmoScenario["gateway_outages"][number]): GatewayOutageDraft {
  return { gatewayId: value.gateway_id, startS: value.start_s, endS: value.end_s };
}

function draftFromCanonical(canonical: CosmoScenario): ScenarioDraft {
  return {
    schemaVersion: "cosmo-A-1.0",
    id: canonical.meta.id,
    title: canonical.meta.title,
    altitudeKm: canonical.environment.altitude_km,
    inclinationDeg: canonical.environment.inclination_deg,
    earthAngle0Deg: canonical.environment.earth_angle0_deg,
    horizonS: canonical.environment.horizon_s,
    stepS: canonical.environment.step_s,
    minElevationDeg: canonical.environment.min_elevation_deg,
    islRangeKm: canonical.environment.isl_range_km,
    targetAvailability: canonical.environment.target_availability,
    launchStage: canonical.design.launch_stage,
    planes: canonical.design.planes.map(planeFromCanonical),
    satellites: canonical.design.satellites.map(satelliteFromCanonical),
    groundSites: canonical.ground_sites.map(groundFromCanonical),
    failures: canonical.failures.map(failureFromCanonical),
    gatewayOutages: canonical.gateway_outages.map(gatewayOutageFromCanonical),
  };
}

export function scenarioToJson(scenario: ScenarioDraft): CosmoScenario {
  return {
    schema_version: scenario.schemaVersion,
    meta: { id: scenario.id, title: scenario.title },
    environment: {
      altitude_km: scenario.altitudeKm,
      inclination_deg: scenario.inclinationDeg,
      earth_angle0_deg: scenario.earthAngle0Deg,
      horizon_s: scenario.horizonS,
      step_s: scenario.stepS,
      min_elevation_deg: scenario.minElevationDeg,
      isl_range_km: scenario.islRangeKm,
      target_availability: scenario.targetAvailability,
    },
    design: {
      launch_stage: scenario.launchStage,
      planes: scenario.planes.map((plane) => ({
        id: plane.id,
        raan_deg: plane.raanDeg,
        phase_deg: plane.phaseDeg,
      })),
      satellites: scenario.satellites.map((satellite) => ({
        id: satellite.id,
        plane_id: satellite.planeId,
        slot_deg: satellite.slotDeg,
        launch_batch: satellite.launchBatch,
      })),
    },
    ground_sites: scenario.groundSites.map((site) => ({
      id: site.id,
      name: site.name,
      role: site.role,
      lat_deg: site.latDeg,
      lon_deg: site.lonDeg,
    })),
    failures: scenario.failures.map((failure) => ({
      satellite_id: failure.satelliteId,
      start_s: failure.startS,
      end_s: failure.endS,
    })),
    gateway_outages: scenario.gatewayOutages.map((outage) => ({
      gateway_id: outage.gatewayId,
      start_s: outage.startS,
      end_s: outage.endS,
    })),
  };
}

export function scenarioFromJson(value: unknown): ScenarioDraft {
  return draftFromCanonical(validateCanonicalScenario(value));
}

export function validateScenarioDraft(scenario: ScenarioDraft): ScenarioDraft {
  return scenarioFromJson(scenarioToJson(scenario));
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

export const DEFAULT_SCENARIO: ScenarioDraft = draftFromCanonical(defaultCanonical);
