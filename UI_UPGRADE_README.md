# UI upgrade: HD globe + hierarchical outliner

Если изменения накладываются на предыдущую версию вручную, замените файлы:

1. `frontend/src/shared/model/appStore.tsx`
2. `frontend/src/features/globe/GlobeView.tsx`
3. `frontend/src/features/globe/layers/SatellitesLayer.tsx`
4. `frontend/src/features/globe/layers/GroundSitesLayer.tsx`
5. `frontend/src/features/globe/layers/OrbitLayer.tsx`
6. `frontend/src/features/outliner/Outliner.tsx`
7. Добавьте `frontend/src/features/outliner/OutlinerTreeNode.tsx`
8. `frontend/src/styles/globe.css`
9. `frontend/README.md`

После замены:

```powershell
cd frontend
npm.cmd install
npm.cmd run dev
```

Отдельная установка пакетов не требуется: ArcGIS-провайдер и средства
повышения качества входят в уже установленный пакет Cesium.
