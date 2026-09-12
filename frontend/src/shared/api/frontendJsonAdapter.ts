import type { FrameRequest } from "./client";
import type {
  EarthStyle,
  GroundSite,
  LayerVisibility,
  NetworkLink,
  PageId,
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
  contacts: Array<{
    a: string;
    b: string;
    distance_km: number;
    kind: "inter_satellite" | "ground_satellite";
  }>;
};

type NetworkProjectionDto = {
  schema_version: "spatial-network-1.0";
  t_s: number;
  nodes: Array<{ id: string; kind: ScenePointKind; available: boolean }>;
  edges: Array<{
    a: string;
    b: string;
    distance_km: number;
    kind: "inter_satellite" | "ground_satellite";
  }>;
};

type RouteDto = {
  node_ids: string[];
};

type ClientAnalysisDto = {
  client_id: string;
  coverage: { visible_satellites: string[]; has_visibility: boolean };
  service: {
    reachable: boolean;
    no_route_reason: string | null;
  };
  routing: { selected_route: RouteDto | null };
};

type StaticAnalysisDto = {
  schema_version: "static-analysis-1.0";
  clients: ClientAnalysisDto[];
};

export type FrontendFrameBundleDto = {
  schema_version?: "frontend-frame-1.0";
  scene: SceneFrameDto;
  network?: NetworkProjectionDto | null;
  analysis?: StaticAnalysisDto | null;
};

function vector(point: ScenePointDto): Vector3Km {
  return {
    xKm: point.position.x_km,
    yKm: point.position.y_km,
    zKm: point.position.z_km,
  };
}

function ecefToLatLon(position: Vector3Km) {
  const horizontal = Math.hypot(position.xKm, position.yKm);
  return {
    latDeg: (Math.atan2(position.zKm, horizontal) * 180) / Math.PI,
    lonDeg: (Math.atan2(position.yKm, position.xKm) * 180) / Math.PI,
  };
}

function routeEdges(route: string[]) {
  return new Set(
    route.slice(0, -1).map((id, index) => {
      const next = route[index + 1];
      return [id, next].sort().join("::");
    }),
  );
}

function isSceneFrame(value: unknown): value is SceneFrameDto {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<SceneFrameDto>;
  return (
    candidate.schema_version === "spatial-scene-1.0" &&
    Array.isArray(candidate.points) &&
    Array.isArray(candidate.contacts)
  );
}

export function isFrontendFrameBundle(value: unknown): value is FrontendFrameBundleDto {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<FrontendFrameBundleDto>;
  return isSceneFrame(candidate.scene);
}

export function adaptFrontendFrameBundle(
  bundle: FrontendFrameBundleDto,
  request: FrameRequest,
): SimulationFrame {
  const { scene, network, analysis } = bundle;
  const selectedClient =
    analysis?.clients.find((client) => client.client_id === request.clientId) ??
    analysis?.clients[0];
  const route = selectedClient?.routing.selected_route?.node_ids ?? [];
  const routeEdgeIds = routeEdges(route);
  const availabilityByNode = new Map(
    network?.nodes.map((node) => [node.id, node.available]) ?? [],
  );

  const satellites: SatelliteFrame[] = scene.points
    .filter((point) => point.kind === "satellite")
    .map((point) => ({
      id: point.id,
      planeId: point.trajectory_group_id ?? "Orbit",
      active: availabilityByNode.get(point.id) ?? point.available,
      failed: !(availabilityByNode.get(point.id) ?? point.available),
      launchBatch: 1,
      position: vector(point),
    }));

  const groundSites: GroundSite[] = scene.points
    .filter((point) => point.kind === "client" || point.kind === "gateway")
    .map((point) => {
      const coordinates = ecefToLatLon(vector(point));
      return {
        id: point.id,
        name: point.label || point.id,
        role: point.kind === "gateway" ? "gateway" : "client",
        ...coordinates,
      };
    });

  const sourceEdges = network?.edges ?? scene.contacts;
  const links: NetworkLink[] = sourceEdges.map((edge, index) => ({
    id: `${edge.a}-${edge.b}-${index}`,
    sourceId: edge.a,
    targetId: edge.b,
    kind: edge.kind === "inter_satellite" ? "isl" : "ground",
    distanceKm: edge.distance_km,
    inRoute: routeEdgeIds.has([edge.a, edge.b].sort().join("::")),
  }));

  const metrics = (analysis?.clients ?? []).map((client) => ({
    clientId: client.client_id,
    visibility: client.coverage.has_visibility ? 100 : 0,
    availability: client.service.reachable ? 100 : 0,
    maxOutageMinutes: 0,
    outages: client.service.reachable ? 0 : 1,
  }));

  return {
    source: "backend",
    tS: scene.t_s,
    horizonS: request.scenario.horizonS,
    stepS: request.scenario.stepS,
    satellites,
    groundSites,
    links,
    route,
    orbits: [],
    metrics,
    availability: Object.fromEntries(
      groundSites
        .filter((site) => site.role === "client")
        .map((site) => [site.id, []]),
    ),
    outageReason: selectedClient?.service.no_route_reason ?? null,
  };
}


export type FrontendWorkspaceStateDto = {
  schema_version: "frontend-workspace-state-1.0";
  saved_at: string;
  scenario: ScenarioDraft;
  runtime: {
    t_s: number;
    client_id: string;
    selected_id: string | null;
  };
  viewport: {
    page: PageId;
    view_mode: ViewMode;
    earth_style: EarthStyle;
  };
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

/**
 * Encode the current React workbench state into a versioned JSON transport DTO.
 * This is intentionally kept next to the frame adapter: both are frontend_json
 * boundary contracts and neither leaks React objects/functions into JSON.
 */
export function buildFrontendWorkspaceState(
  state: FrontendWorkspaceStateInput,
): FrontendWorkspaceStateDto {
  return {
    schema_version: "frontend-workspace-state-1.0",
    saved_at: new Date().toISOString(),
    scenario: { ...state.scenario },
    runtime: {
      t_s: state.tS,
      client_id: state.clientId,
      selected_id: state.selectedId,
    },
    viewport: {
      page: state.page,
      view_mode: state.viewMode,
      earth_style: state.earthStyle,
    },
    layers: { ...state.layers },
    hidden_node_ids: [...state.hiddenNodeIds],
    frame_snapshot: state.frame,
  };
}

export function isFrontendWorkspaceState(
  value: unknown,
): value is FrontendWorkspaceStateDto {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<FrontendWorkspaceStateDto>;
  return (
    candidate.schema_version === "frontend-workspace-state-1.0" &&
    Boolean(candidate.scenario) &&
    Boolean(candidate.runtime) &&
    Boolean(candidate.viewport) &&
    Boolean(candidate.layers) &&
    Array.isArray(candidate.hidden_node_ids)
  );
}
