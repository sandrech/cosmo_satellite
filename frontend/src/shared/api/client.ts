import type {
  ModelRunData,
  ModelSummary,
  RoutingStrategyId,
  ScenarioDraft,
  SimulationFrame,
} from "../model/types";
import type { FrontendWorkspaceStateDto } from "./frontendJsonAdapter";
import { isModelRunResponse, toModelRunData } from "./modelRunAdapter";
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
