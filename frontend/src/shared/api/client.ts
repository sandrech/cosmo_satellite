import type {
  ModelRunData,
  ModelSummary,
  RoutingStrategyId,
  ScenarioDraft,
  SimulationFrame,
} from "../model/types";
import type { FrontendWorkspaceStateDto } from "./frontendJsonAdapter";
import {
  isModelRunResponse,
  toModelRunData,
} from "./modelRunAdapter";
import { scenarioFromJson, scenarioToJson } from "./scenarios";


// Kept for the isolated legacy mock module/tests. The production store uses ModelApiClient.
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

async function jsonOrThrow(response: Response) {
  if (!response.ok) {
    let detail = `HTTP ${response.status}`;
    try {
      const body = await response.json();
      detail = String(body?.detail ?? body?.message ?? detail);
    } catch {
      // keep HTTP status
    }
    throw new Error(detail);
  }
  return response.json() as Promise<unknown>;
}

export class ModelApiClient {
  constructor(private readonly baseUrl = "/api") {}

  async listModels(): Promise<ModelSummary[]> {
    const payload = await jsonOrThrow(
      await fetch(`${this.baseUrl}/models`, {
        headers: { Accept: "application/json" },
      }),
    );
    if (!Array.isArray(payload)) throw new Error("Некорректный список моделей от backend");
    return payload.map((item: any) => ({
      id: String(item.id),
      title: String(item.title ?? item.id),
      filename: String(item.filename ?? `${item.id}.json`),
    }));
  }

  async getModel(id: string): Promise<ScenarioDraft> {
    const payload = await jsonOrThrow(
      await fetch(`${this.baseUrl}/models/${encodeURIComponent(id)}`, {
        headers: { Accept: "application/json" },
      }),
    );
    return scenarioFromJson(payload);
  }

  /**
   * Calculate the complete official time grid in one backend call.
   * Timeline scrubbing afterwards is local and causes no per-frame HTTP roundtrip.
   */
  async runModel(
    scenario: ScenarioDraft,
    primaryRoutingStrategyId: RoutingStrategyId,
  ): Promise<ModelRunData> {
    const payload = await jsonOrThrow(
      await fetch(`${this.baseUrl}/model/run`, {
        method: "POST",
        headers: {
          Accept: "application/json",
          "Content-Type": "application/json",
        },
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
    const response = await fetch(`${baseUrl}/runs/current/state`, {
      method: "POST",
      headers: {
        Accept: "application/json",
        "Content-Type": "application/json",
      },
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
