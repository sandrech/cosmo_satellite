import type {
  GatewayOutageDraft,
  GroundSiteDraft,
  PlaneDraft,
  SatelliteDraft,
  SatelliteOutageDraft,
  ScenarioDraft,
} from "../model/types";

const DEFAULT_PLANES: PlaneDraft[] = [
  { id: "P1", raanDeg: 0, phaseDeg: 0 },
  { id: "P2", raanDeg: 60, phaseDeg: 7.5 },
  { id: "P3", raanDeg: 120, phaseDeg: 15 },
];

const DEFAULT_SATELLITES: SatelliteDraft[] = DEFAULT_PLANES.flatMap(
  (plane, planeIndex) =>
    Array.from({ length: 16 }, (_, slotIndex) => ({
      id: `S${String(planeIndex * 16 + slotIndex + 1).padStart(2, "0")}`,
      planeId: plane.id,
      slotDeg: slotIndex * 22.5,
      launchBatch: (planeIndex + 1) as 1 | 2 | 3,
    })),
);

const DEFAULT_GROUND_SITES: GroundSiteDraft[] = [
  {
    id: "G_MUR",
    name: "Murmansk reference gateway (synthetic installation)",
    role: "gateway",
    latDeg: 68.97,
    lonDeg: 33.07,
  },
  {
    id: "C65",
    name: "Northern terminal 65",
    role: "client",
    latDeg: 65,
    lonDeg: 60,
  },
  {
    id: "C70",
    name: "Northern terminal 70",
    role: "client",
    latDeg: 70,
    lonDeg: 90,
  },
  {
    id: "C72",
    name: "Northern terminal 72",
    role: "client",
    latDeg: 72,
    lonDeg: 130,
  },
];

export const DEFAULT_SCENARIO: ScenarioDraft = {
  schemaVersion: "cosmo-A-1.0",
  id: "01_full_constellation",
  title: "Полная группировка",
  altitudeKm: 550,
  inclinationDeg: 87,
  earthAngle0Deg: 12,
  horizonS: 86400,
  stepS: 120,
  minElevationDeg: 10,
  islRangeKm: 3000,
  targetAvailability: 0.9,
  launchStage: 3,
  planes: DEFAULT_PLANES.map((item) => ({ ...item })),
  satellites: DEFAULT_SATELLITES.map((item) => ({ ...item })),
  groundSites: DEFAULT_GROUND_SITES.map((item) => ({ ...item })),
  failures: [],
  gatewayOutages: [],
};

function finiteNumber(value: unknown, fallback: number) {
  const number = Number(value);
  return Number.isFinite(number) ? number : fallback;
}

function launchStage(value: unknown, fallback: 1 | 2 | 3): 1 | 2 | 3 {
  const number = Number(value);
  return number === 1 || number === 2 || number === 3 ? number : fallback;
}

function planeFromJson(value: any, index: number): PlaneDraft {
  return {
    id: String(value?.id ?? `P${index + 1}`),
    raanDeg: finiteNumber(value?.raan_deg, index * 60),
    phaseDeg: finiteNumber(value?.phase_deg, 0),
  };
}

function satelliteFromJson(value: any, index: number): SatelliteDraft {
  return {
    id: String(value?.id ?? `S${String(index + 1).padStart(2, "0")}`),
    planeId: String(value?.plane_id ?? "P1"),
    slotDeg: finiteNumber(value?.slot_deg, 0),
    launchBatch: launchStage(value?.launch_batch, 1),
  };
}

function groundFromJson(value: any, index: number): GroundSiteDraft {
  const role = value?.role === "gateway" ? "gateway" : "client";
  return {
    id: String(value?.id ?? `G${index + 1}`),
    name: String(value?.name ?? value?.id ?? `Ground ${index + 1}`),
    role,
    latDeg: finiteNumber(value?.lat_deg, 0),
    lonDeg: finiteNumber(value?.lon_deg, 0),
  };
}

function failureFromJson(value: any): SatelliteOutageDraft {
  return {
    satelliteId: String(value?.satellite_id ?? ""),
    startS: finiteNumber(value?.start_s, 0),
    endS: finiteNumber(value?.end_s, 0),
  };
}

function gatewayOutageFromJson(value: any): GatewayOutageDraft {
  return {
    gatewayId: String(value?.gateway_id ?? ""),
    startS: finiteNumber(value?.start_s, 0),
    endS: finiteNumber(value?.end_s, 0),
  };
}

/** Parse the complete cosmo-A-1.0 document without dropping model fields. */
export function scenarioFromJson(value: unknown): ScenarioDraft {
  if (!value || typeof value !== "object") {
    throw new Error("Файл должен содержать JSON-объект");
  }

  const source = value as Record<string, any>;
  const schemaVersion = String(source.schema_version ?? "cosmo-A-1.0");
  if (schemaVersion !== "cosmo-A-1.0") {
    throw new Error(`Неподдерживаемая версия сценария: ${schemaVersion}`);
  }

  const environment = source.environment ?? {};
  const design = source.design ?? {};
  const planesSource = Array.isArray(design.planes) ? design.planes : DEFAULT_PLANES;
  const satellitesSource = Array.isArray(design.satellites)
    ? design.satellites
    : DEFAULT_SATELLITES;
  const groundSource = Array.isArray(source.ground_sites)
    ? source.ground_sites
    : DEFAULT_GROUND_SITES;

  return {
    schemaVersion: "cosmo-A-1.0",
    id: String(source.meta?.id ?? "uploaded_scenario"),
    title: String(source.meta?.title ?? "Загруженный сценарий"),
    altitudeKm: finiteNumber(environment.altitude_km, 550),
    inclinationDeg: finiteNumber(environment.inclination_deg, 87),
    earthAngle0Deg: finiteNumber(environment.earth_angle0_deg, 12),
    horizonS: finiteNumber(environment.horizon_s, 86400),
    stepS: finiteNumber(environment.step_s, 120),
    minElevationDeg: finiteNumber(environment.min_elevation_deg, 10),
    islRangeKm: finiteNumber(environment.isl_range_km, 3000),
    targetAvailability: finiteNumber(environment.target_availability, 0.9),
    launchStage: launchStage(design.launch_stage, 3),
    planes: planesSource.map(planeFromJson),
    satellites: satellitesSource.map(satelliteFromJson),
    groundSites: groundSource.map(groundFromJson),
    failures: Array.isArray(source.failures)
      ? source.failures.map(failureFromJson)
      : [],
    gatewayOutages: Array.isArray(source.gateway_outages)
      ? source.gateway_outages.map(gatewayOutageFromJson)
      : [],
  };
}

/** Serialize the editable model back to the exact backend cosmo-A-1.0 contract. */
export function scenarioToJson(scenario: ScenarioDraft) {
  return {
    schema_version: scenario.schemaVersion,
    meta: {
      id: scenario.id,
      title: scenario.title,
    },
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
