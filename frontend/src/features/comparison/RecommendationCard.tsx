export function RecommendationCard() {
  return (
    <section className="recommendation-card">
      <span className="eyebrow">Рекомендация · demo</span>
      <h2>Рекомендуем вариант B</h2>
      <p>Все три наземных пункта достигают целевой доступности не менее 90%.</p>
      <div className="recommendation-columns">
        <div><strong>Преимущества</strong><span>C65: +4.2 п.п.</span><span>Худший перерыв: −22 мин</span><span>Цель достигнута для 3/3 пунктов</span></div>
        <div><strong>Ограничения</strong><span>Оценка для ISL 3000 км</span><span>Использован демонстрационный набор отказов</span><span>Подключение backend ещё выключено</span></div>
      </div>
    </section>
  );
}
