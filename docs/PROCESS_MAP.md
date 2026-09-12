# Карта процессов и файлов

| Процесс | Основные файлы |
| --- | --- |
| Загрузка JSON | `domain/scenario/loader.py` |
| Валидация входа | `domain/scenario/validator.py` |
| Редактирование и effective scenario | `domain/scenario/editor.py` |
| Временная сетка | `domain/analysis/time_grid.py` |
| Состав запущенных и отказавших аппаратов | `domain/network/activation.py` |
| Орбитальные координаты | `domain/geometry/orbit.py` |
| Earth-fixed преобразование | `domain/geometry/earth.py` |
| Координаты наземных пунктов | `domain/geometry/ground.py` |
| Угол возвышения | `domain/geometry/visibility.py` |
| Наземные и ISL-контакты | `domain/geometry/contacts.py` |
| Солнечный свет/тень | `domain/geometry/sunlight.py` |
| Граф сети | `domain/network/graph.py` |
| Поиск маршрута | `domain/network/routing.py` |
| Причина отсутствия маршрута | `domain/network/outage_reason.py` |
| Статический кадр в точке времени | `domain/modeling/static_model.py` |
| Динамический прогон временной сетки | `domain/modeling/dynamic_model.py` |
| Доступность и перерывы | `domain/analysis/metrics.py` |
| Влияние отказов | `domain/analysis/resilience.py` |
| Сравнение A/B | `domain/analysis/comparison.py` |
| Рекомендации и ограничения | `domain/analysis/recommendations.py` |
| Оркестрация расчёта | `application/run_service.py` |
| Получение одного кадра | `application/frame_service.py` |
| Экспорт JSON | `application/export_service.py` |
| REST API | `api/routes/*.py` |
| 3D-глобус и выбор объектов | `frontend/src/features/globe` |
| Временная шкала и playback | `frontend/src/features/timeline` |
| KPI и диаграмма доступности | `frontend/src/features/metrics` |
| Анализ устойчивости | `frontend/src/features/resilience` |
| Сравнение вариантов | `frontend/src/features/comparison` |

## Как разнести исходный geometry.py

- константы `R`, `MU`, `OMEGA` → `geometry/constants.py`;
- `load` → `scenario/loader.py`;
- `validate` → `scenario/validator.py`;
- `positions` → `geometry/orbit.py` и `geometry/earth.py`;
- `ground_position` → `geometry/ground.py`;
- расчёт elevation/контактов из `snapshot` → `visibility.py` и `contacts.py`;
- выбор active/failed из `snapshot` → `network/activation.py`;
- сбор итогового кадра → `modeling/static_model.py`;
- прогон временной сетки → `modeling/dynamic_model.py`, переиспользующий StaticModel;
- `sunlight` → `geometry/sunlight.py`.

Так официальный расчёт не теряется, но перестаёт быть одним монолитным файлом.

## Минимальные тестовые уровни

- Unit: формулы и пограничные условия каждого domain-модуля.
- Integration: полный run и API на четырёх исходных сценариях.
- Frontend: связывание selection, timeline, client и полученного frame.
- Contract: вход и экспорт валидируются по JSON Schema.
