import { useAppState } from "../../shared/model/store";

export function OutageExplanation() {
  const { frame, clientId, tS } = useAppState();
  const available = Boolean(frame?.route.length);
  return (
    <article className={`explanation-card ${available ? "ok" : "warning"}`}>
      <div>
        <span className="eyebrow">{clientId} · t={tS} с</span>
        <h3>{available ? "Маршрут сохраняется" : "Маршрут отсутствует"}</h3>
      </div>
      <div className="check-list">
        <span>✓ Client → satellite</span>
        <span>✓ Gateway → satellite</span>
        <span>{available ? "✓" : "×"} ISL route</span>
      </div>
      <p>{available ? `Текущий путь: ${frame?.route.join(" → ")}` : frame?.outageReason}</p>
    </article>
  );
}
