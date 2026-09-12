import {
  createContext,
  useContext,
  useEffect,
  useMemo,
  useState,
  type PropsWithChildren,
} from "react";
import type {
  EarthStyle,
  LayerVisibility,
  PageId,
  ScenarioDraft,
  SimulationFrame,
  ViewMode,
} from "./types";
import type { SimulationGateway } from "../api/client";
import { DEFAULT_SCENARIO } from "../api/scenarios";
import { mockSimulationGateway } from "../api/runs";
import { HttpSimulationGateway } from "../api/client";
import { applyDynamicAnalysis, type DynamicAnalysisView } from "../api/frontendJsonAdapter";

interface AppState {
  page: PageId;
  setPage: (page: PageId) => void;
  scenario: ScenarioDraft;
  setScenario: (scenario: ScenarioDraft) => void;
  frame: SimulationFrame | null;
  loading: boolean;
  error: string | null;
  dynamicLoading: boolean;
  dynamicError: string | null;
  runDynamicAnalysis: () => Promise<void>;
  tS: number;
  setTS: (value: number) => void;
  clientId: string;
  setClientId: (value: string) => void;
  selectedId: string | null;
  setSelectedId: (value: string | null) => void;
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

const defaultSimulationGateway: SimulationGateway =
  ((import.meta as ImportMeta & { env?: Record<string, string | undefined> }).env?.VITE_USE_MOCK === "1")
    ? mockSimulationGateway
    : new HttpSimulationGateway();

export function AppStateProvider({
  children,
  gateway = defaultSimulationGateway,
}: PropsWithChildren<{ gateway?: SimulationGateway }>) {
  const [page, setPage] = useState<PageId>("analysis");
  const [scenario, setScenario] = useState(DEFAULT_SCENARIO);
  const [frame, setFrame] = useState<SimulationFrame | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [dynamicAnalysis, setDynamicAnalysis] = useState<DynamicAnalysisView | null>(null);
  const [dynamicLoading, setDynamicLoading] = useState(false);
  const [dynamicError, setDynamicError] = useState<string | null>(null);
  const [tS, setTS] = useState(34680);
  const [clientId, setClientId] = useState("C65");
  const [selectedId, setSelectedId] = useState<string | null>(null);
  const [viewMode, setViewMode] = useState<ViewMode>("3d");
  const [earthStyle, setEarthStyle] = useState<EarthStyle>("imagery");
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

  useEffect(() => {
    let active = true;
    setLoading(true);
    gateway
      .getFrame({ scenario, tS, clientId })
      .then((nextFrame) => {
        if (active) {
          setFrame(applyDynamicAnalysis(nextFrame, dynamicAnalysis));
          setError(null);
        }
      })
      .catch((reason: unknown) => {
        if (active) {
          setError(reason instanceof Error ? reason.message : "Неизвестная ошибка");
        }
      })
      .finally(() => active && setLoading(false));
    return () => {
      active = false;
    };
  }, [gateway, scenario, tS, clientId]);

  useEffect(() => {
    setDynamicAnalysis(null);
    setDynamicError(null);
  }, [scenario]);

  useEffect(() => {
    if (!dynamicAnalysis) return;
    setFrame((current) => current ? applyDynamicAnalysis(current, dynamicAnalysis) : current);
  }, [dynamicAnalysis]);

  const runDynamicAnalysis = async () => {
    if (!gateway.getDynamicAnalysis) {
      setDynamicError("Текущий gateway не поддерживает динамический анализ");
      return;
    }
    setDynamicLoading(true);
    setDynamicError(null);
    try {
      const analysis = await gateway.getDynamicAnalysis(scenario);
      setDynamicAnalysis(analysis);
    } catch (reason) {
      setDynamicError(reason instanceof Error ? reason.message : "Ошибка динамического анализа");
    } finally {
      setDynamicLoading(false);
    }
  };

  useEffect(() => {
    if (!playing) return;
    const timer = window.setInterval(() => {
      setTS((current) =>
        current + scenario.stepS >= scenario.horizonS
          ? 0
          : current + scenario.stepS,
      );
    }, 180);
    return () => window.clearInterval(timer);
  }, [playing, scenario.horizonS, scenario.stepS]);

  const value = useMemo<AppState>(
    () => ({
      page,
      setPage,
      scenario,
      setScenario,
      frame,
      loading,
      error,
      dynamicLoading,
      dynamicError,
      runDynamicAnalysis,
      tS,
      setTS,
      clientId,
      setClientId,
      selectedId,
      setSelectedId,
      viewMode,
      setViewMode,
      earthStyle,
      setEarthStyle,
      layers,
      toggleLayer: (key) =>
        setLayers((current) => ({ ...current, [key]: !current[key] })),
      setLayerVisibility: (key, visible) =>
        setLayers((current) => ({ ...current, [key]: visible })),
      hiddenNodeIds,
      toggleNodeVisibility: (nodeId) =>
        setHiddenNodeIds((current) =>
          current.includes(nodeId)
            ? current.filter((id) => id !== nodeId)
            : [...current, nodeId],
        ),
      playing,
      setPlaying,
    }),
    [
      page,
      scenario,
      frame,
      loading,
      error,
      dynamicLoading,
      dynamicError,
      runDynamicAnalysis,
      tS,
      clientId,
      selectedId,
      viewMode,
      earthStyle,
      layers,
      hiddenNodeIds,
      playing,
    ],
  );

  return <StateContext.Provider value={value}>{children}</StateContext.Provider>;
}

export function useAppState() {
  const state = useContext(StateContext);
  if (!state) throw new Error("useAppState must be used inside AppStateProvider");
  return state;
}
