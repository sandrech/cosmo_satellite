import { useEffect, useMemo, useRef } from "react";
import { useAppState } from "../../shared/model/store";
import type { GroundSite, Vector3Km } from "../../shared/model/types";

type GlobeCommand = "zoom-in" | "zoom-out" | "fullscreen";
type Vec3 = { x: number; y: number; z: number };
type HitTarget = { id: string; x: number; y: number; radius: number; client?: boolean };

const EARTH_RADIUS_KM = 6371;

function normalizePosition(position: Vector3Km, earthRadius = 4): Vec3 {
  const scale = earthRadius / EARTH_RADIUS_KM;
  return {
    x: position.xKm * scale,
    y: position.yKm * scale,
    z: position.zKm * scale,
  };
}

function groundPosition(site: GroundSite, radius = 4.03): Vec3 {
  const lat = site.latDeg * Math.PI / 180;
  const lon = site.lonDeg * Math.PI / 180;
  return {
    x: radius * Math.cos(lat) * Math.cos(lon),
    y: radius * Math.sin(lat),
    z: radius * Math.cos(lat) * Math.sin(lon),
  };
}

function spherePoint(latDeg: number, lonDeg: number, radius = 4.02): Vec3 {
  const lat = latDeg * Math.PI / 180;
  const lon = lonDeg * Math.PI / 180;
  return {
    x: radius * Math.cos(lat) * Math.cos(lon),
    y: radius * Math.sin(lat),
    z: radius * Math.cos(lat) * Math.sin(lon),
  };
}

function rotate(point: Vec3, rx: number, ry: number): Vec3 {
  const cy = Math.cos(ry);
  const sy = Math.sin(ry);
  const x1 = point.x * cy + point.z * sy;
  const z1 = -point.x * sy + point.z * cy;

  const cx = Math.cos(rx);
  const sx = Math.sin(rx);
  return {
    x: x1,
    y: point.y * cx - z1 * sx,
    z: point.y * sx + z1 * cx,
  };
}

function project(point: Vec3, width: number, height: number, zoom: number) {
  const base = Math.min(width, height) * 0.105 * zoom;
  const camera = 12;
  const perspective = camera / Math.max(2, camera - point.z);
  return {
    x: width / 2 + point.x * base * perspective,
    y: height / 2 - point.y * base * perspective,
    z: point.z,
    perspective,
  };
}

export function GlobeCanvas3D() {
  const {
    frame,
    layers,
    selectedId,
    setSelectedId,
    setClientId,
    hiddenNodeIds,
  } = useAppState();
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const hostRef = useRef<HTMLDivElement>(null);
  const rotationRef = useRef({ x: -0.12, y: -0.78 });
  const zoomRef = useRef(1);
  const dragRef = useRef({ active: false, moved: false, x: 0, y: 0 });
  const hitsRef = useRef<HitTarget[]>([]);
  const hidden = useMemo(() => new Set(hiddenNodeIds), [hiddenNodeIds]);

  useEffect(() => {
    const canvas = canvasRef.current;
    const host = hostRef.current;
    if (!canvas || !host || !frame) return;

    const ctx = canvas.getContext("2d");
    if (!ctx) return;

    let raf = 0;
    let resizeObserver: ResizeObserver | null = null;
    let dirty = true;

    const requestDraw = () => {
      dirty = true;
      if (!raf) raf = requestAnimationFrame(drawFrame);
    };

    const sizeCanvas = () => {
      const rect = host.getBoundingClientRect();
      const dpr = Math.min(Math.max(window.devicePixelRatio || 1, 1), 3);
      canvas.width = Math.max(1, Math.round(rect.width * dpr));
      canvas.height = Math.max(1, Math.round(rect.height * dpr));
      canvas.style.width = `${rect.width}px`;
      canvas.style.height = `${rect.height}px`;
      ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
      requestDraw();
    };

    const drawPolyline = (
      points: Vec3[],
      width: number,
      height: number,
      color: string,
      lineWidth: number,
      opacity = 1,
      dash: number[] = [],
    ) => {
      if (points.length < 2) return;
      ctx.save();
      ctx.strokeStyle = color;
      ctx.globalAlpha = opacity;
      ctx.lineWidth = lineWidth;
      ctx.setLineDash(dash);
      ctx.beginPath();
      let started = false;
      for (const raw of points) {
        const rotated = rotate(raw, rotationRef.current.x, rotationRef.current.y);
        const p = project(rotated, width, height, zoomRef.current);
        if (!started) {
          ctx.moveTo(p.x, p.y);
          started = true;
        } else {
          ctx.lineTo(p.x, p.y);
        }
      }
      ctx.stroke();
      ctx.restore();
    };

    const drawMesh = (width: number, height: number) => {
      ctx.save();
      ctx.strokeStyle = "rgba(70,70,70,.58)";
      ctx.lineWidth = 0.75;

      const latitudes = Array.from({ length: 11 }, (_, index) => -75 + index * 15);
      const longitudes = Array.from({ length: 24 }, (_, index) => -180 + index * 15);

      const segment = (a: Vec3, b: Vec3) => {
        const ar = rotate(a, rotationRef.current.x, rotationRef.current.y);
        const br = rotate(b, rotationRef.current.x, rotationRef.current.y);
        if ((ar.z + br.z) / 2 < -0.08) return;
        const ap = project(ar, width, height, zoomRef.current);
        const bp = project(br, width, height, zoomRef.current);
        ctx.beginPath();
        ctx.moveTo(ap.x, ap.y);
        ctx.lineTo(bp.x, bp.y);
        ctx.stroke();
      };

      for (let li = 0; li < latitudes.length - 1; li += 1) {
        const latA = latitudes[li];
        const latB = latitudes[li + 1];
        for (let oi = 0; oi < longitudes.length; oi += 1) {
          const lonA = longitudes[oi];
          const lonB = longitudes[(oi + 1) % longitudes.length];
          const a = spherePoint(latA, lonA);
          const b = spherePoint(latA, lonB);
          const c = spherePoint(latB, lonA);
          const d = spherePoint(latB, lonB);
          segment(a, b);
          segment(a, c);
          segment(a, d);
        }
      }

      ctx.restore();
    };

    function drawFrame() {
      raf = 0;
      if (!dirty) return;
      dirty = false;

      const rect = host.getBoundingClientRect();
      const width = rect.width;
      const height = rect.height;
      ctx.clearRect(0, 0, width, height);
      ctx.fillStyle = "#141414";
      ctx.fillRect(0, 0, width, height);

      const center = project({ x: 0, y: 0, z: 0 }, width, height, zoomRef.current);
      const edge = project({ x: 4, y: 0, z: 0 }, width, height, zoomRef.current);
      const radius = Math.abs(edge.x - center.x);

      ctx.save();
      ctx.shadowColor = "rgba(226,122,29,.34)";
      ctx.shadowBlur = 24;
      ctx.beginPath();
      ctx.arc(center.x, center.y, radius * 1.025, 0, Math.PI * 2);
      ctx.strokeStyle = "rgba(226,122,29,.16)";
      ctx.lineWidth = 12;
      ctx.stroke();
      ctx.restore();

      const gradient = ctx.createRadialGradient(
        center.x - radius * 0.25,
        center.y - radius * 0.30,
        radius * 0.10,
        center.x,
        center.y,
        radius,
      );
      gradient.addColorStop(0, "#2a2a2a");
      gradient.addColorStop(0.62, "#1d1d1d");
      gradient.addColorStop(1, "#101010");
      ctx.fillStyle = gradient;
      ctx.beginPath();
      ctx.arc(center.x, center.y, radius, 0, Math.PI * 2);
      ctx.fill();

      ctx.save();
      ctx.beginPath();
      ctx.arc(center.x, center.y, radius, 0, Math.PI * 2);
      ctx.clip();
      drawMesh(width, height);
      ctx.restore();

      if (layers.orbits) {
        for (const orbit of frame.orbits) {
          if (hidden.has(`plane:${orbit.planeId}`)) continue;
          drawPolyline(
            orbit.positions.map((position) => normalizePosition(position)),
            width,
            height,
            "#b9b9b9",
            1,
            0.34,
          );
        }
      }

      const positions = new Map<string, Vec3>();
      frame.satellites.forEach((satellite) => positions.set(satellite.id, normalizePosition(satellite.position)));
      frame.groundSites.forEach((site) => positions.set(site.id, groundPosition(site)));

      if (layers.network) {
        for (const link of frame.links.filter((item) => !item.inRoute)) {
          const source = positions.get(link.sourceId);
          const target = positions.get(link.targetId);
          if (!source || !target) continue;
          drawPolyline([source, target], width, height, "#8e8e8e", 0.8, 0.22, [2, 4]);
        }
      }

      if (layers.route) {
        for (const link of frame.links.filter((item) => item.inRoute)) {
          const source = positions.get(link.sourceId);
          const target = positions.get(link.targetId);
          if (!source || !target) continue;
          drawPolyline([source, target], width, height, "#e27a1d", 1.6, 0.95);
        }
      }

      hitsRef.current = [];

      if (layers.groundSites) {
        for (const site of frame.groundSites) {
          if (hidden.has(`site:${site.id}`)) continue;
          const rotated = rotate(groundPosition(site), rotationRef.current.x, rotationRef.current.y);
          if (rotated.z < -0.35) continue;
          const p = project(rotated, width, height, zoomRef.current);
          const selected = selectedId === site.id;
          ctx.save();
          ctx.translate(p.x, p.y);
          ctx.rotate(Math.PI / 4);
          ctx.fillStyle = site.role === "gateway" ? "#7ed6a5" : "#d7d7d7";
          ctx.strokeStyle = selected ? "#e27a1d" : "#0f0f0f";
          ctx.lineWidth = selected ? 2.5 : 2;
          ctx.fillRect(-4, -4, 8, 8);
          ctx.strokeRect(-4, -4, 8, 8);
          ctx.restore();
          if (layers.labels) {
            ctx.fillStyle = "#e9e9e9";
            ctx.font = "600 10px Inter, system-ui, sans-serif";
            ctx.fillText(site.id, p.x + 9, p.y - 7);
          }
          hitsRef.current.push({ id: site.id, x: p.x, y: p.y, radius: 10, client: site.role === "client" });
        }
      }

      if (layers.satellites) {
        frame.satellites.forEach((satellite, index) => {
          if (hidden.has(`satellite:${satellite.id}`) || hidden.has(`plane:${satellite.planeId}`)) return;
          const rotated = rotate(normalizePosition(satellite.position), rotationRef.current.x, rotationRef.current.y);
          const p = project(rotated, width, height, zoomRef.current);
          const selected = selectedId === satellite.id;
          const inRoute = frame.route.includes(satellite.id);
          const r = selected ? 5.5 : 3.4;

          ctx.save();
          ctx.beginPath();
          ctx.arc(p.x, p.y, r, 0, Math.PI * 2);
          ctx.fillStyle = satellite.failed ? "#a34343" : inRoute ? "#f0f0f0" : "#f6f6f6";
          ctx.fill();
          ctx.lineWidth = selected ? 2.5 : 1.8;
          ctx.strokeStyle = selected ? "#e27a1d" : "#101010";
          ctx.stroke();
          ctx.restore();

          if (layers.labels && (selected || inRoute || index % 10 === 0)) {
            ctx.fillStyle = "#ededed";
            ctx.font = selected ? "700 11px Inter, system-ui, sans-serif" : "600 9px Inter, system-ui, sans-serif";
            ctx.fillText(satellite.id, p.x + 7, p.y - 6);
          }

          hitsRef.current.push({ id: satellite.id, x: p.x, y: p.y, radius: 9 });
        });
      }
    }

    const pointerDown = (event: PointerEvent) => {
      if (event.button !== 0) return;
      dragRef.current = { active: true, moved: false, x: event.clientX, y: event.clientY };
      canvas.setPointerCapture(event.pointerId);
    };

    const pointerMove = (event: PointerEvent) => {
      if (!dragRef.current.active) return;
      const dx = event.clientX - dragRef.current.x;
      const dy = event.clientY - dragRef.current.y;
      if (Math.hypot(dx, dy) > 2) dragRef.current.moved = true;
      rotationRef.current.y += dx * 0.006;
      rotationRef.current.x = Math.max(-1.25, Math.min(1.25, rotationRef.current.x + dy * 0.006));
      dragRef.current.x = event.clientX;
      dragRef.current.y = event.clientY;
      requestDraw();
    };

    const pointerUp = (event: PointerEvent) => {
      const wasMoved = dragRef.current.moved;
      dragRef.current.active = false;
      if (canvas.hasPointerCapture(event.pointerId)) canvas.releasePointerCapture(event.pointerId);
      if (wasMoved) return;

      const rect = canvas.getBoundingClientRect();
      const x = event.clientX - rect.left;
      const y = event.clientY - rect.top;
      const hit = [...hitsRef.current]
        .reverse()
        .find((item) => Math.hypot(item.x - x, item.y - y) <= item.radius);
      if (hit) {
        setSelectedId(hit.id);
        if (hit.client) setClientId(hit.id);
      } else {
        setSelectedId(null);
      }
      requestDraw();
    };

    const wheel = (event: WheelEvent) => {
      event.preventDefault();
      zoomRef.current = Math.max(0.72, Math.min(1.85, zoomRef.current - event.deltaY * 0.0007));
      requestDraw();
    };

    const command = (event: Event) => {
      const detail = (event as CustomEvent<GlobeCommand>).detail;
      if (detail === "zoom-in") zoomRef.current = Math.min(1.85, zoomRef.current * 1.15);
      if (detail === "zoom-out") zoomRef.current = Math.max(0.72, zoomRef.current / 1.15);
      if (detail === "fullscreen") {
        const target = host.closest(".globe-area") as HTMLElement | null;
        if (!document.fullscreenElement) target?.requestFullscreen?.();
        else document.exitFullscreen?.();
      }
      requestDraw();
    };

    canvas.addEventListener("pointerdown", pointerDown);
    canvas.addEventListener("pointermove", pointerMove);
    canvas.addEventListener("pointerup", pointerUp);
    canvas.addEventListener("pointercancel", pointerUp);
    canvas.addEventListener("wheel", wheel, { passive: false });
    window.addEventListener("cosmo:globe-command", command as EventListener);

    resizeObserver = new ResizeObserver(sizeCanvas);
    resizeObserver.observe(host);
    sizeCanvas();

    return () => {
      if (raf) cancelAnimationFrame(raf);
      resizeObserver?.disconnect();
      canvas.removeEventListener("pointerdown", pointerDown);
      canvas.removeEventListener("pointermove", pointerMove);
      canvas.removeEventListener("pointerup", pointerUp);
      canvas.removeEventListener("pointercancel", pointerUp);
      canvas.removeEventListener("wheel", wheel);
      window.removeEventListener("cosmo:globe-command", command as EventListener);
    };
  }, [frame, hidden, layers, selectedId, setClientId, setSelectedId]);

  return (
    <div className="reference-globe3d" ref={hostRef}>
      <canvas ref={canvasRef} aria-label="Трёхмерная модель спутниковой группировки" />
      <div className="globe-scale"><span>5000 км</span></div>
      <div className="globe-coordinates">0.0000° N | 0.0000° E</div>
    </div>
  );
}
