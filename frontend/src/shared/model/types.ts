export type PageId = "project" | "analysis" | "resilience" | "comparison";
export type ViewMode = "3d" | "2d";
export type EarthStyle = "black" | "imagery";
export type ObjectId = string;
export type RoutingStrategyId =
  | "minimum_hops"
  | "minimum_distance"
  | "resilient_distance";

export interface RoutingStrategyOption {
  id: RoutingStrategyId;
  label: string;
  description: string;
}

export interface Vector3Km {
  xKm: number;
  yKm: number;
  zKm: number;
}

export interface SatelliteFrame {
  id: string;
  planeId: string;
  active: boolean;
  failed: boolean;
  launchBatch: number;
  position: Vector3Km;
}

export interface GroundSite {
  id: string;
  name: string;
  role: "client" | "gateway";
  latDeg: number;
  lonDeg: number;
}

export interface NetworkLink {
  id: string;
  sourceId: string;
  targetId: string;
  kind: "isl" | "ground";
  distanceKm: number;
  inRoute: boolean;
}

export interface OrbitPath {
  planeId: string;
  positions: Vector3Km[];
}

export interface ClientMetrics {
  clientId: string;
  visibility: number;
  availability: number;
  maxOutageMinutes: number;
  outages: number;
}

export interface AvailabilitySegment {
  from: number;
  to: number;
  state: "path" | "visible-only" | "no-satellite";
}

export interface RouteDetails {
  strategyId: RoutingStrategyId | string;
  sourceId: string;
  targetId: string;
  nodeIds: string[];
  hopCount: number;
  totalDistanceKm: number;
  quality: Array<{
    name: string;
    value: number;
    direction: "maximize" | "minimize";
  }>;
}

export interface SimulationFrame {
  source: "mock" | "backend";
  tS: number;
  horizonS: number;
  stepS: number;
  satellites: SatelliteFrame[];
  groundSites: GroundSite[];
  links: NetworkLink[];
  route: string[];
  routeDetails: RouteDetails | null;
  routesByStrategy: Record<string, RouteDetails | null>;
  orbits: OrbitPath[];
  metrics: ClientMetrics[];
  availability: Record<string, AvailabilitySegment[]>;
  outageReason: string | null;
}

export interface PlaneDraft {
  id: string;
  raanDeg: number;
  phaseDeg: number;
}

export interface SatelliteDraft {
  id: string;
  planeId: string;
  slotDeg: number;
  launchBatch: 1 | 2 | 3;
}

export interface GroundSiteDraft {
  id: string;
  name: string;
  role: "client" | "gateway";
  latDeg: number;
  lonDeg: number;
}

export interface SatelliteOutageDraft {
  satelliteId: string;
  startS: number;
  endS: number;
}

export interface GatewayOutageDraft {
  gatewayId: string;
  startS: number;
  endS: number;
}

/**
 * Complete editable representation of the cosmo-A-1.0 scenario.
 * Nothing from the source JSON is intentionally discarded.
 */
export interface ScenarioDraft {
  schemaVersion: "cosmo-A-1.0";
  id: string;
  title: string;
  altitudeKm: number;
  inclinationDeg: number;
  earthAngle0Deg: number;
  horizonS: number;
  stepS: number;
  minElevationDeg: number;
  islRangeKm: number;
  targetAvailability: number;
  launchStage: 1 | 2 | 3;
  planes: PlaneDraft[];
  satellites: SatelliteDraft[];
  groundSites: GroundSiteDraft[];
  failures: SatelliteOutageDraft[];
  gatewayOutages: GatewayOutageDraft[];
}

export interface ModelSummary {
  id: string;
  title: string;
  filename: string;
}

export interface ModelRunData {
  schemaVersion: "cosmo-model-run-1.0";
  scenario: ScenarioDraft;
  routingStrategies: RoutingStrategyOption[];
  primaryRoutingStrategyId: RoutingStrategyId;
  trace: unknown;
  dynamicAnalysis: unknown;
  raw: unknown;
}

export interface LayerVisibility {
  satellites: boolean;
  groundSites: boolean;
  orbits: boolean;
  network: boolean;
  route: boolean;
  labels: boolean;
}

export interface ComparisonResult {
  baselineName: string;
  variantName: string;
  changes: Array<{ parameter: string; before: string; after: string }>;
  clients: Array<{
    clientId: string;
    baselineAvailability: number;
    variantAvailability: number;
    baselineMaxOutage: number;
    variantMaxOutage: number;
  }>;
}