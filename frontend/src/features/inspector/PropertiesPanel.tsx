import { useAppState } from "../../shared/model/store";

function number(value: number) {
  return new Intl.NumberFormat("ru-RU", {
    maximumFractionDigits: 1,
  }).format(value);
}

export function PropertiesPanel() {
  const { frame, selectedId } = useAppState();
  const satellite = frame?.satellites.find((item) => item.id === selectedId);
  const site = frame?.groundSites.find((item) => item.id === selectedId);

  return (
    <section className="sidebar-section inspector">
      <h2>☼ Свойства</h2>
      {!satellite && !site && (
        <p className="empty-copy">Выберите объект на глобусе или в аутлайнере.</p>
      )}
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
            <dt>Роль</dt><dd>{site.role}</dd>
            <dt>Широта</dt><dd>{site.latDeg}°</dd>
            <dt>Долгота</dt><dd>{site.lonDeg}°</dd>
          </dl>
        </div>
      )}
    </section>
  );
}
