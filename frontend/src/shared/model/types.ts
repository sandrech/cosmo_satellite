export type PageId = "project" | "analysis" | "resilience" | "comparison";
export type ViewMode = "3d" | "2d";
export type EarthStyle = "black" | "imagery";
export type ObjectId = string;

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
  inactiveReason: "not-launched" | "failed" | null;
  launchBatch: number;
  position: Vector3Km;
}

export interface GroundSite {
  id: string;
  name: string;
  role: "client" | "gateway";
  latDeg: number;
  lonDeg: number;
  available: boolean;
  position: Vector3Km;
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
  nMinusOne?: number;
}

export interface AvailabilitySegment {
  from: number;
  to: number;
  state: "path" | "visible-only" | "no-satellite";
}

export interface RouteView {
  strategyId: string;
  nodeIds: string[];
  hopCount: number;
  totalDistanceKm: number;
}

export interface SimulationFrame {
  source: "mock" | "backend";
  tS: number;
  horizonS: number;
  stepS: number;
  bodyRadiusKm: number;
  satellites: SatelliteFrame[];
  groundSites: GroundSite[];
  links: NetworkLink[];
  route: string[];
  routes: RouteView[];
  orbits: OrbitPath[];
  metrics: ClientMetrics[];
  availability: Record<string, AvailabilitySegment[]>;
  outageReason: string | null;
  reachableClients: number;
  clientCount: number;
  currentConnectivity: number | null;
  survivesAnySingleSatelliteFailure: boolean | null;
}

export interface CosmoScenario {
  schema_version: "cosmo-A-1.0";
  meta: { id: string; title: string };
  environment: {
    altitude_km: number;
    inclination_deg: number;
    earth_angle0_deg: number;
    horizon_s: number;
    step_s: number;
    min_elevation_deg: number;
    isl_range_km: number;
    target_availability: number;
  };
  design: {
    launch_stage: 1 | 2 | 3;
    planes: Array<{ id: string; raan_deg: number; phase_deg: number }>;
    satellites: Array<{
      id: string;
      plane_id: string;
      slot_deg: number;
      launch_batch: 1 | 2 | 3;
    }>;
  };
  ground_sites: Array<{
    id: string;
    name: string;
    role: "client" | "gateway";
    lat_deg: number;
    lon_deg: number;
  }>;
  failures: Array<{ satellite_id: string; start_s: number; end_s: number }>;
  gateway_outages: Array<{ gateway_id: string; start_s: number; end_s: number }>;
}

/**
 * Editable frontend view of the canonical scenario. `canonical` is always the
 * authoritative payload sent to / exported from the backend; scalar fields are
 * convenient projections used by the existing form controls.
 */
export interface ScenarioDraft {
  id: string;
  title: string;
  altitudeKm: number;
  inclinationDeg: number;
  earthAngle0Deg: number;
  launchStage: 1 | 2 | 3;
  islRangeKm: number;
  minElevationDeg: number;
  stepS: number;
  horizonS: number;
  targetAvailability: number;
  canonical: CosmoScenario;
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
