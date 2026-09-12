import type { FrameRequest } from "./client";
import type {
  AvailabilitySegment,
  ClientMetrics,
  EarthStyle,
  GroundSite,
  LayerVisibility,
  NetworkLink,
  PageId,
  RouteView,
  SatelliteFrame,
  ScenarioDraft,
  SimulationFrame,
  Vector3Km,
  ViewMode,
} from "../model/types";

type ScenePointKind = "satellite" | "client" | "gateway";

type ScenePointDto = {
  id: string;
  label: string;
  kind: ScenePointKind;
  position: { x_km: number; y_km: number; z_km: number };
  available: boolean;
  trajectory_group_id?: string | null;
};

type SceneFrameDto = {
  schema_version: "spatial-scene-1.0";
  t_s: number;
  coordinate_frame: "earth_fixed";
  body_radius_km: number;
  points: ScenePointDto[];
  contacts: Array<{ a: string; b: string; distance_km: number; kind: "inter_satellite" | "ground_satellite" }>;
};

type NetworkProjectionDto = {
  schema_version: "spatial-network-1.0";
  t_s: number;
  nodes: Array<{ id: string; kind: ScenePointKind; available: boolean }>;
  edges: Array<{ a: string; b: string; distance_km: number; kind: "inter_satellite" | "ground_satellite" }>;
  ground_observations: unknown[];
  ground_visibility: unknown[];
};

type RouteDto = {
  strategy_id: string;
  source_id: string;
  target_id: string;
  node_ids: string[];
  metrics: { hop_count: number; total_distance_km: number };
};

type ClientAnalysisDto = {
  client_id: string;
  coverage: { visible_satellites: string[]; has_visibility: boolean };
  service: {
    reachable: boolean;
    valid_ingress_satellites: string[];
    reachable_gateways: string[];
    no_route_reason: string | null;
  };
  routing: { selected_route: RouteDto | null; routes: RouteDto[] };
  resilience: {
    satellite_connectivity: { node_disjoint_path_count: number; minimum_cut: string[] };
    critical_satellites: string[];
    survives_any_single_satellite_failure: boolean;
  } | null;
};

type StaticAnalysisDto = {
  schema_version: "static-analysis-2.0";
  clients: ClientAnalysisDto[];
};

export type ModelSnapshotDto = {
  schema_version: "model-snapshot-2.0";
  t_s: number;
  scene: SceneFrameDto;
  network: NetworkProjectionDto;
  analysis: StaticAnalysisDto;
};

type DynamicClientDto = {
  client_id: string;
  samples: Array<{
    t_s: number;
    analysis: {
      coverage: { has_visibility: boolean };
      service: { reachable: boolean; no_route_reason: string | null };
    };
  }>;
  coverage: { visibility: { fraction: number } };
  service: {
    availability: {
      fraction: number;
      unavailable: { maximum_s: number; count: number };
    };
  };
  resilience: { n_minus_one: { fraction: number } };
};

export type DynamicAnalysisDto = {
  schema_version: "dynamic-analysis-2.0";
  grid: { start_s: number; end_s: number; step_s: number; sample_count: number };
  clients: DynamicClientDto[];
};

export type DynamicAnalysisView = {
  grid: DynamicAnalysisDto["grid"];
  metrics: ClientMetrics[];
  availability: Record<string, AvailabilitySegment[]>;
};

function vector(point: ScenePointDto): Vector3Km {
  return { xKm: point.position.x_km, yKm: point.position.y_km, zKm: point.position.z_km };
}

function ecefToLatLon(position: Vector3Km) {
  const horizontal = Math.hypot(position.xKm, position.yKm);
  return {
    latDeg: (Math.atan2(position.zKm, horizontal) * 180) / Math.PI,
    lonDeg: (Math.atan2(position.yKm, position.xKm) * 180) / Math.PI,
  };
}

function routeEdges(route: string[]) {
  return new Set(route.slice(0, -1).map((id, index) => [id, route[index + 1]].sort().join("::")));
}

function object(value: unknown): value is Record<string, unknown> {
  return Boolean(value) && typeof value === "object" && !Array.isArray(value);
}

export function isModelSnapshotDto(value: unknown): value is ModelSnapshotDto {
  if (!object(value) || value.schema_version !== "model-snapshot-2.0") return false;
  const scene = value.scene;
  const network = value.network;
  const analysis = value.analysis;
  if (!object(scene) || scene.schema_version !== "spatial-scene-1.0" || !Array.isArray(scene.points) || !Array.isArray(scene.contacts)) return false;
  if (!object(network) || network.schema_version !== "spatial-network-1.0" || !Array.isArray(network.nodes) || !Array.isArray(network.edges)) return false;
  if (!object(analysis) || analysis.schema_version !== "static-analysis-2.0" || !Array.isArray(analysis.clients)) return false;
  return typeof value.t_s === "number" && scene.t_s === value.t_s && network.t_s === value.t_s;
}

export function isDynamicAnalysisDto(value: unknown): value is DynamicAnalysisDto {
  return object(value) && value.schema_version === "dynamic-analysis-2.0" && object(value.grid) && Array.isArray(value.clients);
}

function routeView(route: RouteDto): RouteView {
  return {
    strategyId: route.strategy_id,
    nodeIds: [...route.node_ids],
    hopCount: route.metrics.hop_count,
    totalDistanceKm: route.metrics.total_distance_km,
  };
}

export function adaptModelSnapshot(bundle: ModelSnapshotDto, request: FrameRequest): SimulationFrame {
  const { scene, network, analysis } = bundle;
  const selectedClient = analysis.clients.find((client) => client.client_id === request.clientId);
  if (!selectedClient) throw new Error(`Backend response does not contain requested client ${request.clientId}`);

  const route = selectedClient.routing.selected_route?.node_ids ?? [];
  const routeEdgeIds = routeEdges(route);
  const availabilityByNode = new Map(network.nodes.map((node) => [node.id, node.available]));
  const satelliteSpec = new Map(request.scenario.canonical.design.satellites.map((item) => [item.id, item]));
  const groundSpec = new Map(request.scenario.canonical.ground_sites.map((item) => [item.id, item]));

  const satellites: SatelliteFrame[] = scene.points
    .filter((point) => point.kind === "satellite")
    .map((point) => {
      const spec = satelliteSpec.get(point.id);
      if (!spec) throw new Error(`Unknown satellite ${point.id} in backend response`);
      const active = availabilityByNode.get(point.id) ?? point.available;
      const notLaunched = spec.launch_batch > request.scenario.launchStage;
      const failed = request.scenario.canonical.failures.some(
        (failure) => failure.satellite_id === point.id && failure.start_s <= scene.t_s && scene.t_s < failure.end_s,
      );
      return {
        id: point.id,
        planeId: point.trajectory_group_id ?? spec.plane_id,
        active,
        failed,
        inactiveReason: active ? null : notLaunched ? "not-launched" : failed ? "failed" : null,
        launchBatch: spec.launch_batch,
        position: vector(point),
      };
    });

  const groundSites: GroundSite[] = scene.points
    .filter((point) => point.kind === "client" || point.kind === "gateway")
    .map((point) => {
      const spec = groundSpec.get(point.id);
      const position = vector(point);
      const fallback = ecefToLatLon(position);
      return {
        id: point.id,
        name: spec?.name ?? (point.label || point.id),
        role: point.kind === "gateway" ? "gateway" : "client",
        latDeg: spec?.lat_deg ?? fallback.latDeg,
        lonDeg: spec?.lon_deg ?? fallback.lonDeg,
        available: availabilityByNode.get(point.id) ?? point.available,
        position,
      };
    });

  const links: NetworkLink[] = network.edges.map((edge, index) => ({
    id: `${edge.a}-${edge.b}-${index}`,
    sourceId: edge.a,
    targetId: edge.b,
    kind: edge.kind === "inter_satellite" ? "isl" : "ground",
    distanceKm: edge.distance_km,
    inRoute: routeEdgeIds.has([edge.a, edge.b].sort().join("::")),
  }));

  const positionBySatellite = new Map(satellites.map((satellite) => [satellite.id, satellite.position]));
  const orbits = request.scenario.canonical.design.planes.map((plane) => ({
    planeId: plane.id,
    positions: request.scenario.canonical.design.satellites
      .filter((satellite) => satellite.plane_id === plane.id)
      .sort((left, right) => left.slot_deg - right.slot_deg)
      .map((satellite) => positionBySatellite.get(satellite.id))
      .filter((position): position is Vector3Km => Boolean(position)),
  })).map((orbit) => ({
    ...orbit,
    positions: orbit.positions.length > 1 ? [...orbit.positions, orbit.positions[0]] : orbit.positions,
  }));

  const reachableClients = analysis.clients.filter((client) => client.service.reachable).length;
  return {
    source: "backend",
    tS: scene.t_s,
    horizonS: request.scenario.horizonS,
    stepS: request.scenario.stepS,
    bodyRadiusKm: scene.body_radius_km,
    satellites,
    groundSites,
    links,
    route,
    routes: selectedClient.routing.routes.map(routeView),
    orbits,
    metrics: [],
    availability: Object.fromEntries(analysis.clients.map((client) => [client.client_id, []])),
    outageReason: selectedClient.service.no_route_reason,
    reachableClients,
    clientCount: analysis.clients.length,
    currentConnectivity: selectedClient.resilience?.satellite_connectivity.node_disjoint_path_count ?? null,
    survivesAnySingleSatelliteFailure: selectedClient.resilience?.survives_any_single_satellite_failure ?? null,
  };
}

export function adaptDynamicAnalysis(dto: DynamicAnalysisDto): DynamicAnalysisView {
  const metrics: ClientMetrics[] = dto.clients.map((client) => ({
    clientId: client.client_id,
    visibility: client.coverage.visibility.fraction * 100,
    availability: client.service.availability.fraction * 100,
    maxOutageMinutes: client.service.availability.unavailable.maximum_s / 60,
    outages: client.service.availability.unavailable.count,
    nMinusOne: client.resilience.n_minus_one.fraction * 100,
  }));

  const availability = Object.fromEntries(dto.clients.map((client) => {
    const segments: AvailabilitySegment[] = [];
    for (const sample of client.samples) {
      const state: AvailabilitySegment["state"] = sample.analysis.service.reachable
        ? "path"
        : sample.analysis.coverage.has_visibility
          ? "visible-only"
          : "no-satellite";
      const previous = segments[segments.length - 1];
      if (previous && previous.state === state && previous.to === sample.t_s) previous.to += dto.grid.step_s;
      else segments.push({ from: sample.t_s, to: sample.t_s + dto.grid.step_s, state });
    }
    return [client.client_id, segments];
  }));

  return { grid: dto.grid, metrics, availability };
}

export function applyDynamicAnalysis(frame: SimulationFrame, analysis: DynamicAnalysisView | null): SimulationFrame {
  if (!analysis) return frame;
  return { ...frame, metrics: analysis.metrics, availability: analysis.availability };
}

export type FrontendWorkspaceStateDto = {
  schema_version: "frontend-workspace-state-1.0";
  saved_at: string;
  scenario: ScenarioDraft;
  runtime: { t_s: number; client_id: string; selected_id: string | null };
  viewport: { page: PageId; view_mode: ViewMode; earth_style: EarthStyle };
  layers: LayerVisibility;
  hidden_node_ids: string[];
  frame_snapshot: SimulationFrame | null;
};

export type FrontendWorkspaceStateInput = {
  scenario: ScenarioDraft;
  tS: number;
  clientId: string;
  selectedId: string | null;
  page: PageId;
  viewMode: ViewMode;
  earthStyle: EarthStyle;
  layers: LayerVisibility;
  hiddenNodeIds: string[];
  frame: SimulationFrame | null;
};

export function buildFrontendWorkspaceState(state: FrontendWorkspaceStateInput): FrontendWorkspaceStateDto {
  return {
    schema_version: "frontend-workspace-state-1.0",
    saved_at: new Date().toISOString(),
    scenario: structuredClone(state.scenario),
    runtime: { t_s: state.tS, client_id: state.clientId, selected_id: state.selectedId },
    viewport: { page: state.page, view_mode: state.viewMode, earth_style: state.earthStyle },
    layers: { ...state.layers },
    hidden_node_ids: [...state.hiddenNodeIds],
    frame_snapshot: state.frame,
  };
}

export function isFrontendWorkspaceState(value: unknown): value is FrontendWorkspaceStateDto {
  if (!object(value)) return false;
  return value.schema_version === "frontend-workspace-state-1.0" && object(value.scenario) && object(value.runtime) && object(value.viewport) && object(value.layers) && Array.isArray(value.hidden_node_ids);
}
