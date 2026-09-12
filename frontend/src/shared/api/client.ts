import type {
  ModelRunData,
  ModelRunProgress,
  ModelSummary,
  RoutingStrategyId,
  ScenarioDraft,
  SimulationFrame,
} from "../model/types";
import type { FrontendWorkspaceStateDto } from "./frontendJsonAdapter";
import { adaptModelSnapshot, isModelSnapshotDto } from "./frontendJsonAdapter";
import {
  isModelRunResponse,
  toModelRunData,
  toStreamingModelRunData,
} from "./modelRunAdapter";
import { scenarioFromJson, scenarioToJson } from "./scenarios";

// Kept for the isolated legacy mock module/tests. Production uses ModelApiClient.
export interface FrameRequest {
  scenario: ScenarioDraft;
  tS: number;
  clientId: string;
}

export interface SimulationGateway {
  getFrame(request: FrameRequest): Promise<SimulationFrame>;
}

export type WorkspaceSaveResult = {
  storage: "backend" | "download";
  filename?: string;
};

async function readJson(response: Response): Promise<unknown> {
  const body = await response.text();
  let payload: unknown = null;
  if (body) {
    try {
      payload = JSON.parse(body) as unknown;
    } catch {
      payload = null;
    }
  }

  if (!response.ok) {
    const record = payload && typeof payload === "object" ? payload as Record<string, unknown> : null;
    const nested = record?.error && typeof record.error === "object"
      ? record.error as Record<string, unknown>
      : null;
    const detail = record?.detail ?? record?.message ?? nested?.message;
    if (typeof detail === "string" && detail) throw new Error(detail);
    if (response.status >= 500 && !body) {
      throw new Error("Backend API недоступен");
    }
    throw new Error(`Backend returned HTTP ${response.status}`);
  }

  if (!body) throw new Error("Backend returned an empty response");
  if (payload === null) throw new Error("Backend returned invalid JSON");
  return payload;
}


export interface ContextualModelRunController {
  readonly done: Promise<ModelRunData>;
  focus(tS: number, direction?: -1 | 0 | 1, radiusS?: number): void;
  cancel(): void;
}

type ContextStartEvent = {
  type: "start";
  routing_strategies: ModelRunData["routingStrategies"];
  primary_route_strategy_id: RoutingStrategyId;
  sampling: { start_s: number; end_s: number; step_s: number };
  total_frames: number;
  cache_hit?: boolean;
};

function websocketUrl(baseUrl: string, path: string) {
  const url = new URL(`${baseUrl}${path}`, window.location.href);
  url.protocol = url.protocol === "https:" ? "wss:" : "ws:";
  return url.toString();
}

class BrowserContextualModelRun implements ContextualModelRunController {
  readonly done: Promise<ModelRunData>;

  private readonly socket: WebSocket;
  private readonly frames = new Map<number, unknown>();
  private start: ContextStartEvent | null = null;
  private dynamicAnalysis: unknown | null = null;
  private settled = false;
  private pendingFocus: { tS: number; direction: -1 | 0 | 1; radiusS?: number } | null = null;
  private resolveDone!: (run: ModelRunData) => void;
  private rejectDone!: (reason: unknown) => void;

  constructor(
    baseUrl: string,
    private readonly scenario: ScenarioDraft,
    private readonly primaryRoutingStrategyId: RoutingStrategyId,
    private readonly onUpdate: (run: ModelRunData, progress: ModelRunProgress) => void,
    private readonly batchSize: number,
    initialFocusTS: number,
    focusRadiusS?: number,
  ) {
    this.done = new Promise<ModelRunData>((resolve, reject) => {
      this.resolveDone = resolve;
      this.rejectDone = reject;
    });
    this.socket = new WebSocket(websocketUrl(baseUrl, "/model/run/context"));

    this.socket.addEventListener("open", () => {
      this.socket.send(JSON.stringify({
        scenario: scenarioToJson(this.scenario),
        primary_route_strategy_id: this.primaryRoutingStrategyId,
        batch_size: this.batchSize,
        focus_t_s: initialFocusTS,
        focus_radius_s: focusRadiusS,
        direction: 0,
      }));
      if (this.pendingFocus) {
        const focus = this.pendingFocus;
        this.pendingFocus = null;
        this.sendFocus(focus.tS, focus.direction, focus.radiusS);
      }
    });

    this.socket.addEventListener("message", (message) => {
      try {
        const parsed = JSON.parse(String(message.data)) as unknown;
        if (!parsed || typeof parsed !== "object") {
          throw new Error("Backend прислал повреждённое WebSocket-сообщение");
        }
        this.handleEvent(parsed as Record<string, unknown>);
      } catch (reason) {
        this.fail(reason instanceof Error ? reason : new Error("Некорректный WebSocket-контракт"));
      }
    });

    this.socket.addEventListener("error", () => {
      this.fail(new Error("WebSocket расчёта недоступен"));
    });

    this.socket.addEventListener("close", () => {
      if (!this.settled) {
        this.fail(new Error("Соединение расчёта закрылось до завершения модели"));
      }
    });
  }

  focus(tS: number, direction: -1 | 0 | 1 = 0, radiusS?: number) {
    if (this.settled) return;
    if (this.socket.readyState !== WebSocket.OPEN) {
      this.pendingFocus = { tS, direction, radiusS };
      return;
    }
    this.sendFocus(tS, direction, radiusS);
  }

  cancel() {
    if (this.settled) return;
    this.settled = true;
    if (this.socket.readyState === WebSocket.OPEN) {
      this.socket.send(JSON.stringify({ type: "cancel" }));
    }
    this.socket.close(1000, "superseded");
    this.rejectDone(new DOMException("Model run was cancelled", "AbortError"));
  }

  private sendFocus(tS: number, direction: -1 | 0 | 1, radiusS?: number) {
    this.socket.send(JSON.stringify({
      type: "focus",
      t_s: tS,
      direction,
      radius_s: radiusS,
    }));
  }

  private currentRun(dynamicAnalysis: unknown | null = this.dynamicAnalysis) {
    if (!this.start) throw new Error("Backend прислал кадры до метаданных расчёта");
    const orderedFrames = [...this.frames.entries()]
      .sort(([left], [right]) => left - right)
      .map(([, frame]) => frame);
    return toStreamingModelRunData({
      scenario: this.scenario,
      routingStrategies: this.start.routing_strategies,
      primaryRoutingStrategyId: this.start.primary_route_strategy_id,
      sampling: this.start.sampling,
      frames: orderedFrames,
      dynamicAnalysis,
    });
  }

  private progress(event: Record<string, unknown>, phase: ModelRunProgress["phase"]): ModelRunProgress {
    if (!this.start) throw new Error("Backend прислал прогресс до метаданных расчёта");
    return {
      completedFrames: Number(event.computed_frames ?? this.frames.size),
      deliveredFrames: Number(event.delivered_frames ?? this.frames.size),
      totalFrames: Number(event.total_frames ?? this.start.total_frames),
      phase,
      cacheHit: Boolean(event.cache_hit ?? this.start.cache_hit),
      focusTS: typeof event.focus_t_s === "number" ? event.focus_t_s : undefined,
      focusReady: typeof event.focus_ready === "boolean" ? event.focus_ready : undefined,
    };
  }

  private handleEvent(event: Record<string, unknown>) {
    if (event.type === "start") {
      if (!event.sampling || typeof event.sampling !== "object" || !Array.isArray(event.routing_strategies)) {
        throw new Error("Backend прислал некорректные метаданные контекстного расчёта");
      }
      this.start = event as unknown as ContextStartEvent;
      this.onUpdate(this.currentRun(null), this.progress({ ...event, computed_frames: 0, delivered_frames: 0 }, "frames"));
      return;
    }

    if (event.type === "frames") {
      if (!this.start || !Array.isArray(event.frames) || !Array.isArray(event.indices)) {
        throw new Error("Backend прислал некорректный контекстный батч кадров");
      }
      const frameBatch = event.frames;
      const indices = event.indices;
      if (frameBatch.length !== indices.length) {
        throw new Error("Backend прислал несовместимые индексы и кадры");
      }
      indices.forEach((rawIndex, position) => {
        const index = Number(rawIndex);
        if (!Number.isInteger(index) || index < 0) {
          throw new Error("Backend прислал некорректный индекс кадра");
        }
        this.frames.set(index, frameBatch[position]);
      });
      this.onUpdate(this.currentRun(null), this.progress(event, "frames"));
      return;
    }

    if (event.type === "phase" && event.phase === "aggregating") {
      this.onUpdate(this.currentRun(null), this.progress(event, "aggregating"));
      return;
    }

    if (event.type === "complete") {
      if (!("dynamic_analysis" in event)) {
        throw new Error("Backend не прислал финальную динамическую аналитику");
      }
      this.dynamicAnalysis = event.dynamic_analysis;
      const run = this.currentRun(this.dynamicAnalysis);
      this.onUpdate(run, this.progress(event, "complete"));
      this.settled = true;
      this.resolveDone(run);
      this.socket.close(1000, "complete");
      return;
    }

    if (event.type === "error") {
      throw new Error(typeof event.detail === "string" ? event.detail : "Ошибка контекстного расчёта");
    }
  }

  private fail(reason: unknown) {
    if (this.settled) return;
    this.settled = true;
    this.rejectDone(reason);
    if (this.socket.readyState === WebSocket.OPEN || this.socket.readyState === WebSocket.CONNECTING) {
      this.socket.close();
    }
  }
}

export class ModelApiClient {
  constructor(private readonly baseUrl = "/api") {}

  async listModels(): Promise<ModelSummary[]> {
    const payload = await readJson(
      await fetch(`${this.baseUrl}/models`, { headers: { Accept: "application/json" } }),
    );
    if (!Array.isArray(payload)) throw new Error("Некорректный список моделей от backend");
    return payload.map((item) => {
      const value = item && typeof item === "object" ? item as Record<string, unknown> : {};
      const id = String(value.id ?? "");
      return {
        id,
        title: String(value.title ?? id),
        filename: String(value.filename ?? `${id}.json`),
      };
    });
  }

  async getModel(id: string): Promise<ScenarioDraft> {
    const payload = await readJson(
      await fetch(`${this.baseUrl}/models/${encodeURIComponent(id)}`, {
        headers: { Accept: "application/json" },
      }),
    );
    return scenarioFromJson(payload);
  }

  async getSnapshot(
    scenario: ScenarioDraft,
    tS: number,
    clientId: string,
    primaryRoutingStrategyId: RoutingStrategyId,
  ): Promise<SimulationFrame> {
    const payload = await readJson(
      await fetch(`${this.baseUrl}/model/snapshot`, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario: scenarioToJson(scenario),
          t_s: tS,
          primary_route_strategy_id: primaryRoutingStrategyId,
        }),
      }),
    );
    if (!isModelSnapshotDto(payload)) {
      throw new Error("Backend вернул неподдерживаемый контракт кадра");
    }
    return adaptModelSnapshot(payload, {
      scenario,
      tS,
      clientId,
      routingStrategyId: primaryRoutingStrategyId,
    });
  }

  /** Calculate the complete official time grid in one backend call. */
  async runModel(
    scenario: ScenarioDraft,
    primaryRoutingStrategyId: RoutingStrategyId,
  ): Promise<ModelRunData> {
    const payload = await readJson(
      await fetch(`${this.baseUrl}/model/run`, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({
          scenario: scenarioToJson(scenario),
          primary_route_strategy_id: primaryRoutingStrategyId,
        }),
      }),
    );
    if (!isModelRunResponse(payload)) {
      throw new Error("Backend вернул неподдерживаемый контракт полного расчёта");
    }
    return toModelRunData(payload);
  }

  /**
   * Calculate the official grid in one HTTP request while receiving NDJSON
   * frame batches as soon as the backend finishes them.
   */
  async runModelStream(
    scenario: ScenarioDraft,
    primaryRoutingStrategyId: RoutingStrategyId,
    onUpdate: (run: ModelRunData, progress: ModelRunProgress) => void,
    batchSize = 8,
  ): Promise<ModelRunData> {
    const response = await fetch(`${this.baseUrl}/model/run/stream`, {
      method: "POST",
      headers: {
        Accept: "application/x-ndjson",
        "Content-Type": "application/json",
      },
      body: JSON.stringify({
        scenario: scenarioToJson(scenario),
        primary_route_strategy_id: primaryRoutingStrategyId,
        batch_size: batchSize,
      }),
    });

    if (!response.ok) {
      await readJson(response);
      throw new Error(`Backend returned HTTP ${response.status}`);
    }
    if (!response.body) throw new Error("Backend не поддерживает потоковый ответ");

    type StartEvent = {
      type: "start";
      routing_strategies: ModelRunData["routingStrategies"];
      primary_route_strategy_id: RoutingStrategyId;
      sampling: { start_s: number; end_s: number; step_s: number };
      total_frames: number;
      cache_hit?: boolean;
    };

    const decoder = new TextDecoder();
    const reader = response.body.getReader();
    let buffer = "";
    let start: StartEvent | null = null;
    let frames: unknown[] = [];
    let finalRun: ModelRunData | null = null;

    const partialRun = (dynamicAnalysis: unknown | null) => {
      if (!start) throw new Error("Backend прислал кадры до метаданных расчёта");
      return toStreamingModelRunData({
        scenario,
        routingStrategies: start.routing_strategies,
        primaryRoutingStrategyId: start.primary_route_strategy_id,
        sampling: start.sampling,
        frames,
        dynamicAnalysis,
      });
    };

    const handleLine = (line: string) => {
      if (!line.trim()) return;
      let event: Record<string, unknown>;
      try {
        const parsed = JSON.parse(line) as unknown;
        if (!parsed || typeof parsed !== "object") throw new Error("not an object");
        event = parsed as Record<string, unknown>;
      } catch {
        throw new Error("Backend прислал повреждённый NDJSON-поток");
      }

      if (event.type === "start") {
        const sampling = event.sampling;
        if (!sampling || typeof sampling !== "object" || !Array.isArray(event.routing_strategies)) {
          throw new Error("Backend прислал некорректные метаданные потокового расчёта");
        }
        start = event as unknown as StartEvent;
        return;
      }

      if (event.type === "frames") {
        if (!start || !Array.isArray(event.frames)) {
          throw new Error("Backend прислал некорректный батч кадров");
        }
        frames = [...frames, ...event.frames];
        const completedFrames = Number(event.completed_frames ?? frames.length);
        const totalFrames = Number(event.total_frames ?? start.total_frames);
        const run = partialRun(null);
        onUpdate(run, {
          completedFrames,
          totalFrames,
          phase: "frames",
          cacheHit: Boolean(start.cache_hit),
        });
        return;
      }

      if (event.type === "phase" && event.phase === "aggregating") {
        if (!start || !frames.length) return;
        const run = partialRun(null);
        onUpdate(run, {
          completedFrames: Number(event.completed_frames ?? frames.length),
          totalFrames: Number(event.total_frames ?? start.total_frames),
          phase: "aggregating",
          cacheHit: Boolean(start.cache_hit),
        });
        return;
      }

      if (event.type === "complete") {
        if (!start || !("dynamic_analysis" in event)) {
          throw new Error("Backend не прислал финальную динамическую аналитику");
        }
        finalRun = partialRun(event.dynamic_analysis);
        onUpdate(finalRun, {
          completedFrames: Number(event.completed_frames ?? frames.length),
          totalFrames: Number(event.total_frames ?? start.total_frames),
          phase: "complete",
          cacheHit: Boolean(event.cache_hit ?? start.cache_hit),
        });
        return;
      }

      if (event.type === "error") {
        throw new Error(typeof event.detail === "string" ? event.detail : "Ошибка потокового расчёта");
      }
    };

    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true });
      let newline = buffer.indexOf("\n");
      while (newline >= 0) {
        const line = buffer.slice(0, newline);
        buffer = buffer.slice(newline + 1);
        handleLine(line);
        newline = buffer.indexOf("\n");
      }
    }
    buffer += decoder.decode();
    if (buffer.trim()) handleLine(buffer);

    if (!finalRun) throw new Error("Поток расчёта завершился до финального результата");
    return finalRun;
  }


  /**
   * Start a bidirectional demand-driven calculation.  The backend keeps filling
   * the whole time grid in the background, but timeline focus messages preempt
   * queued work so the exact selected frame and its neighbours arrive first.
   */
  runModelContext(
    scenario: ScenarioDraft,
    primaryRoutingStrategyId: RoutingStrategyId,
    onUpdate: (run: ModelRunData, progress: ModelRunProgress) => void,
    options: { batchSize?: number; initialFocusTS?: number; focusRadiusS?: number } = {},
  ): ContextualModelRunController {
    return new BrowserContextualModelRun(
      this.baseUrl,
      scenario,
      primaryRoutingStrategyId,
      onUpdate,
      options.batchSize ?? 8,
      options.initialFocusTS ?? 0,
      options.focusRadiusS,
    );
  }

  async exportResult(scenario: ScenarioDraft): Promise<unknown> {
    return readJson(
      await fetch(`${this.baseUrl}/export/result`, {
        method: "POST",
        headers: { Accept: "application/json", "Content-Type": "application/json" },
        body: JSON.stringify({ scenario: scenarioToJson(scenario) }),
      }),
    );
  }
}

/** Compatibility wrapper for the existing export UI. */
export class HttpSimulationGateway {
  constructor(private readonly api = new ModelApiClient()) {}

  exportResult(scenario: ScenarioDraft): Promise<unknown> {
    return this.api.exportResult(scenario);
  }
}

function downloadJson(filename: string, payload: unknown) {
  const blob = new Blob([JSON.stringify(payload, null, 2)], {
    type: "application/json;charset=utf-8",
  });
  const url = URL.createObjectURL(blob);
  const link = document.createElement("a");
  link.href = url;
  link.download = filename;
  document.body.appendChild(link);
  link.click();
  link.remove();
  window.setTimeout(() => URL.revokeObjectURL(url), 0);
}

export async function saveFrontendWorkspaceState(
  payload: FrontendWorkspaceStateDto,
  baseUrl = "/api",
): Promise<WorkspaceSaveResult> {
  try {
    const response = await fetch(`${baseUrl}/workspace/state`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify(payload),
    });
    if (response.ok) return { storage: "backend" };
  } catch {
    // Offline/local development fallback: preserve the same JSON envelope.
  }

  const safeScenario = payload.scenario.id.replace(/[^a-zA-Z0-9._-]+/g, "-");
  const filename = `${safeScenario || "cosmo"}-state-${Math.round(payload.runtime.t_s)}s.json`;
  downloadJson(filename, payload);
  return { storage: "download", filename };
}

export async function compareScenarios(
  baseline: ScenarioDraft,
  variant: ScenarioDraft,
  baseUrl = "/api",
): Promise<unknown> {
  return readJson(
    await fetch(`${baseUrl}/query/compare`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({
        baseline: scenarioToJson(baseline),
        variant: scenarioToJson(variant),
      }),
    }),
  );
}
