import type { ScenarioDraft } from "../model/types";

export const DEFAULT_SCENARIO: ScenarioDraft = {
  id: "01_full_constellation",
  title: "Полная группировка",
  altitudeKm: 550,
  inclinationDeg: 87,
  launchStage: 3,
  islRangeKm: 3000,
  stepS: 120,
  horizonS: 86400,
  targetAvailability: 0.9,
};

export function scenarioFromJson(value: unknown): ScenarioDraft {
  if (!value || typeof value !== "object") {
    throw new Error("Файл должен содержать JSON-объект");
  }
  const source = value as Record<string, any>;
  const environment = source.environment ?? {};
  const design = source.design ?? {};
  return {
    id: String(source.meta?.id ?? "uploaded_scenario"),
    title: String(source.meta?.title ?? "Загруженный сценарий"),
    altitudeKm: Number(environment.altitude_km ?? 550),
    inclinationDeg: Number(environment.inclination_deg ?? 87),
    launchStage: Number(design.launch_stage ?? 3) as 1 | 2 | 3,
    islRangeKm: Number(environment.isl_range_km ?? 3000),
    stepS: Number(environment.step_s ?? 120),
    horizonS: Number(environment.horizon_s ?? 86400),
    targetAvailability: Number(environment.target_availability ?? 0.9),
  };
}
