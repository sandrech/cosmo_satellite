import type {
  AvailabilitySegment,
  ClientMetrics,
  ModelRunData,
  NetworkLink,
  OrbitPath,
  RouteDetails,
  RoutingStrategyId,
  RoutingStrategyOption,
  ScenarioDraft,
  SimulationFrame,
  Vector3Km,
} from "../model/types";
import { scenarioFromJson } from "./scenarios";

type Vec3Dto = { x_km: number; y_km: number; z_km: number };
type ScenePointDto = {
  id: string;
  label: string;
  kind: "satellite" | "client" | "gateway";
  position: Vec3Dto;
  available: boolean;
  trajectory_group_id?: string | null;
};
type SceneDto = {
  schema_version: "spatial-scene-1.0";
  t_s: number;
  body_radius_km: number;
  points: ScenePointDto[];
  contacts: Array<{
    a: string;
    b: string;
    distance_km: number;
    kind: "inter_satellite" | "ground_satellite";
  }>;
};
type NetworkDto = {
  schema_version: "spatial-network-1.0";
  t_s: number;
  nodes: Array<{ id: string; kind: ScenePointDto["kind"]; available: boolean }>;
  edges: Array<{
    a: string;
    b: string;
    distance_km: number;
    kind: "inter_satellite" | "ground_satellite";
  }>;
};
type RouteDto = {
  strategy_id: string;
  source_id: string;
  target_id: string;
  node_ids: string[];
  metrics: { hop_count: number; total_distance_km: number };
  quality: {
    dimensions: Array<{
      name: string;
      value: number;
      direction: "maximize" | "minimize";
    }>;
  };
};
type ClientSnapshotDto = {
  client_id: string;
  coverage: { visible_satellites: string[]; has_visibility: boolean };
  service: {
    reachable: boolean;
    valid_ingress_satellites: string[];
    reachable_gateways: string[];
    no_route_reason: string | null;
  };
  routing: { selected_route: RouteDto | null; routes: RouteDto[] };
  resilience?: {
    satellite_connectivity: { node_disjoint_path_count: number; minimum_cut: string[] };
    critical_satellites: string[];
    survives_any_single_satellite_failure: boolean;
  } | null;
};
type StaticAnalysisDto = {
  schema_version: "static-analysis-2.0";
  clients: ClientSnapshotDto[];
};
type SnapshotDto = {
  schema_version: "model-snapshot-2.0";
  t_s: number;
  scene: SceneDto;
  network: NetworkDto;
  analysis: StaticAnalysisDto;
};
type TraceDto = {
  schema_version: "model-trace-2.0";
  sampling: { start_s: number; end_s: number; step_s: number };
  frames: SnapshotDto[];
};
type IntervalDto = { start_s: number; end_s: number; duration_s: number };
type DynamicClientDto = {
  client_id: string;
  samples: Array<{ t_s: number; analysis: ClientSnapshotDto }>;
  coverage: { visibility: { fraction: number } };
  service: {
    availability: {
      fraction: number;
      unavailable: { intervals: IntervalDto[]; maximum_s: number; count: number };
    };
  };
  resilience?: { n_minus_one: { fraction: number } };
};
type DynamicAnalysisDto = {
  schema_version: "dynamic-analysis-2.0";
  grid: { start_s: number; end_s: number; step_s: number; sample_count: number };
  clients: DynamicClientDto[];
};

export type ModelRunResponseDto = {
  schema_version: "cosmo-model-run-1.0";
  scenario: unknown;
  routing_strategies: RoutingStrategyOption[];
  primary_route_strategy_id: RoutingStrategyId;
  trace: TraceDto;
  dynamic_analysis: DynamicAnalysisDto;
};

function isObject(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object";
}

export function isModelRunResponse(value: unknown): value is ModelRunResponseDto {
  if (!isObject(value)) return false;
  const candidate = value as Partial<ModelRunResponseDto>;
  return (
    candidate.schema_version === "cosmo-model-run-1.0" &&
    isObject(candidate.trace) &&
    Array.isArray((candidate.trace as TraceDto).frames) &&
    isObject(candidate.dynamic_analysis)
  );
}

function vector(value: Vec3Dto): Vector3Km {
  return { xKm: value.x_km, yKm: value.y_km, zKm: value.z_km };
}

function routeDetails(route: RouteDto | null | undefined): RouteDetails | null {
  if (!route) return null;
  return {
    strategyId: route.strategy_id,
    sourceId: route.source_id,
    targetId: route.target_id,
    nodeIds: [...route.node_ids],
    hopCount: route.metrics.hop_count,
    totalDistanceKm: route.metrics.total_distance_km,
    quality: route.quality.dimensions.map((item) => ({ ...item })),
  };
}

function routeEdgeKeys(route: string[]) {
  return new Set(
    route.slice(0, -1).map((id, index) =>
      [id, route[index + 1]].sort().join("::"),
    ),
  );
}

function availabilitySegments(client: DynamicClientDto): AvailabilitySegment[] {
  if (!client.samples.length) return [];
  const step = client.samples.length > 1
    ? client.samples[1].t_s - client.samples[0].t_s
    : 0;
  const stateAt = (sample: DynamicClientDto["samples"][number]): AvailabilitySegment["state"] => {
    if (sample.analysis.service.reachable) return "path";
    if (sample.analysis.coverage.has_visibility) return "visible-only";
    return "no-satellite";
  };

  const result: AvailabilitySegment[] = [];
  let start = client.samples[0].t_s;
  let current = stateAt(client.samples[0]);
  for (let index = 1; index < client.samples.length; index += 1) {
    const next = stateAt(client.samples[index]);
    if (next !== current) {
      result.push({ from: start, to: client.samples[index].t_s, state: current });
      start = client.samples[index].t_s;
      current = next;
    }
  }
  const last = client.samples[client.samples.length - 1].t_s;
  result.push({ from: start, to: last + Math.max(step, 1), state: current });
  return result;
}

function dynamicMetrics(dynamic: DynamicAnalysisDto): ClientMetrics[] {
  return dynamic.clients.map((client) => ({
    clientId: client.client_id,
    visibility: client.coverage.visibility.fraction * 100,
    availability: client.service.availability.fraction * 100,
    maxOutageMinutes: client.service.availability.unavailable.maximum_s / 60,
    outages: client.service.availability.unavailable.count,
    ...(client.resilience ? { nMinusOne: client.resilience.n_minus_one.fraction * 100 } : {}),
  }));
}

function radians(value: number) {
  return (value * Math.PI) / 180;
}

/** Display-only orbit curves derived from the exact scenario plane parameters. */
function buildOrbitPaths(scenario: ScenarioDraft, tS: number): OrbitPath[] {
  const earthRadius = 6371;
  const radius = earthRadius + scenario.altitudeKm;
  const mu = 398600.435507;
  const meanMotion = Math.sqrt(mu / Math.pow(radius, 3));
  const earthRotation = (2 * Math.PI) / 86164.09054;
  const inclination = radians(scenario.inclinationDeg);
  const earthAngle = radians(scenario.earthAngle0Deg) + earthRotation * tS;

  return scenario.planes.map((plane) => {
    const raan = radians(plane.raanDeg);
    const phase = radians(plane.phaseDeg) + meanMotion * tS;
    const positions = Array.from({ length: 145 }, (_, index) => {
      const u = phase + (2 * Math.PI * index) / 144;
      const xi = radius * (
        Math.cos(raan) * Math.cos(u) -
        Math.sin(raan) * Math.sin(u) * Math.cos(inclination)
      );
      const yi = radius * (
        Math.sin(raan) * Math.cos(u) +
        Math.cos(raan) * Math.sin(u) * Math.cos(inclination)
      );
      const z = radius * Math.sin(u) * Math.sin(inclination);
      return {
        xKm: xi * Math.cos(earthAngle) + yi * Math.sin(earthAngle),
        yKm: -xi * Math.sin(earthAngle) + yi * Math.cos(earthAngle),
        zKm: z,
      };
    });
    return { planeId: plane.id, positions };
  });
}

export function toModelRunData(payload: ModelRunResponseDto): ModelRunData {
  return {
    schemaVersion: "cosmo-model-run-1.0",
    scenario: scenarioFromJson(payload.scenario),
    routingStrategies: payload.routing_strategies,
    primaryRoutingStrategyId: payload.primary_route_strategy_id,
    trace: payload.trace,
    dynamicAnalysis: payload.dynamic_analysis,
    raw: payload,
  };
}

function nearestSnapshot(trace: TraceDto, tS: number): SnapshotDto | null {
  if (!trace.frames.length) return null;
  const step = trace.sampling.step_s;
  const rawIndex = Math.round((tS - trace.sampling.start_s) / step);
  const index = Math.min(Math.max(rawIndex, 0), trace.frames.length - 1);
  return trace.frames[index];
}

export function frameFromModelRun(
  run: ModelRunData,
  tS: number,
  clientId: string,
  routingStrategyId: RoutingStrategyId,
): SimulationFrame | null {
  const trace = run.trace as TraceDto;
  const dynamic = run.dynamicAnalysis as DynamicAnalysisDto;
  const snapshot = nearestSnapshot(trace, tS);
  if (!snapshot) return null;

  const scenario = run.scenario;
  const client =
    snapshot.analysis.clients.find((item) => item.client_id === clientId) ??
    snapshot.analysis.clients[0];
  const routeMap: Record<string, RouteDetails | null> = {};
  for (const route of client?.routing.routes ?? []) {
    routeMap[route.strategy_id] = routeDetails(route);
  }
  for (const option of run.routingStrategies) {
    if (!(option.id in routeMap)) routeMap[option.id] = null;
  }
  const selectedRoute = routeMap[routingStrategyId] ?? null;
  const route = selectedRoute?.nodeIds ?? [];
  const routeEdges = routeEdgeKeys(route);
  const satelliteDrafts = new Map(scenario.satellites.map((item) => [item.id, item]));
  const groundDrafts = new Map(scenario.groundSites.map((item) => [item.id, item]));
  const networkAvailability = new Map(snapshot.network.nodes.map((item) => [item.id, item.available]));

  const satellites = snapshot.scene.points
    .filter((point) => point.kind === "satellite")
    .map((point) => {
      const spec = satelliteDrafts.get(point.id);
      const available = networkAvailability.get(point.id) ?? point.available;
      const deployed = (spec?.launchBatch ?? 1) <= scenario.launchStage;
      return {
        id: point.id,
        planeId: spec?.planeId ?? point.trajectory_group_id ?? "Orbit",
        active: available,
        failed: deployed && !available,
        inactiveReason: available ? null : deployed ? "failed" as const : "not-launched" as const,
        launchBatch: spec?.launchBatch ?? 1,
        position: vector(point.position),
      };
    });

  const groundSites = snapshot.scene.points
    .filter((point) => point.kind === "client" || point.kind === "gateway")
    .map((point) => {
      const spec = groundDrafts.get(point.id);
      return {
        id: point.id,
        name: spec?.name ?? point.label ?? point.id,
        role: point.kind === "gateway" ? "gateway" as const : "client" as const,
        latDeg: spec?.latDeg ?? 0,
        lonDeg: spec?.lonDeg ?? 0,
        available: networkAvailability.get(point.id) ?? point.available,
        position: vector(point.position),
      };
    });

  const links: NetworkLink[] = snapshot.network.edges.map((edge, index) => ({
    id: `${edge.a}-${edge.b}-${index}`,
    sourceId: edge.a,
    targetId: edge.b,
    kind: edge.kind === "inter_satellite" ? "isl" : "ground",
    distanceKm: edge.distance_km,
    inRoute: routeEdges.has([edge.a, edge.b].sort().join("::")),
  }));

  const availability = Object.fromEntries(
    dynamic.clients.map((item) => [item.client_id, availabilitySegments(item)]),
  );

  return {
    source: "backend",
    tS: snapshot.t_s,
    horizonS: scenario.horizonS,
    stepS: scenario.stepS,
    bodyRadiusKm: snapshot.scene.body_radius_km,
    satellites,
    groundSites,
    links,
    route,
    routeDetails: selectedRoute,
    routesByStrategy: routeMap,
    orbits: buildOrbitPaths(scenario, snapshot.t_s),
    metrics: dynamicMetrics(dynamic),
    availability,
    outageReason: client?.service.no_route_reason ?? null,
    reachableClients: snapshot.analysis.clients.filter((item) => item.service.reachable).length,
    clientCount: snapshot.analysis.clients.length,
    currentConnectivity: client?.resilience?.satellite_connectivity.node_disjoint_path_count ?? null,
    survivesAnySingleSatelliteFailure: client?.resilience?.survives_any_single_satellite_failure ?? null,
  };
}
