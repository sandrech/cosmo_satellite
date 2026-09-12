import type { ScenarioDraft, SimulationFrame } from "../model/types";

export interface FrameRequest {
  scenario: ScenarioDraft;
  tS: number;
  clientId: string;
}

export interface SimulationGateway {
  getFrame(request: FrameRequest): Promise<SimulationFrame>;
}

export class HttpSimulationGateway implements SimulationGateway {
  constructor(private readonly baseUrl = "/api") {}

  async getFrame(request: FrameRequest): Promise<SimulationFrame> {
    const query = new URLSearchParams({
      t_s: String(request.tS),
      client_id: request.clientId,
    });
    const response = await fetch(
      `${this.baseUrl}/runs/current/frame?${query.toString()}`,
    );
    if (!response.ok) {
      throw new Error(`Backend returned HTTP ${response.status}`);
    }
    return response.json() as Promise<SimulationFrame>;
  }
}
