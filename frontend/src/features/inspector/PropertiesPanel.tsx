import { useAppState } from "../../shared/model/store";

function number(value: number) {
  return new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 1,
  }).format(value);
}

export function PropertiesPanel() {
  const { frame, selectedId, setSelectedId } = useAppState();
  const satellite = frame?.satellites.find((item) => item.id === selectedId);
  const site = frame?.groundSites.find((item) => item.id === selectedId);

  if (!selectedId || (!satellite && !site)) return null;

  return (
    <section className="sidebar-section inspector">
      <header className="sidebar-heading">
        <h2>Свойства</h2>
        <button
          className="sidebar-close"
          type="button"
          onClick={() => setSelectedId(null)}
          aria-label="Закрыть подробную информацию"
          title="Закрыть"
        >
          ×
        </button>
      </header>

      {satellite && (
        <div className="property-list">
          <h3>{satellite.id}</h3>
          <dl>
            <dt>Статус</dt><dd>{satellite.failed ? "Отказ" : satellite.active ? "Активен" : "Не запущен"}</dd>
            <dt>Плоскость</dt><dd>{satellite.planeId}</dd>
            <dt>Очередь</dt><dd>{satellite.launchBatch}</dd>
            <dt>X</dt><dd>{number(satellite.position.xKm)} км</dd>
            <dt>Y</dt><dd>{number(satellite.position.yKm)} км</dd>
            <dt>Z</dt><dd>{number(satellite.position.zKm)} км</dd>
            <dt>В маршруте</dt><dd>{frame?.route.includes(satellite.id) ? "Да" : "Нет"}</dd>
          </dl>
        </div>
      )}

      {site && (
        <div className="property-list">
          <h3>{site.name}</h3>
          <dl>
            <dt>ID</dt><dd>{site.id}</dd>
            <dt>Роль</dt><dd>{site.role === "gateway" ? "Шлюз" : "Клиент"}</dd>
            <dt>Широта</dt><dd>{site.latDeg}°</dd>
            <dt>Долгота</dt><dd>{site.lonDeg}°</dd>
          </dl>
        </div>
      )}
    </section>
  );
}