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

export interface SimulationFrame {
  source: "mock" | "backend";
  tS: number;
  horizonS: number;
  stepS: number;
  satellites: SatelliteFrame[];
  groundSites: GroundSite[];
  links: NetworkLink[];
  route: string[];
  orbits: OrbitPath[];
  metrics: ClientMetrics[];
  availability: Record<string, AvailabilitySegment[]>;
  outageReason: string | null;
}

export interface ScenarioDraft {
  id: string;
  title: string;
  altitudeKm: number;
  inclinationDeg: number;
  launchStage: 1 | 2 | 3;
  islRangeKm: number;
  stepS: number;
  horizonS: number;
  targetAvailability: number;
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