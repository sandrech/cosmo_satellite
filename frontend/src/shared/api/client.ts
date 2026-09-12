import type { ScenarioDraft, SimulationFrame } from "../model/types";
import {
  adaptFrontendFrameBundle,
  isFrontendFrameBundle,
  type FrontendWorkspaceStateDto,
} from "./frontendJsonAdapter";

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

function isSimulationFrame(value: unknown): value is SimulationFrame {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<SimulationFrame>;
  return (
    Array.isArray(candidate.satellites) &&
    Array.isArray(candidate.groundSites) &&
    Array.isArray(candidate.links) &&
    typeof candidate.tS === "number"
  );
}

export class HttpSimulationGateway implements SimulationGateway {
  constructor(private readonly baseUrl = "/api") {}

  async getFrame(request: FrameRequest): Promise<SimulationFrame> {
    const query = new URLSearchParams({
      t_s: String(request.tS),
      client_id: request.clientId,
      scenario_id: request.scenario.id,
    });
    const response = await fetch(
      `${this.baseUrl}/runs/current/frame?${query.toString()}`,
      { headers: { Accept: "application/json" } },
    );
    if (!response.ok) {
      throw new Error(`Backend returned HTTP ${response.status}`);
    }

    const payload: unknown = await response.json();
    if (isFrontendFrameBundle(payload)) {
      return adaptFrontendFrameBundle(payload, request);
    }
    if (isSimulationFrame(payload)) {
      return { ...payload, source: "backend" };
    }
    throw new Error("Backend frame has an unsupported JSON contract");
  }
}

export class FallbackSimulationGateway implements SimulationGateway {
  private backendAvailable: boolean | null = null;

  constructor(
    private readonly backend: SimulationGateway,
    private readonly fallback: SimulationGateway,
  ) {}

  async getFrame(request: FrameRequest): Promise<SimulationFrame> {
    if (this.backendAvailable !== false) {
      try {
        const frame = await this.backend.getFrame(request);
        this.backendAvailable = true;
        return frame;
      } catch {
        this.backendAvailable = false;
      }
    }
    return this.fallback.getFrame(request);
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

/**
 * Save through the backend JSON transport when that endpoint is available.
 * Until the HTTP backend is wired, the exact same versioned DTO is downloaded
 * locally, so the Save button remains fully functional in mock/offline mode.
 */
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

    if (response.ok) {
      return { storage: "backend" };
    }
  } catch {
    // The backend HTTP layer is optional in the current branch. Fall through
    // to a local JSON save using the same frontend_json contract.
  }

  const safeScenario = payload.scenario.id.replace(/[^a-zA-Z0-9._-]+/g, "-");
  const filename = `${safeScenario || "cosmo"}-state-${Math.round(payload.runtime.t_s)}s.json`;
  downloadJson(filename, payload);
  return { storage: "download", filename };
}
