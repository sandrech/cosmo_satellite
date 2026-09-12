import type {
  EarthStyle,
  LayerVisibility,
  PageId,
  RoutingStrategyId,
  ScenarioDraft,
  SimulationFrame,
  ViewMode,
} from "../model/types";

export type FrontendWorkspaceStateDto = {
  schema_version: "frontend-workspace-state-1.0";
  saved_at: string;
  scenario: ScenarioDraft;
  runtime: {
    t_s: number;
    client_id: string;
    selected_id: string | null;
    routing_strategy_id: RoutingStrategyId;
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
  routingStrategyId: RoutingStrategyId;
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
    runtime: {
      t_s: state.tS,
      client_id: state.clientId,
      selected_id: state.selectedId,
      routing_strategy_id: state.routingStrategyId,
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

export function isFrontendWorkspaceState(value: unknown): value is FrontendWorkspaceStateDto {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<FrontendWorkspaceStateDto>;
  return candidate.schema_version === "frontend-workspace-state-1.0"
    && Boolean(candidate.scenario)
    && Boolean(candidate.runtime)
    && Boolean(candidate.viewport)
    && Boolean(candidate.layers)
    && Array.isArray(candidate.hidden_node_ids);
}
