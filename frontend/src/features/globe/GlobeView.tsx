import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArcGisMapServerImageryProvider,
  Cartesian3,
  Color,
  OpenStreetMapImageryProvider,
  type ImageryProvider,
} from "cesium";
import { Globe, ImageryLayer, Viewer } from "resium";
import "cesium/Build/Cesium/Widgets/widgets.css";
import { useAppState } from "../../shared/model/store";
import { createPositionIndex } from "./cesiumCoordinates";
import { GroundSitesLayer } from "./layers/GroundSitesLayer";
import { NetworkLayer } from "./layers/NetworkLayer";
import { OrbitLayer } from "./layers/OrbitLayer";
import { RouteLayer } from "./layers/RouteLayer";
import { SatellitesLayer } from "./layers/SatellitesLayer";
import { useGlobePicking } from "./useGlobePicking";
import { LoadingState } from "../../shared/ui/LoadingState";
import { ErrorState } from "../../shared/ui/ErrorState";

export function GlobeView() {
  const {
    frame,
    loading,
    error,
    clientId,
    setClientId,
    selectedId,
    setSelectedId,
    layers,
    viewMode,
    hiddenNodeIds,
  } = useAppState();
  const viewerRef = useRef<any>(null);
  const cameraInitialized = useRef(false);
  const [imagery, setImagery] = useState<ImageryProvider | null>(null);
  const [imageryName, setImageryName] = useState("загрузка HD");
  const hiddenNodes = useMemo(() => new Set(hiddenNodeIds), [hiddenNodeIds]);
  const positions = useMemo(
    () => (frame ? createPositionIndex(frame) : new Map()),
    [frame],
  );
  const picking = useGlobePicking(setSelectedId, setClientId);

  useEffect(() => {
    let cancelled = false;
    ArcGisMapServerImageryProvider.fromUrl(
      "https://services.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer",
      { enablePickFeatures: false },
    )
      .then((provider) => {
        if (!cancelled) {
          setImagery(provider);
          setImageryName("ArcGIS World Imagery");
        }
      })
      .catch(() => {
        if (!cancelled) {
          setImagery(
            new OpenStreetMapImageryProvider({
              url: "https://tile.openstreetmap.org/",
            }),
          );
          setImageryName("OSM fallback");
        }
      });
    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const scene = viewerRef.current?.cesiumElement?.scene;
    if (!scene) return;
    if (viewMode === "3d") scene.morphTo3D(0.45);
    else scene.morphTo2D(0.45);
  }, [frame, viewMode]);

  useEffect(() => {
    if (!frame) return;
    const animationFrame = window.requestAnimationFrame(() => {
      const viewer = viewerRef.current?.cesiumElement;
      if (!viewer) return;
      viewer.resolutionScale = Math.min(window.devicePixelRatio || 1, 2);
      viewer.scene.postProcessStages.fxaa.enabled = true;
      viewer.scene.highDynamicRange = true;
      viewer.scene.globe.maximumScreenSpaceError = 1.15;
      viewer.scene.globe.tileCacheSize = 240;
      viewer.scene.fog.enabled = true;
      if (!cameraInitialized.current) {
        viewer.camera.flyTo({
          destination: Cartesian3.fromDegrees(42, 59, 18_000_000),
          duration: 0,
        });
        cameraInitialized.current = true;
      }
    });
    return () => window.cancelAnimationFrame(animationFrame);
  }, [frame]);

  if (error) return <ErrorState message={error} />;
  if (!frame) return <LoadingState label="Формируем демонстрационный кадр…" />;

  return (
    <div className="globe-view">
      {loading && <div className="frame-loading">Обновление кадра…</div>}
      <Viewer
        ref={viewerRef}
        full
        baseLayer={false}
        animation={false}
        timeline={false}
        geocoder={false}
        homeButton={false}
        sceneModePicker={false}
        baseLayerPicker={false}
        navigationHelpButton={false}
        fullscreenButton={false}
        selectionIndicator={false}
        infoBox={false}
      >
        <Globe
          baseColor={Color.fromCssColorString("#1d4f73")}
          showGroundAtmosphere
          maximumScreenSpaceError={1.15}
          tileCacheSize={240}
        />
        {imagery && (
          <ImageryLayer
            imageryProvider={imagery}
            alpha={1}
            brightness={1.08}
            contrast={1.16}
            saturation={1.28}
            gamma={0.92}
          />
        )}
        {layers.orbits && (
          <OrbitLayer orbits={frame.orbits} hiddenNodeIds={hiddenNodes} />
        )}
        {layers.network && (
          <NetworkLayer links={frame.links} positions={positions} />
        )}
        {layers.route && (
          <RouteLayer links={frame.links} positions={positions} />
        )}
        {layers.satellites && (
          <SatellitesLayer
            satellites={frame.satellites}
            route={frame.route}
            selectedId={selectedId}
            showLabels={layers.labels}
            hiddenNodeIds={hiddenNodes}
            onSelect={picking.selectSatellite}
          />
        )}
        {layers.groundSites && (
          <GroundSitesLayer
            sites={frame.groundSites}
            activeClientId={clientId}
            selectedId={selectedId}
            hiddenNodeIds={hiddenNodes}
            onSelect={picking.selectGroundSite}
          />
        )}
      </Viewer>
      <div className="imagery-badge">HD · {imageryName}</div>
      <div className="mock-badge">DEMO · MOCK DATA</div>
    </div>
  );
}
