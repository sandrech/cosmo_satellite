import { useAppState } from "../../shared/model/store";
import type { GatewayOutageDraft, SatelliteOutageDraft } from "../../shared/model/types";

function numberValue(value: string) {
  const parsed = Number(value);
  return Number.isFinite(parsed) ? parsed : 0;
}

export function FailureEditor() {
  const { scenario, setScenario } = useAppState();
  const gateways = scenario.groundSites.filter((site) => site.role === "gateway");

  const setFailures = (failures: SatelliteOutageDraft[]) =>
    setScenario({ ...scenario, failures });
  const setGatewayOutages = (gatewayOutages: GatewayOutageDraft[]) =>
    setScenario({ ...scenario, gatewayOutages });

  const patchFailure = (index: number, next: Partial<SatelliteOutageDraft>) =>
    setFailures(
      scenario.failures.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...next } : item,
      ),
    );

  const patchGateway = (index: number, next: Partial<GatewayOutageDraft>) =>
    setGatewayOutages(
      scenario.gatewayOutages.map((item, itemIndex) =>
        itemIndex === index ? { ...item, ...next } : item,
      ),
    );

  return (
    <div className="failure-editor">
      <section className="failure-block">
        <div className="section-heading compact-heading">
          <div>
            <h3>Отказы спутников</h3>
            <p>Это реальные поля <code>failures</code> сценария; они уйдут в backend при пересчёте.</p>
          </div>
          <button
            className="secondary-button"
            type="button"
            disabled={scenario.satellites.length === 0}
            onClick={() =>
              setFailures([
                ...scenario.failures,
                {
                  satelliteId: scenario.satellites[0]?.id ?? "",
                  startS: 0,
                  endS: Math.min(scenario.horizonS, Math.max(scenario.stepS, 3600)),
                },
              ])
            }
          >
            + Отказ
          </button>
        </div>

        {scenario.failures.length === 0 ? (
          <p className="empty-copy">Заданных отказов спутников нет.</p>
        ) : (
          <div className="outage-table">
            <div className="outage-table-head"><span>Спутник</span><span>Начало, с</span><span>Конец, с</span><span /></div>
            {scenario.failures.map((item, index) => (
              <div className="outage-table-row" key={`${item.satelliteId}-${index}`}>
                <select value={item.satelliteId} onChange={(event) => patchFailure(index, { satelliteId: event.target.value })}>
                  {scenario.satellites.map((satellite) => <option key={satellite.id} value={satellite.id}>{satellite.id}</option>)}
                </select>
                <input type="number" min={0} max={scenario.horizonS} value={item.startS} onChange={(event) => patchFailure(index, { startS: numberValue(event.target.value) })} />
                <input type="number" min={0} max={scenario.horizonS} value={item.endS} onChange={(event) => patchFailure(index, { endS: numberValue(event.target.value) })} />
                <button className="row-delete" type="button" onClick={() => setFailures(scenario.failures.filter((_, itemIndex) => itemIndex !== index))}>×</button>
              </div>
            ))}
          </div>
        )}
      </section>

      <section className="failure-block">
        <div className="section-heading compact-heading">
          <div>
            <h3>Недоступность шлюзов</h3>
            <p>Поля <code>gateway_outages</code> также участвуют в полном динамическом расчёте.</p>
          </div>
          <button
            className="secondary-button"
            type="button"
            disabled={gateways.length === 0}
            onClick={() =>
              setGatewayOutages([
                ...scenario.gatewayOutages,
                {
                  gatewayId: gateways[0]?.id ?? "",
                  startS: 0,
                  endS: Math.min(scenario.horizonS, Math.max(scenario.stepS, 3600)),
                },
              ])
            }
          >
            + Интервал
          </button>
        </div>

        {scenario.gatewayOutages.length === 0 ? (
          <p className="empty-copy">Интервалы недоступности шлюзов не заданы.</p>
        ) : (
          <div className="outage-table">
            <div className="outage-table-head"><span>Шлюз</span><span>Начало, с</span><span>Конец, с</span><span /></div>
            {scenario.gatewayOutages.map((item, index) => (
              <div className="outage-table-row" key={`${item.gatewayId}-${index}`}>
                <select value={item.gatewayId} onChange={(event) => patchGateway(index, { gatewayId: event.target.value })}>
                  {gateways.map((gateway) => <option key={gateway.id} value={gateway.id}>{gateway.id}</option>)}
                </select>
                <input type="number" min={0} max={scenario.horizonS} value={item.startS} onChange={(event) => patchGateway(index, { startS: numberValue(event.target.value) })} />
                <input type="number" min={0} max={scenario.horizonS} value={item.endS} onChange={(event) => patchGateway(index, { endS: numberValue(event.target.value) })} />
                <button className="row-delete" type="button" onClick={() => setGatewayOutages(scenario.gatewayOutages.filter((_, itemIndex) => itemIndex !== index))}>×</button>
              </div>
            ))}
          </div>
        )}
      </section>
    </div>
  );
}
