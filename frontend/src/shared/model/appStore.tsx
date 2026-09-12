import {
  createContext,
  useCallback,
  useContext,
  useEffect,
  useMemo,
  useRef,
  useState,
  type PropsWithChildren,
} from "react";
import type {
  EarthStyle,
  LayerVisibility,
  ModelRunData,
  ModelRunProgress,
  ModelSummary,
  PageId,
  RoutingStrategyId,
  RoutingStrategyOption,
  ScenarioDraft,
  SimulationFrame,
  ViewMode,
} from "./types";
import { ModelApiClient, type ContextualModelRunController } from "../api/client";
import { frameFromModelRun, hasModelRunFrame } from "../api/modelRunAdapter";
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
  runProgress: ModelRunProgress | null;
  availableModels: ModelSummary[];
  loadModel: (id: string) => Promise<void>;
  recalculate: () => Promise<void>;
  dirty: boolean;
  frame: SimulationFrame | null;
  loading: boolean;
  error: string | null;
  tS: number;
  setTS: (value: number) => void;
  timelineReady: boolean;
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
  playbackRate: number;
  setPlaybackRate: (value: number) => void;
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
  const [runProgress, setRunProgress] = useState<ModelRunProgress | null>(null);
  const [snapshotFrame, setSnapshotFrame] = useState<SimulationFrame | null>(null);
  const [availableModels, setAvailableModels] = useState<ModelSummary[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dirty, setDirty] = useState(false);
  const [tS, setTSState] = useState(0);
  const [timelineReady, setTimelineReady] = useState(false);
  const [clientId, setClientIdState] = useState(firstClientId(DEFAULT_SCENARIO));
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [routingStrategyId, setRoutingStrategyId] = useState<RoutingStrategyId>("minimum_hops");
  const [routingStrategies, setRoutingStrategies] = useState<RoutingStrategyOption[]>(DEFAULT_ROUTING_STRATEGIES);
  const [viewMode, setViewMode] = useState<ViewMode>("3d");
  const [earthStyle, setEarthStyle] = useState<EarthStyle>("black");
  const [playing, setPlaying] = useState(false);
  const [playbackRate, setPlaybackRateState] = useState(1);
  const [layers, setLayers] = useState<LayerVisibility>({
    satellites: true,
    groundSites: true,
    orbits: true,
    network: true,
    route: true,
    labels: true,
  });
  const [hiddenNodeIds, setHiddenNodeIds] = useState<string[]>([]);
  const contextRunRef = useRef<ContextualModelRunController | null>(null);
  const runGenerationRef = useRef(0);
  const seekTimerRef = useRef<number | null>(null);
  const snapshotRequestRef = useRef(0);

  const cancelContextRun = useCallback(() => {
    if (seekTimerRef.current !== null) {
      window.clearTimeout(seekTimerRef.current);
      seekTimerRef.current = null;
    }
    runGenerationRef.current += 1;
    contextRunRef.current?.cancel();
    contextRunRef.current = null;
  }, []);

  const setScenario = useCallback((next: ScenarioDraft) => {
    cancelContextRun();
    setLoading(false);
    setPlaying(false);
    setScenarioState(next);
    setModelRun(null);
    setRunProgress(null);
    setSnapshotFrame(null);
    setTimelineReady(false);
    setDirty(true);
    const clients = next.groundSites.filter((site) => site.role === "client");
    if (!clients.some((site) => site.id === clientId)) {
      setClientIdState(clients[0]?.id ?? "");
    }
    setTSState((current) => normalizeTime(current, next));
  }, [cancelContextRun, clientId]);

  const runScenario = useCallback(async (
    nextScenario: ScenarioDraft,
    nextRoutingStrategy: RoutingStrategyId,
    requestedFocusTS: number,
    requestedClientId: string,
  ) => {
    const generation = runGenerationRef.current + 1;
    runGenerationRef.current = generation;
    contextRunRef.current?.cancel();
    contextRunRef.current = null;

    setLoading(true);
    setError(null);
    try {
      const validatedScenario = validateScenarioDraft(nextScenario);
      const previewClientId = validatedScenario.groundSites.some(
        (site) => site.role === "client" && site.id === requestedClientId,
      ) ? requestedClientId : firstClientId(validatedScenario);
      const focusTS = normalizeTime(requestedFocusTS, validatedScenario);

      // Render the exact requested moment immediately.  The bidirectional run
      // then fills the same region and the rest of the grid in the background.
      const preview = await api.getSnapshot(
        validatedScenario,
        focusTS,
        previewClientId,
        nextRoutingStrategy,
      );
      if (generation !== runGenerationRef.current) return;

      setScenarioState(validatedScenario);
      setClientIdState(previewClientId);
      setTSState(focusTS);
      setSnapshotFrame(preview);
      setTimelineReady(true);
      setModelRun(null);
      setRunProgress(null);

      const controller = api.runModelContext(
        validatedScenario,
        nextRoutingStrategy,
        (partialRun, progress) => {
          if (generation !== runGenerationRef.current) return;
          setModelRun(partialRun);
          setRunProgress(progress);
          setRoutingStrategies(
            partialRun.routingStrategies.length
              ? partialRun.routingStrategies
              : DEFAULT_ROUTING_STRATEGIES,
          );
        },
        {
          batchSize: 8,
          initialFocusTS: focusTS,
          focusRadiusS: validatedScenario.stepS * 16,
        },
      );
      contextRunRef.current = controller;
      const run = await controller.done;
      if (generation !== runGenerationRef.current) return;

      contextRunRef.current = null;
      setModelRun(run);
      setRoutingStrategies(run.routingStrategies.length ? run.routingStrategies : DEFAULT_ROUTING_STRATEGIES);
      setDirty(false);
    } catch (reason: unknown) {
      if (generation !== runGenerationRef.current) return;
      if (reason instanceof DOMException && reason.name === "AbortError") return;
      const message = reason instanceof Error ? reason.message : "Не удалось рассчитать модель";
      setError(message);
      throw reason;
    } finally {
      if (generation === runGenerationRef.current) setLoading(false);
    }
  }, []);

  const recalculate = useCallback(async () => {
    setPlaying(false);
    await runScenario(scenario, routingStrategyId, tS, clientId);
    setTSState((current) => normalizeTime(current, scenario));
  }, [clientId, routingStrategyId, runScenario, scenario, tS]);

  const loadModel = useCallback(async (id: string) => {
    cancelContextRun();
    setLoading(true);
    setError(null);
    setPlaying(false);
    try {
      const nextScenario = await api.getModel(id);
      const nextClientId = firstClientId(nextScenario);
      const preview = await api.getSnapshot(
        nextScenario,
        0,
        nextClientId,
        routingStrategyId,
      );
      setScenarioState(nextScenario);
      setTSState(0);
      setClientIdState(nextClientId);
      setSelectedId(null);
      setSnapshotFrame(preview);
      setTimelineReady(true);
      setModelRun(null);
      setRunProgress(null);
      setRoutingStrategies(DEFAULT_ROUTING_STRATEGIES);
      setDirty(false);
    } catch (reason: unknown) {
      const message = reason instanceof Error ? reason.message : "Не удалось загрузить модель";
      setError(message);
      throw reason;
    } finally {
      setLoading(false);
    }
  }, [cancelContextRun, routingStrategyId]);

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
        const nextClientId = firstClientId(nextScenario);
        const preview = await api.getSnapshot(nextScenario, 0, nextClientId, "minimum_hops");
        if (!active) return;
        setScenarioState(nextScenario);
        setClientIdState(nextClientId);
        setTSState(0);
        setSnapshotFrame(preview);
        setTimelineReady(true);
        setModelRun(null);
        setRunProgress(null);
        setRoutingStrategies(DEFAULT_ROUTING_STRATEGIES);
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

  useEffect(() => () => {
    runGenerationRef.current += 1;
    contextRunRef.current?.cancel();
    contextRunRef.current = null;
  }, []);

  const setTS = useCallback((value: number) => {
    if (!timelineReady) return;
    const next = normalizeTime(value, scenario);
    const direction: -1 | 0 | 1 = next > tS ? 1 : next < tS ? -1 : 0;
    setPlaying(false);
    setTSState(next);
    setRunProgress((current) => current
      ? { ...current, focusTS: next, focusReady: modelRun ? hasModelRunFrame(modelRun, next) : false }
      : current);

    if (modelRun && hasModelRunFrame(modelRun, next)) return;
    if (contextRunRef.current) {
      contextRunRef.current.focus(next, direction, scenario.stepS * 16);
      return;
    }

    // A model loaded only as a startup snapshot has no background calculation
    // yet.  The first timeline seek lazily starts the demand-driven run around
    // the requested point instead of leaving the slider visually movable but
    // functionally disconnected from the backend.
    if (seekTimerRef.current !== null) window.clearTimeout(seekTimerRef.current);
    seekTimerRef.current = window.setTimeout(() => {
      seekTimerRef.current = null;
      void runScenario(scenario, routingStrategyId, next, clientId).catch(() => undefined);
    }, 90);
  }, [clientId, modelRun, routingStrategyId, runScenario, scenario, tS, timelineReady]);

  const setClientId = useCallback((value: string) => {
    setClientIdState(value);
    if (!timelineReady || (modelRun && hasModelRunFrame(modelRun, tS))) return;

    const request = snapshotRequestRef.current + 1;
    snapshotRequestRef.current = request;
    void api.getSnapshot(scenario, tS, value, routingStrategyId)
      .then((nextFrame) => {
        if (request === snapshotRequestRef.current) setSnapshotFrame(nextFrame);
      })
      .catch(() => undefined);
  }, [modelRun, routingStrategyId, scenario, tS, timelineReady]);

  const setPlaybackRate = useCallback((value: number) => {
    const allowed = [1, 5, 20, 60];
    setPlaybackRateState(allowed.includes(value) ? value : 1);
  }, []);

  useEffect(() => {
    if (!playing || !timelineReady) return;

    // Playback from a startup-only snapshot lazily opens the contextual run.
    // Once the start event arrives, normal demand-driven playback continues.
    if (!modelRun && !contextRunRef.current) {
      if (!loading) {
        void runScenario(scenario, routingStrategyId, tS, clientId).catch(() => undefined);
      }
      return;
    }

    const maximum = Math.max(0, scenario.horizonS - scenario.stepS);
    const timer = window.setInterval(() => {
      setTSState((current) => {
        const stride = Math.max(1, playbackRate) * scenario.stepS;
        const next = current + stride > maximum ? 0 : normalizeTime(current + stride, scenario);

        if (modelRun && hasModelRunFrame(modelRun, next)) return next;

        // Do not outrun a demand-driven calculation.  Ask for the next playback
        // point and keep rendering the current exact frame until it arrives.
        contextRunRef.current?.focus(next, 1, Math.max(scenario.stepS * 16, stride * 2));
        return current;
      });
    }, 180);
    return () => window.clearInterval(timer);
  }, [clientId, loading, modelRun, playbackRate, playing, routingStrategyId, runScenario, scenario, tS, timelineReady]);

  function selectRouteForFrame(source: SimulationFrame, strategyId: RoutingStrategyId): SimulationFrame {
    const details = source.routesByStrategy[strategyId] ?? null;
    const route = details?.nodeIds ?? [];
    const routeEdges = new Set(
      route.slice(0, -1).map((id, index) => [id, route[index + 1]].sort().join("::")),
    );
    return {
      ...source,
      route,
      routeDetails: details,
      links: source.links.map((link) => ({
        ...link,
        inRoute: routeEdges.has([link.sourceId, link.targetId].sort().join("::")),
      })),
    };
  }

  const frame = useMemo(() => {
    const calculated = modelRun
      ? frameFromModelRun(modelRun, tS, clientId, routingStrategyId)
      : null;
    if (calculated) return calculated;
    return snapshotFrame?.tS === tS ? selectRouteForFrame(snapshotFrame, routingStrategyId) : null;
  }, [modelRun, snapshotFrame, tS, clientId, routingStrategyId]);

  const value = useMemo<AppState>(() => ({
    page,
    setPage,
    scenario,
    setScenario,
    modelRun,
    runProgress,
    availableModels,
    loadModel,
    recalculate,
    dirty,
    frame,
    loading,
    error,
    tS,
    setTS,
    timelineReady,
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
    playbackRate,
    setPlaybackRate,
  }), [
    page,
    scenario,
    setScenario,
    modelRun,
    runProgress,
    availableModels,
    loadModel,
    recalculate,
    dirty,
    frame,
    loading,
    error,
    tS,
    setTS,
    timelineReady,
    clientId,
    selectedId,
    routingStrategyId,
    routingStrategies,
    viewMode,
    earthStyle,
    layers,
    hiddenNodeIds,
    playing,
    playbackRate,
    setPlaybackRate,
  ]);

  return <StateContext.Provider value={value}>{children}</StateContext.Provider>;
}

export function useAppState() {
  const state = useContext(StateContext);
  if (!state) throw new Error("useAppState must be used inside AppStateProvider");
  return state;
}
