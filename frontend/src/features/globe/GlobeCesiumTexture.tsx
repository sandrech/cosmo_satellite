import { useEffect, useMemo, useRef, useState } from "react";
import {
  ArcGisMapServerImageryProvider,
  Cartesian3,
  Color,
  OpenStreetMapImageryProvider,
  SceneMode,
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

type GlobeCommand = "zoom-in" | "zoom-out" | "fullscreen";

const DARK_GRAY_BASE =
  "https://services.arcgisonline.com/ArcGIS/rest/services/Canvas/World_Dark_Gray_Base/MapServer";

/**
 * Detailed earth renderer used when the "Текстура" toggle is enabled.
 *
 * The same imagery provider is used for 2D and 3D so switching view modes does
 * not change the visual language: both remain a dark monochrome earth/map.
 */
export function GlobeCesiumTexture() {
  const {
    frame,
    clientId,
    setClientId,
    selectedId,
    setSelectedId,
    layers,
    viewMode,
    hiddenNodeIds,
  } = useAppState();

  const viewerRef = useRef<any>(null);
  const hostRef = useRef<HTMLDivElement>(null);
  const [imagery, setImagery] = useState<ImageryProvider | null>(null);
  const [fallbackImagery, setFallbackImagery] = useState(false);
  const hidden = useMemo(() => new Set(hiddenNodeIds), [hiddenNodeIds]);
  const positions = useMemo(
    () => (frame ? createPositionIndex(frame) : new Map()),
    [frame],
  );
  const picking = useGlobePicking(setSelectedId, setClientId);

  useEffect(() => {
    let cancelled = false;

    ArcGisMapServerImageryProvider.fromUrl(DARK_GRAY_BASE, {
      enablePickFeatures: false,
    })
      .then((provider) => {
        if (!cancelled) {
          setImagery(provider);
          setFallbackImagery(false);
        }
      })
      .catch(() => {
        if (!cancelled) {
          setImagery(
            new OpenStreetMapImageryProvider({
              url: "https://tile.openstreetmap.org/",
            }),
          );
          setFallbackImagery(true);
        }
      });

    return () => {
      cancelled = true;
    };
  }, []);

  useEffect(() => {
    const viewer = viewerRef.current?.cesiumElement;
    if (!viewer) return;

    const applyQuality = () => {
      viewer.resolutionScale = Math.min(Math.max(window.devicePixelRatio || 1, 1), 2.5);
      viewer.scene.postProcessStages.fxaa.enabled = true;
      viewer.scene.highDynamicRange = true;
      viewer.scene.globe.maximumScreenSpaceError = 1.0;
      viewer.scene.globe.tileCacheSize = 300;
      viewer.scene.globe.showGroundAtmosphere = viewMode === "3d";
      viewer.scene.fog.enabled = viewMode === "3d";

      if (viewMode === "2d") {
        viewer.camera.flyHome(0);
      } else {
        viewer.camera.setView({
          destination: Cartesian3.fromDegrees(25, 30, 18_500_000),
        });
      }
    };

    const raf = window.requestAnimationFrame(applyQuality);
    return () => window.cancelAnimationFrame(raf);
  }, [viewMode, imagery]);

  useEffect(() => {
    const handler = (event: Event) => {
      const command = (event as CustomEvent<GlobeCommand>).detail;
      const viewer = viewerRef.current?.cesiumElement;
      if (!viewer) return;

      if (command === "zoom-in") {
        if (viewMode === "2d") viewer.camera.zoomIn(viewer.camera.positionCartographic.height * 0.22);
        else viewer.camera.zoomIn(viewer.camera.positionCartographic.height * 0.20);
      }

      if (command === "zoom-out") {
        if (viewMode === "2d") viewer.camera.zoomOut(viewer.camera.positionCartographic.height * 0.22);
        else viewer.camera.zoomOut(viewer.camera.positionCartographic.height * 0.20);
      }

      if (command === "fullscreen") {
        const host = hostRef.current?.closest(".globe-area") as HTMLElement | null;
        if (!document.fullscreenElement) host?.requestFullscreen?.().catch(() => {});
        else document.exitFullscreen?.().catch(() => {});
      }
    };

    window.addEventListener("cosmo:globe-command", handler as EventListener);
    return () => window.removeEventListener("cosmo:globe-command", handler as EventListener);
  }, [viewMode]);

  if (!frame) return null;

  return (
    <div ref={hostRef} className="texture-earth-view">
      <Viewer
        key={`earth-${viewMode}`}
        ref={viewerRef}
        full
        sceneMode={viewMode === "2d" ? SceneMode.SCENE2D : SceneMode.SCENE3D}
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
          baseColor={Color.fromCssColorString("#111315")}
          showGroundAtmosphere={viewMode === "3d"}
          maximumScreenSpaceError={1.0}
          tileCacheSize={300}
        />

        {imagery ? (
          <ImageryLayer
            imageryProvider={imagery}
            alpha={1}
            brightness={fallbackImagery ? 0.42 : 0.72}
            contrast={fallbackImagery ? 1.42 : 1.18}
            saturation={0}
            gamma={fallbackImagery ? 0.82 : 0.92}
          />
        ) : null}

        {layers.orbits ? (
          <OrbitLayer orbits={frame.orbits} hiddenNodeIds={hidden} />
        ) : null}
        {layers.network ? (
          <NetworkLayer links={frame.links} positions={positions} />
        ) : null}
        {layers.route ? (
          <RouteLayer links={frame.links} positions={positions} />
        ) : null}
        {layers.satellites ? (
          <SatellitesLayer
            satellites={frame.satellites}
            route={frame.route}
            selectedId={selectedId}
            showLabels={layers.labels}
            hiddenNodeIds={hidden}
            onSelect={picking.selectSatellite}
          />
        ) : null}
        {layers.groundSites ? (
          <GroundSitesLayer
            sites={frame.groundSites}
            activeClientId={clientId}
            selectedId={selectedId}
            hiddenNodeIds={hidden}
            onSelect={picking.selectGroundSite}
          />
        ) : null}
      </Viewer>

      {!imagery ? <div className="earth-texture-loading">Загрузка карты…</div> : null}
    </div>
  );
}
