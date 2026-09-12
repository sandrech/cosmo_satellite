# Компонентная архитектура

## Базовая модель

Каждый процесс оформляется как заменяемый компонент с явным входом и выходом.
Координация выполняется композицией компонентов, а не вызовом глобальных функций.

### StaticModel

`StaticModel.calculate(scenario, t_s) -> Frame` рассчитывает полностью
независимый снимок сети в одной точке времени:

1. активный состав;
2. положение спутников;
3. наземную видимость;
4. ISL-контакты;
5. граф сети;
6. маршруты;
7. причины отсутствия маршрута.

Фиксация `t_s=0`, `t_s=120` и любого другого шага использует один и тот же
компонент. StaticModel не хранит состояние предыдущего шага.

### DynamicModel

`DynamicModel.run(scenario, time_grid) -> Iterable[Frame]` переиспользует
StaticModel. Он проходит по временной сетке и для каждого значения вызывает
`static_model.calculate(scenario, t_s)`. Формулы и правила контактов внутри
DynamicModel не дублируются.

```text
TimeGrid -> DynamicModel -> StaticModel.calculate(t0) -> Frame0
                         -> StaticModel.calculate(t1) -> Frame1
                         -> StaticModel.calculate(tN) -> FrameN
```

Абстракции заданы в
`backend/app/domain/modeling/contracts.py`, а будущие реализации размещаются в
`static_model.py` и `dynamic_model.py`.

## Переиспользуемые компоненты

Внутри StaticModel используются заменяемые компоненты:

- PositionProvider;
- ActivationPolicy;
- GroundVisibilityProvider;
- InterSatelliteContactProvider;
- NetworkGraphBuilder;
- RouteProvider;
- OutageReasonProvider.

DynamicModel передаёт полученные кадры компонентам:

- MetricCalculator;
- ResilienceAnalyzer;
- VariantComparator;
- RecommendationBuilder.

Каждый компонент должен зависеть от абстракций соседнего компонента, а не от
конкретной реализации.

## Компонентный frontend

Frontend не зависит от Python-моделей напрямую:

```text
Page -> reusable UI components -> SimulationGateway -> adapter
                                                 ├─ MockSimulationGateway
                                                 └─ HttpSimulationGateway
```

Сейчас приложение использует mock-адаптер. Он формирует демонстрационные кадры
для проверки интерфейса. После появления backend меняется только провайдер
`SimulationGateway`; Globe, Timeline, Outliner, Inspector и страницы остаются
без изменений.

## Слои

### 1. Контракты и данные

`contracts/` описывает входной сценарий `cosmo-A-1.0`, экспорт результата
`cosmo-A-result-1.0` и HTTP API. `data/scenarios/` содержит проверочные
наборы, но код не должен зависеть от конкретных идентификаторов этих файлов.

### 2. Domain

В `backend/app/domain/` размещаются детерминированные функции предметной
области. Они не знают о FastAPI, базе данных, React или Cesium.

- `scenario`: чтение, модели, валидация, применение изменений.
- `geometry`: координаты, вращение Земли, наземные точки, видимость, ISL,
  солнечный свет.
- `network`: активный состав, граф, маршрут, объяснение разрыва.
- `analysis`: временная сетка, прогон, метрики, устойчивость, сравнение,
  рекомендации.

### 3. Application

`backend/app/application/` содержит варианты использования: загрузить сценарий,
запустить расчёт, получить кадр, сравнить варианты и экспортировать результат.
Сервисы координируют domain и репозитории, но не повторяют формулы.

### 4. API и хранение

`backend/app/api/` переводит HTTP-запросы в вызовы application-сервисов.
`backend/app/infrastructure/` хранит сценарии, запуски и кэш кадров. Смену
in-memory хранения на БД следует выполнять только здесь.

### 5. Frontend

`frontend/src/pages/` собирает экраны, а `frontend/src/features/` содержит
законченные функции интерфейса. `GlobeView` и слои Cesium только отображают
готовый backend-frame.

## Поток расчёта

1. Загрузить JSON.
2. Проверить схему, значения, идентификаторы, ссылки и интервалы отказов.
3. Применить изменения пользователя и сформировать effective scenario.
4. Построить временную сетку `0 .. horizon_s - step_s`.
5. Для каждого `t_s` определить активные аппараты и шлюзы.
6. Рассчитать Earth-fixed координаты.
7. Построить наземные и межспутниковые контакты.
8. Собрать неориентированный граф допустимых связей.
9. Для каждого client найти путь до доступного gateway.
10. При отсутствии пути определить причину.
11. Сохранить frame и запись route.
12. Рассчитать видимость, доступность, максимальные перерывы и характеристики
    маршрутов.
13. Сопоставить варианты на одинаковой временной сетке.
14. Сформировать рекомендацию и ограничения.
15. Отдать UI кадры/метрики или выгрузить scenario/result JSON.

## Зависимости между слоями

```text
api -> application -> domain
                  -> infrastructure

frontend -> api contract
domain   -> no web/UI/storage dependencies
```

## Идентификаторы результатов

После каждого запуска application-слой создаёт `run_id`. Один run хранит:

- effective scenario;
- все frames по расчётной сетке;
- routes для каждой пары `t_s + client_id`;
- агрегированные metrics;
- сведения об ошибках/ограничениях.

Это позволяет timeline получать кадр без повторного полного расчёта.
