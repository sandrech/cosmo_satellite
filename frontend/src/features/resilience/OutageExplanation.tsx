import { useAppState } from "../../shared/model/store";

const LABELS: Record<string, string> = {
  no_visible_satellite: "Нет видимого активного спутника",
  isl_disconnected: "Спутниковая сеть не соединяет клиента со шлюзом",
  no_gateway_contact: "Нет спутникового контакта с доступным шлюзом",
  gateway_unavailable: "Шлюз недоступен",
};

export function OutageExplanation() {
  const { frame, clientId, tS } = useAppState();
  const available = Boolean(frame?.route.length);
  const reason = frame?.outageReason ? LABELS[frame.outageReason] ?? frame.outageReason : null;
  return (
    <article className={`explanation-card ${available ? "ok" : "warning"}`}>
      <div><span className="eyebrow">{clientId} · t={tS} с</span><h3>{available ? "Маршрут сохраняется" : "Маршрут отсутствует"}</h3></div>
      <p>{available ? `Текущий путь: ${frame?.route.join(" → ")}` : reason ?? "Причина не определена"}</p>
    </article>
  );
}
