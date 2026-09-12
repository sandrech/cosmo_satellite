import type { ScenarioDraft, SimulationFrame } from "../model/types";
import {
  adaptModelSnapshot,
  adaptDynamicAnalysis,
  isDynamicAnalysisDto,
  isModelSnapshotDto,
  type DynamicAnalysisView,
  type FrontendWorkspaceStateDto,
} from "./frontendJsonAdapter";

export interface FrameRequest {
  scenario: ScenarioDraft;
  tS: number;
  clientId: string;
}

export interface SimulationGateway {
  getFrame(request: FrameRequest): Promise<SimulationFrame>;
  getDynamicAnalysis?(scenario: ScenarioDraft): Promise<DynamicAnalysisView>;
  exportResult?(scenario: ScenarioDraft): Promise<unknown>;
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
    const error = payload && typeof payload === "object" && "error" in payload
      ? (payload as { error?: { message?: string } }).error?.message
      : null;

    if (error) throw new Error(error);
    if (response.status >= 500 && !body) {
      throw new Error(
        "Backend API недоступен. Запускай весь проект через ./scripts/run_dev.sh " +
        "или npm run dev из frontend/; Python backend должен быть доступен на 127.0.0.1:8000.",
      );
    }
    throw new Error(`Backend returned HTTP ${response.status}`);
  }

  if (!body) throw new Error("Backend returned an empty response");
  if (payload === null) throw new Error("Backend returned invalid JSON");
  return payload;
}

export class HttpSimulationGateway implements SimulationGateway {
  constructor(private readonly baseUrl = "/api") {}

  async getFrame(request: FrameRequest): Promise<SimulationFrame> {
    const response = await fetch(`${this.baseUrl}/query/snapshot`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ scenario: request.scenario.canonical, t_s: request.tS }),
    });
    const payload = await readJson(response);
    if (!isModelSnapshotDto(payload)) {
      throw new Error("Backend returned an invalid model-snapshot-2.0 payload");
    }
    return adaptModelSnapshot(payload, request);
  }

  async getDynamicAnalysis(scenario: ScenarioDraft): Promise<DynamicAnalysisView> {
    const response = await fetch(`${this.baseUrl}/query/dynamic`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ scenario: scenario.canonical }),
    });
    const payload = await readJson(response);
    if (!isDynamicAnalysisDto(payload)) {
      throw new Error("Backend returned an invalid dynamic-analysis-2.0 payload");
    }
    return adaptDynamicAnalysis(payload);
  }

  async exportResult(scenario: ScenarioDraft): Promise<unknown> {
    const response = await fetch(`${this.baseUrl}/export/result`, {
      method: "POST",
      headers: { Accept: "application/json", "Content-Type": "application/json" },
      body: JSON.stringify({ scenario: scenario.canonical }),
    });
    return readJson(response);
  }
}

/** Explicit opt-in fallback for demos/tests only. Never used by the default app. */
export class FallbackSimulationGateway implements SimulationGateway {
  constructor(
    private readonly backend: SimulationGateway,
    private readonly fallback: SimulationGateway,
  ) {}

  async getFrame(request: FrameRequest): Promise<SimulationFrame> {
    try {
      return await this.backend.getFrame(request);
    } catch {
      return this.fallback.getFrame(request);
    }
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
    // Saving the workbench itself may fall back to a local file; calculation data never does.
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
  const response = await fetch(`${baseUrl}/query/compare`, {
    method: "POST",
    headers: { Accept: "application/json", "Content-Type": "application/json" },
    body: JSON.stringify({ baseline: baseline.canonical, variant: variant.canonical }),
  });
  return readJson(response);
}
