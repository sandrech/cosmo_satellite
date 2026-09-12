import { useAppState } from "../../shared/model/store";

export function ResilienceSummary() {
  const { frame } = useAppState();
  const failed = frame?.satellites.filter((item) => item.failed) ?? [];
  return (
    <div className="summary-grid">
      <article><span>Отказавшие аппараты</span><strong>{failed.length}</strong><small>{failed.map((item) => item.id).join(", ") || "нет"}</small></article>
      <article><span>Пункты с маршрутом</span><strong>{frame?.route.length ? "3/3" : "2/3"}</strong><small>на выбранном шаге</small></article>
      <article><span>Худший перерыв</span><strong>16 мин</strong><small>клиент C65</small></article>
    </div>
  );
}
