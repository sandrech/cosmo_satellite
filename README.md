# Веб-сервис для проектирования и анализа устойчивой спутниковой группировки.

## Структура

backend/ — статическая модель одного момента времени, динамическая модель и API.

frontend/ — React-интерфейс и 3D-глобус Cesium.

contracts/ — контракты сценария, результата и API.

data/ — входные сценарии и выгрузки.

docs/ — архитектура и исходная документация.

Сейчас frontend работает автономно через MockSimulationGateway, без backend.

## Установка и запуск

Требуется Node.js LTS.

Windows

```
cd cosmo_satellite_project\frontend
npm.cmd install
npm.cmd run dev
```
Linux

```
cd cosmo_satellite_project/frontend
npm install
npm run dev
```
Открыть: http://127.0.0.1:5173