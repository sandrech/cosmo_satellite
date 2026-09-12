# Cosmo Satellite

Веб-сервис проектирования и анализа устойчивой спутниковой группировки.

## Что работает

- строгий импорт полного `cosmo-A-1.0` сценария;
- математический `spatial3d` snapshot в произвольный момент;
- статическая маршрутизация, N−1 и анализ отказов;
- динамическая аналитика периода;
- сравнение двух сценариев;
- канонический `cosmo-A-result-1.0` экспорт;
- HTTP application boundary и React/Cesium UI.

## Быстрый запуск

Требуются Python 3.12+ и Node.js. Один раз установите зависимости:

```bash
python3 -m venv .venv
. ./venv/bin/activate
python3 -m pip install -e ./backend
cd frontend && npm install && cd ..
```

После этого запускайте **весь стек**, а не отдельный Vite:

```bash
./scripts/run_dev.sh
```

То же самое из каталога `frontend/`:

```bash
npm run dev
```

Обе команды сначала запускают Python backend, ждут успешный `/api/health` и только затем запускают Vite. Если Python backend не стартует, скрипт завершается с его реальной ошибкой вместо пустого HTTP 500 от Vite proxy.

Backend: `http://127.0.0.1:8000`, frontend: `http://127.0.0.1:5173`. Vite проксирует `/api` в Python backend. Для намеренного запуска одного только Vite существует `npm run dev:frontend`.

Проверка проекта:

```bash
./scripts/test.sh
```

Mock-режим больше не включается при ошибке backend автоматически. Для явного демонстрационного запуска можно задать `VITE_USE_MOCK=1`; это режим UI-демонстрации, а не результат расчёта.

## Структура

- `backend/` — domain-модели, JSON adapters и `backend_api`;
- `frontend/` — React/Cesium UI;
- `contracts/` — OpenAPI и JSON Schema;
- `data/scenarios/` — исходные сценарии;
- `data/exports/` — сохранения/экспорты;
- `infra/` — docker-compose/nginx.
