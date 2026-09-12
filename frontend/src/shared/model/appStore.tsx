import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import type {
  EarthStyle,
  LayerVisibility,
  ModelRunData,
  ModelSummary,
  PageId,
  RoutingStrategyId,
  RoutingStrategyOption,
  ScenarioDraft,
  SimulationFrame,
  ViewMode,
} from "./types";
import { ModelApiClient } from "../api/client";
import { frameFromModelRun } from "../api/modelRunAdapter";
import { DEFAULT_SCENARIO, validateScenarioDraft } from "../api/scenarios";

const DEFAULT_ROUTING_STRATEGIES: RoutingStrategyOption[] = [
  {
    id: "minimum_hops",
    label: "Минимум переходов",
    description: "Минимизирует число переходов в маршруте.",
  },
  {
    id: "minimum_distance",
    label: "Минимальная дистанция",
    description: "Минимизирует суммарную геометрическую длину маршрута.",
  },
  {
    id: "resilient_distance",
    label: "Устойчивый маршрут",
    description: "Сначала максимизирует живучесть при единичном отказе, затем минимизирует дистанцию.",
  },
];

interface AppState {
  page: PageId;
  setPage: (page: PageId) => void;
  scenario: ScenarioDraft;
  setScenario: (scenario: ScenarioDraft) => void;
  modelRun: ModelRunData | null;
  availableModels: ModelSummary[];
  loadModel: (id: string) => Promise<void>;
  recalculate: () => Promise<void>;
  dirty: boolean;
  frame: SimulationFrame | null;
  loading: boolean;
  error: string | null;
  tS: number;
  setTS: (value: number) => void;
  clientId: string;
  setClientId: (value: string) => void;
  selectedId: string | null;
  setSelectedId: (value: string | null) => void;
  routingStrategyId: RoutingStrategyId;
  setRoutingStrategyId: (value: RoutingStrategyId) => void;
  routingStrategies: RoutingStrategyOption[];
  viewMode: ViewMode;
  setViewMode: (value: ViewMode) => void;
  earthStyle: EarthStyle;
  setEarthStyle: (value: EarthStyle) => void;
  layers: LayerVisibility;
  toggleLayer: (key: keyof LayerVisibility) => void;
  setLayerVisibility: (key: keyof LayerVisibility, visible: boolean) => void;
  hiddenNodeIds: string[];
  toggleNodeVisibility: (nodeId: string) => void;
  playing: boolean;
  setPlaying: (value: boolean) => void;
}

const StateContext = createContext<AppState | null>(null);
const api = new ModelApiClient();

function firstClientId(scenario: ScenarioDraft) {
  return scenario.groundSites.find((site) => site.role === "client")?.id ?? "";
}

function normalizeTime(value: number, scenario: ScenarioDraft) {
  const step = Math.max(1, Math.round(scenario.stepS || 1));
  const horizon = Math.max(step, Math.round(scenario.horizonS || step));
  const maximum = Math.max(0, horizon - step);
  const clamped = Math.min(Math.max(value, 0), maximum);
  return Math.round(clamped / step) * step;
}

export function AppStateProvider({ children }: PropsWithChildren) {
  const [page, setPage] = useState<PageId>("project");
  const [scenario, setScenarioState] = useState<ScenarioDraft>(DEFAULT_SCENARIO);
  const [modelRun, setModelRun] = useState<ModelRunData | null>(null);
  const [availableModels, setAvailableModels] = useState<ModelSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [tS, setTSState] = useState(0);
  const [clientId, setClientId] = useState(firstClientId(DEFAULT_SCENARIO));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [routingStrategyId, setRoutingStrategyId] = useState<RoutingStrategyId>("minimum_hops");
  const [routingStrategies, setRoutingStrategies] = useState<RoutingStrategyOption[]>(DEFAULT_ROUTING_STRATEGIES);
  const [viewMode, setViewMode] = useState<ViewMode>("3d");
  const [earthStyle, setEarthStyle] = useState<EarthStyle>("black");
  const [playing, setPlaying] = useState(false);
  const [layers, setLayers] = useState<LayerVisibility>({
    satellites: true,
    groundSites: true,
    orbits: true,
    network: true,
    route: true,
    labels: true,
  });
  const [hiddenNodeIds, setHiddenNodeIds] = useState<string[]>([]);

  const setScenario = useCallback((next: ScenarioDraft) => {
    setScenarioState(next);
    setDirty(true);
    const clients = next.groundSites.filter((site) => site.role === "client");
    if (!clients.some((site) => site.id === clientId)) {
      setClientId(clients[0]?.id ?? "");
    }
    setTSState((current) => normalizeTime(current, next));
  }, [clientId]);

  const runScenario = useCallback(async (
    nextScenario: ScenarioDraft,
    nextRoutingStrategy: RoutingStrategyId,
  ) => {
    setLoading(true);
    setError(null);
    try {
      const validatedScenario = validateScenarioDraft(nextScenario);
      const run = await api.runModel(validatedScenario, nextRoutingStrategy);
      setScenarioState(validatedScenario);
      setModelRun(run);
      setRoutingStrategies(run.routingStrategies.length ? run.routingStrategies : DEFAULT_ROUTING_STRATEGIES);
      setDirty(false);
      return run;
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Не удалось рассчитать модель";
      setError(message);
      throw reason;
    } finally {
      setLoading(false);
    }
  }, []);

  const recalculate = useCallback(async () => {
    setPlaying(false);
    await runScenario(scenario, routingStrategyId);
    setTSState((current) => normalizeTime(current, scenario));
  }, [routingStrategyId, runScenario, scenario]);

  const loadModel = useCallback(async (id: string) => {
    setLoading(true);
    setError(null);
    setPlaying(false);
    try {
      const nextScenario = await api.getModel(id);
      setScenarioState(nextScenario);
      setTSState(0);
      setClientId(firstClientId(nextScenario));
      setSelectedId(null);
      const run = await api.runModel(nextScenario, routingStrategyId);
      setModelRun(run);
      setRoutingStrategies(run.routingStrategies.length ? run.routingStrategies : DEFAULT_ROUTING_STRATEGIES);
      setDirty(false);
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Не удалось загрузить модель";
      setError(message);
      throw reason;
    } finally {
      setLoading(false);
    }
  }, [routingStrategyId]);

  useEffect(() => {
    let active = true;
    void (async () => {
      try {
        const models = await api.listModels();
        if (!active) return;
        setAvailableModels(models);
        const preferred = models.find((item) => item.id === DEFAULT_SCENARIO.id) ?? models[0];
        const nextScenario = preferred ? await api.getModel(preferred.id) : DEFAULT_SCENARIO;
        if (!active) return;
        setScenarioState(nextScenario);
        setClientId(firstClientId(nextScenario));
        const run = await api.runModel(nextScenario, "minimum_hops");
        if (!active) return;
        setModelRun(run);
        setRoutingStrategies(run.routingStrategies.length ? run.routingStrategies : DEFAULT_ROUTING_STRATEGIES);
        setDirty(false);
        setError(null);
      } catch (reason: unknown) {
        if (active) {
          setError(
            reason instanceof Error
              ? `Backend API недоступен: ${reason.message}`
              : "Backend API недоступен",
          );
        }
      } finally {
        if (active) setLoading(false);
      }
    })();
    return () => {
      active = false;
    };
  }, []);

  const setTS = useCallback((value: number) => {
    setTSState(normalizeTime(value, scenario));
  }, [scenario]);

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setTSState((current) =>
        current + scenario.stepS >= scenario.horizonS ? 0 : current + scenario.stepS,
      );
    }, 180);
    return () => window.clearInterval(timer);
  }, [playing, scenario.horizonS, scenario.stepS]);

  const frame = useMemo(
    () => modelRun
      ? frameFromModelRun(modelRun, tS, clientId, routingStrategyId)
      : null,
    [modelRun, tS, clientId, routingStrategyId],
  );

  const value = useMemo<AppState>(() => ({
    page,
    setPage,
    scenario,
    setScenario,
    modelRun,
    availableModels,
    loadModel,
    recalculate,
    dirty,
    frame,
    loading,
    error,
    tS,
    setTS,
    clientId,
    setClientId,
    selectedId,
    setSelectedId,
    routingStrategyId,
    setRoutingStrategyId,
    routingStrategies,
    viewMode,
    setViewMode,
    earthStyle,
    setEarthStyle,
    layers,
    toggleLayer: (key) => setLayers((current) => ({ ...current, [key]: !current[key] })),
    setLayerVisibility: (key, visible) => setLayers((current) => ({ ...current, [key]: visible })),
    hiddenNodeIds,
    toggleNodeVisibility: (nodeId) =>
      setHiddenNodeIds((current) =>
        current.includes(nodeId)
          ? current.filter((id) => id !== nodeId)
          : [...current, nodeId],
      ),
    playing,
    setPlaying,
  }), [
    page,
    scenario,
    setScenario,
    modelRun,
    availableModels,
    loadModel,
    recalculate,
    dirty,
    frame,
    loading,
    error,
    tS,
    setTS,
    clientId,
    selectedId,
    routingStrategyId,
    routingStrategies,
    viewMode,
    earthStyle,
    layers,
    hiddenNodeIds,
    playing,
  ]);

  return <StateContext.Provider value={value}>{children}</StateContext.Provider>;
}

export function useAppState() {
  const state = useContext(StateContext);
  if (!state) throw new Error("useAppState must be used inside AppStateProvider");
  return state;
}
