import { useEffect, useMemo, useRef, useState } from "react";
import { useAppState } from "../../shared/model/store";
import type { GroundSite, OrbitPath, SatelliteFrame, Vector3Km } from "../../shared/model/types";

type GlobeCommand = "zoom-in" | "zoom-out" | "fullscreen";

const MAP_W = 1100;
const MAP_H = 480;

function vectorToLonLat(position: Vector3Km) {
  const lon = Math.atan2(position.yKm, position.xKm) * 180 / Math.PI;
  const lat = Math.atan2(
    position.zKm,
    Math.hypot(position.xKm, position.yKm),
  ) * 180 / Math.PI;
  return { lon, lat };
}

function projectLonLat(lon: number, lat: number) {
  return {
    x: ((lon + 180) / 360) * MAP_W,
    y: ((90 - lat) / 180) * MAP_H,
  };
}

function projectSatellite(satellite: SatelliteFrame) {
  const { lon, lat } = vectorToLonLat(satellite.position);
  return { ...projectLonLat(lon, lat), lon, lat };
}

function projectGround(site: GroundSite) {
  return projectLonLat(site.lonDeg, site.latDeg);
}

function orbitPathD(orbit: OrbitPath) {
  if (!orbit.positions.length) return "";
  let d = "";
  let previousX: number | null = null;
  for (const position of orbit.positions) {
    const { lon, lat } = vectorToLonLat(position);
    const point = projectLonLat(lon, lat);
    const breakPath = previousX !== null && Math.abs(point.x - previousX) > MAP_W * 0.45;
    d += `${!d || breakPath ? "M" : "L"}${point.x.toFixed(1)} ${point.y.toFixed(1)} `;
    previousX = point.x;
  }
  return d.trim();
}

export function GlobeMap2D() {
  const {
    frame,
    layers,
    selectedId,
    setSelectedId,
    setClientId,
    hiddenNodeIds,
  } = useAppState();
  const containerRef = useRef<HTMLDivElement>(null);
  const dragStart = useRef({ x: 0, y: 0 });
  const panStart = useRef({ x: 0, y: 0 });
  const [zoom, setZoom] = useState(1);
  const [pan, setPan] = useState({ x: 0, y: 0 });
  const [dragging, setDragging] = useState(false);

  const hidden = useMemo(() => new Set(hiddenNodeIds), [hiddenNodeIds]);
  const positionIndex = useMemo(() => {
    if (!frame) return new Map<string, { x: number; y: number }>();
    const values: Array<[string, { x: number; y: number }]> = [
      ...frame.satellites.map((satellite) => [satellite.id, projectSatellite(satellite)] as [string, { x: number; y: number }]),
      ...frame.groundSites.map((site) => [site.id, projectGround(site)] as [string, { x: number; y: number }]),
    ];
    return new Map(values);
  }, [frame]);

  useEffect(() => {
    const handler = (event: Event) => {
      const command = (event as CustomEvent<GlobeCommand>).detail;
      if (command === "zoom-in") setZoom((value) => Math.min(3, +(value + 0.25).toFixed(2)));
      if (command === "zoom-out") {
        setZoom((value) => {
          const next = Math.max(1, +(value - 0.25).toFixed(2));
          if (next === 1) setPan({ x: 0, y: 0 });
          return next;
        });
      }
      if (command === "fullscreen") {
        const host = containerRef.current?.closest(".globe-area") as HTMLElement | null;
        if (!document.fullscreenElement) host?.requestFullscreen?.();
        else document.exitFullscreen?.();
      }
    };
    window.addEventListener("cosmo:globe-command", handler as EventListener);
    return () => window.removeEventListener("cosmo:globe-command", handler as EventListener);
  }, []);

  if (!frame) return null;

  const viewW = MAP_W / zoom;
  const viewH = MAP_H / zoom;
  const viewX = (MAP_W - viewW) / 2 + pan.x;
  const viewY = (MAP_H - viewH) / 2 + pan.y;

  const onPointerDown = (event: React.PointerEvent<HTMLDivElement>) => {
    if (event.button !== 0) return;
    const target = event.target as HTMLElement;
    if (target.closest(".map-object")) return;
    setDragging(true);
    dragStart.current = { x: event.clientX, y: event.clientY };
    panStart.current = { ...pan };
    event.currentTarget.setPointerCapture(event.pointerId);
  };

  const onPointerMove = (event: React.PointerEvent<HTMLDivElement>) => {
    if (!dragging) return;
    const rect = containerRef.current?.getBoundingClientRect();
    if (!rect) return;
    const dx = event.clientX - dragStart.current.x;
    const dy = event.clientY - dragStart.current.y;
    setPan({
      x: panStart.current.x - dx * (viewW / rect.width),
      y: panStart.current.y - dy * (viewH / rect.height),
    });
  };

  const onPointerUp = (event: React.PointerEvent<HTMLDivElement>) => {
    setDragging(false);
    if (event.currentTarget.hasPointerCapture(event.pointerId)) {
      event.currentTarget.releasePointerCapture(event.pointerId);
    }
  };

  return (
    <div
      ref={containerRef}
      className={`reference-map2d ${dragging ? "is-panning" : ""}`}
      onPointerDown={onPointerDown}
      onPointerMove={onPointerMove}
      onPointerUp={onPointerUp}
      onPointerCancel={onPointerUp}
      onDoubleClick={() => {
        setZoom(1);
        setPan({ x: 0, y: 0 });
      }}
    >
      <svg viewBox={`${viewX} ${viewY} ${viewW} ${viewH}`} preserveAspectRatio="xMidYMid meet" aria-label="Двумерная карта спутниковой группировки">
        <g className="map-grid">
          {[120, 240, 360].map((y) => <line key={`h${y}`} x1="0" y1={y} x2={MAP_W} y2={y} />)}
          {[220, 440, 660, 880].map((x) => <line key={`v${x}`} x1={x} y1="0" x2={x} y2={MAP_H} />)}
        </g>

        <g className="map-land">
          <path d="M110 52 L145 42 L210 38 L255 45 L298 62 L320 102 L290 128 L275 142 L260 178 L238 198 L218 220 L195 240 L172 268 L152 245 L135 210 L115 170 L98 135 L80 95 Z" />
          <path d="M228 272 L275 285 L318 318 L338 355 L328 395 L298 442 L270 468 L248 425 L240 375 L248 335 Z" />
          <path d="M352 22 L398 15 L432 28 L415 52 L370 58 L348 42 Z" />
          <path d="M430 78 L510 48 L620 42 L740 48 L860 62 L950 85 L985 125 L945 158 L885 172 L825 188 L755 195 L685 205 L632 235 L585 220 L552 185 L495 148 L440 128 L422 98 Z" />
          <path d="M518 202 L588 198 L642 225 L672 268 L662 335 L625 408 L582 435 L548 392 L532 328 L510 262 Z" />
          <path d="M805 310 L878 295 L938 312 L952 355 L918 412 L852 402 L818 368 Z" />
          <path d="M965 145 L978 135 L988 155 L972 168 Z" />
          <path d="M935 235 L962 228 L975 255 L948 268 Z" />
          <path d="M120 462 L280 455 L450 458 L620 452 L800 458 L980 462 L1050 472 L80 475 Z" />
        </g>

        {layers.orbits && (
          <g className="map-orbits">
            {frame.orbits.map((orbit) => (
              <path key={orbit.planeId} d={orbitPathD(orbit)} />
            ))}
          </g>
        )}

        {layers.network && (
          <g className="map-links">
            {frame.links.filter((link) => !link.inRoute).map((link) => {
              const source = positionIndex.get(link.sourceId);
              const target = positionIndex.get(link.targetId);
              if (!source || !target || Math.abs(source.x - target.x) > MAP_W * 0.45) return null;
              return <line key={link.id} x1={source.x} y1={source.y} x2={target.x} y2={target.y} />;
            })}
          </g>
        )}

        {layers.route && (
          <g className="map-route">
            {frame.links.filter((link) => link.inRoute).map((link) => {
              const source = positionIndex.get(link.sourceId);
              const target = positionIndex.get(link.targetId);
              if (!source || !target || Math.abs(source.x - target.x) > MAP_W * 0.45) return null;
              return <line key={link.id} x1={source.x} y1={source.y} x2={target.x} y2={target.y} />;
            })}
          </g>
        )}

        {layers.satellites && (
          <g className="map-satellites">
            {frame.satellites.map((satellite, index) => {
              if (hidden.has(`satellite:${satellite.id}`) || hidden.has(`plane:${satellite.planeId}`)) return null;
              const point = projectSatellite(satellite);
              const selected = satellite.id === selectedId;
              const inRoute = frame.route.includes(satellite.id);
              const showLabel = layers.labels && (selected || inRoute || index % 8 === 0);
              return (
                <g
                  key={satellite.id}
                  className={`map-object map-satellite ${selected ? "is-selected" : ""} ${inRoute ? "is-route" : ""}`}
                  role="button"
                  tabIndex={0}
                  onClick={(event) => {
                    event.stopPropagation();
                    setSelectedId(satellite.id);
                  }}
                >
                  <circle cx={point.x} cy={point.y} r={selected ? 6 : 4} />
                  {showLabel ? <text x={point.x + 8} y={point.y - 6}>{satellite.id}</text> : null}
                </g>
              );
            })}
          </g>
        )}

        {layers.groundSites && (
          <g className="map-ground-sites">
            {frame.groundSites.map((site) => {
              if (hidden.has(`site:${site.id}`)) return null;
              const point = projectGround(site);
              const selected = site.id === selectedId;
              return (
                <g
                  key={site.id}
                  className={`map-object map-ground ${selected ? "is-selected" : ""}`}
                  role="button"
                  tabIndex={0}
                  onClick={(event) => {
                    event.stopPropagation();
                    setSelectedId(site.id);
                    if (site.role === "client") setClientId(site.id);
                  }}
                >
                  <rect x={point.x - 5} y={point.y - 5} width="10" height="10" transform={`rotate(45 ${point.x} ${point.y})`} />
                  {layers.labels ? <text x={point.x + 10} y={point.y + 4}>{site.id}</text> : null}
                </g>
              );
            })}
          </g>
        )}
      </svg>

      <div className="map-scale"><span>5000 км</span></div>
      <div className="map-coordinates">0.0000° N | 0.0000° E {zoom > 1 ? `| ${Math.round(zoom * 100)}%` : ""}</div>
    </div>
  );
}
