import { useState } from "react";
import { compareScenarios } from "../shared/api/client";
import { scenarioFromJson } from "../shared/api/scenarios";
import { useAppState } from "../shared/model/store";
import type { ScenarioDraft } from "../shared/model/types";

type MetricDelta = { baseline: number | null; variant: number | null; delta: number | null };
type ComparisonPayload = {
  schema_version: "variant-comparison-2.0";
  comparisons: Array<{
    configuration_changes: Array<{ path: string; baseline: unknown; variant: unknown; numeric_delta: number | null }>;
    network: { minimum_n_minus_one_fraction: MetricDelta; minimum_service_availability: MetricDelta; maximum_client_outage_s: MetricDelta };
    clients: Array<{
      client_id: string;
      presence: string;
      service_availability: MetricDelta;
      maximum_outage_s: MetricDelta;
      n_minus_one_fraction: MetricDelta;
      baseline_meets_target: boolean | null;
      variant_meets_target: boolean | null;
    }>;
  }>;
};

function isComparison(value: unknown): value is ComparisonPayload {
  return Boolean(value) && typeof value === "object" && (value as { schema_version?: string }).schema_version === "variant-comparison-2.0";
}

function pct(value: number | null) { return value == null ? "—" : `${(value * 100).toFixed(2)}%`; }
function minutes(value: number | null) { return value == null ? "—" : `${(value / 60).toFixed(1)} мин`; }

export function ComparisonPage() {
  const { scenario } = useAppState();
  const [variant, setVariant] = useState<ScenarioDraft | null>(null);
  const [report, setReport] = useState<ComparisonPayload | null>(null);
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  async function loadVariant(file?: File) {
    if (!file) return;
    try {
      setVariant(scenarioFromJson(JSON.parse(await file.text())));
      setReport(null);
      setError(null);
    } catch (reason) {
      setError(reason instanceof Error ? reason.message : "Некорректный вариант");
    }
  }

  const comparison = report?.comparisons[0];
  return (
    <main className="page content-page">
      <header className="page-title"><div><span className="eyebrow">A/B-анализ</span><h1>Сравнение вариантов</h1></div></header>
      <section className="content-card">
        <h3>Варианты</h3>
        <p>Baseline: <strong>{scenario.title}</strong>. Загрузите второй полный cosmo-A-1.0 сценарий.</p>
        <input type="file" accept=".json,application/json" onChange={(event) => loadVariant(event.target.files?.[0])} />
        <button className="primary-button" disabled={!variant || busy} onClick={async () => {
          if (!variant) return;
          setBusy(true); setError(null);
          try {
            const payload = await compareScenarios(scenario, variant);
            if (!isComparison(payload)) throw new Error("Некорректный variant-comparison-2.0");
            setReport(payload);
          } catch (reason) { setError(reason instanceof Error ? reason.message : "Ошибка сравнения"); }
          finally { setBusy(false); }
        }}>{busy ? "Сравнение…" : "Сравнить"}</button>
        {variant ? <p>Variant: <strong>{variant.title}</strong></p> : null}
        {error ? <p className="error-text">{error}</p> : null}
      </section>

      {comparison ? <>
        <section className="content-card comparison-table">
          <h3>Изменения конфигурации</h3>
          {comparison.configuration_changes.length ? comparison.configuration_changes.map((change) => (
            <div className="comparison-row" key={change.path}><strong>{change.path}</strong><span>{String(change.baseline)}</span><span>{String(change.variant)}</span><span>{change.numeric_delta ?? "—"}</span></div>
          )) : <p>Параметры конфигурации совпадают.</p>}
        </section>
        <section className="content-card comparison-table">
          <h3>Результаты по наземным пунктам</h3>
          <div className="comparison-head"><span>Пункт</span><span>Доступность A</span><span>Доступность B</span><span>Макс. перерыв A/B</span></div>
          {comparison.clients.filter((client) => client.presence === "common").map((client) => (
            <div className="comparison-row" key={client.client_id}>
              <strong>{client.client_id}</strong>
              <span>{pct(client.service_availability.baseline)}</span>
              <span>{pct(client.service_availability.variant)}</span>
              <span>{minutes(client.maximum_outage_s.baseline)} / {minutes(client.maximum_outage_s.variant)}</span>
            </div>
          ))}
        </section>
        <section className="content-card">
          <h3>Устойчивость</h3>
          <p>Минимальная N−1 доля: {pct(comparison.network.minimum_n_minus_one_fraction.baseline)} → {pct(comparison.network.minimum_n_minus_one_fraction.variant)}</p>
          <p>Минимальная доступность: {pct(comparison.network.minimum_service_availability.baseline)} → {pct(comparison.network.minimum_service_availability.variant)}</p>
          <p>Худший перерыв: {minutes(comparison.network.maximum_client_outage_s.baseline)} → {minutes(comparison.network.maximum_client_outage_s.variant)}</p>
        </section>
      </> : null}
    </main>
  );
}
