import type { FrameRequest, SimulationGateway } from "./client";
import type {
  AvailabilitySegment,
  GroundSite,
  NetworkLink,
  OrbitPath,
  SatelliteFrame,
  SimulationFrame,
  Vector3Km,
} from "../model/types";

const EARTH_RADIUS_KM = 6371;
const EARTH_ROTATION_S = 86164.09054;
const PLANES = [
  { id: "P1", raanDeg: 0, phaseDeg: 0 },
  { id: "P2", raanDeg: 60, phaseDeg: 7.5 },
  { id: "P3", raanDeg: 120, phaseDeg: 15 },
];

function groundVector(latDeg: number, lonDeg: number): Vector3Km {
  const lat = radians(latDeg);
  const lon = radians(lonDeg);
  return {
    xKm: EARTH_RADIUS_KM * Math.cos(lat) * Math.cos(lon),
    yKm: EARTH_RADIUS_KM * Math.cos(lat) * Math.sin(lon),
    zKm: EARTH_RADIUS_KM * Math.sin(lat),
  };
}

const GROUND_SITES: GroundSite[] = [
  { id: "C65", name: "Клиент C65", role: "client", latDeg: 65, lonDeg: 33, available: true, position: groundVector(65, 33) },
  { id: "C70", name: "Клиент C70", role: "client", latDeg: 70, lonDeg: 60, available: true, position: groundVector(70, 60) },
  { id: "C72", name: "Клиент C72", role: "client", latDeg: 72, lonDeg: 92, available: true, position: groundVector(72, 92) },
  { id: "GW1", name: "Шлюз MUR", role: "gateway", latDeg: 68.97, lonDeg: 33.08, available: true, position: groundVector(68.97, 33.08) },
];

function radians(value: number) {
  return (value * Math.PI) / 180;
}

function positionAt(
  planeIndex: number,
  slotIndex: number,
  tS: number,
  altitudeKm: number,
  inclinationDeg: number,
): Vector3Km {
  const plane = PLANES[planeIndex];
  const radius = EARTH_RADIUS_KM + altitudeKm;
  const orbitalPeriodS = 5730;
  const u =
    radians(slotIndex * 22.5 + plane.phaseDeg) +
    (2 * Math.PI * tS) / orbitalPeriodS;
  const raan = radians(plane.raanDeg);
  const inclination = radians(inclinationDeg);
  const xInertial =
    radius *
    (Math.cos(raan) * Math.cos(u) -
      Math.sin(raan) * Math.sin(u) * Math.cos(inclination));
  const yInertial =
    radius *
    (Math.sin(raan) * Math.cos(u) +
      Math.cos(raan) * Math.sin(u) * Math.cos(inclination));
  const z = radius * Math.sin(u) * Math.sin(inclination);
  const earthAngle = (2 * Math.PI * tS) / EARTH_ROTATION_S;
  return {
    xKm: xInertial * Math.cos(earthAngle) + yInertial * Math.sin(earthAngle),
    yKm: -xInertial * Math.sin(earthAngle) + yInertial * Math.cos(earthAngle),
    zKm: z,
  };
}

function buildSatellites(request: FrameRequest): SatelliteFrame[] {
  return PLANES.flatMap((plane, planeIndex) =>
    Array.from({ length: 16 }, (_, slotIndex) => {
      const globalIndex = planeIndex * 16 + slotIndex;
      const launchBatch = Math.floor(globalIndex / 16) + 1;
      const id = `S${String(globalIndex + 1).padStart(2, "0")}`;
      const failed =
        request.tS >= 6 * 3600 &&
        ["S06", "S12", "S19", "S25", "S33"].includes(id);
      return {
        id,
        planeId: plane.id,
        active: launchBatch <= request.scenario.launchStage && !failed,
        failed,
        inactiveReason: failed ? "failed" : launchBatch > request.scenario.launchStage ? "not-launched" : null,
        launchBatch,
        position: positionAt(
          planeIndex,
          slotIndex,
          request.tS,
          request.scenario.altitudeKm,
          request.scenario.inclinationDeg,
        ),
      };
    }),
  );
}

function buildOrbits(request: FrameRequest): OrbitPath[] {
  return PLANES.map((plane, planeIndex) => ({
    planeId: plane.id,
    positions: Array.from({ length: 97 }, (_, index) =>
      positionAt(
        planeIndex,
        (index / 96) * 16,
        request.tS,
        request.scenario.altitudeKm,
        request.scenario.inclinationDeg,
      ),
    ),
  }));
}

function buildLinks(
  satellites: SatelliteFrame[],
  clientId: string,
  tS: number,
): { links: NetworkLink[]; route: string[]; reason: string | null } {
  const active = new Map(
    satellites.filter((satellite) => satellite.active).map((satellite) => [
      satellite.id,
      satellite,
    ]),
  );
  const links: NetworkLink[] = [];
  for (let planeIndex = 0; planeIndex < 3; planeIndex += 1) {
    for (let slot = 0; slot < 16; slot += 1) {
      const source = planeIndex * 16 + slot + 1;
      const target = planeIndex * 16 + ((slot + 1) % 16) + 1;
      const sourceId = `S${String(source).padStart(2, "0")}`;
      const targetId = `S${String(target).padStart(2, "0")}`;
      if (active.has(sourceId) && active.has(targetId)) {
        links.push({
          id: `${sourceId}-${targetId}`,
          sourceId,
          targetId,
          kind: "isl",
          distanceKm: 2710,
          inRoute: false,
        });
      }
    }
  }

  for (let slot = 0; slot < 16; slot += 4) {
    for (let plane = 0; plane < 2; plane += 1) {
      const sourceId = `S${String(plane * 16 + slot + 1).padStart(2, "0")}`;
      const targetId = `S${String((plane + 1) * 16 + slot + 1).padStart(2, "0")}`;
      if (active.has(sourceId) && active.has(targetId)) {
        links.push({
          id: `${sourceId}-${targetId}`,
          sourceId,
          targetId,
          kind: "isl",
          distanceKm: 1874,
          inRoute: false,
        });
      }
    }
  }

  const slots: Record<string, number> = { C65: 4, C70: 8, C72: 12 };
  const slot = slots[clientId] ?? 4;
  const routeSatellites = [slot, slot + 16, slot + 32].map(
    (index) => `S${String(index).padStart(2, "0")}`,
  );
  const demoOutage = Math.floor(tS / 120) % 97 >= 91;
  if (demoOutage || routeSatellites.some((id) => !active.has(id))) {
    return {
      links,
      route: [],
      reason: demoOutage
        ? "Межспутниковая сеть разделена на компоненты"
        : "Один из аппаратов маршрута недоступен",
    };
  }

  const route = [clientId, ...routeSatellites, "GW1"];
  for (let index = 0; index < route.length - 1; index += 1) {
    links.push({
      id: `route-${route[index]}-${route[index + 1]}`,
      sourceId: route[index],
      targetId: route[index + 1],
      kind: index === 0 || index === route.length - 2 ? "ground" : "isl",
      distanceKm: index === 0 || index === route.length - 2 ? 920 : 1940,
      inRoute: true,
    });
  }
  return { links, route, reason: null };
}

function segments(offset: number): AvailabilitySegment[] {
  return [
    { from: 0, to: 20400 + offset, state: "path" },
    { from: 20400 + offset, to: 22200 + offset, state: "visible-only" },
    { from: 22200 + offset, to: 50400 + offset, state: "path" },
    { from: 50400 + offset, to: 51600 + offset, state: "no-satellite" },
    { from: 51600 + offset, to: 86400, state: "path" },
  ];
}

class MockSimulationGateway implements SimulationGateway {
  async getFrame(request: FrameRequest): Promise<SimulationFrame> {
    await new Promise((resolve) => window.setTimeout(resolve, 35));
    const satellites = buildSatellites(request);
    const network = buildLinks(satellites, request.clientId, request.tS);
    return {
      source: "mock",
      tS: request.tS,
      horizonS: request.scenario.horizonS,
      stepS: request.scenario.stepS,
      bodyRadiusKm: EARTH_RADIUS_KM,
      satellites,
      groundSites: GROUND_SITES,
      links: network.links,
      route: network.route,
      routeDetails: null,
      routesByStrategy: {},
      orbits: buildOrbits(request),
      metrics: [
        { clientId: "C65", visibility: 99.1, availability: 92.4, maxOutageMinutes: 16, outages: 4 },
        { clientId: "C70", visibility: 99.6, availability: 96.8, maxOutageMinutes: 12, outages: 3 },
        { clientId: "C72", visibility: 99.4, availability: 95.2, maxOutageMinutes: 14, outages: 3 },
      ],
      availability: {
        C65: segments(0),
        C70: segments(1800),
        C72: segments(-1200),
      },
      outageReason: network.reason,
      reachableClients: network.route.length ? 1 : 0,
      clientCount: 3,
      currentConnectivity: null,
      survivesAnySingleSatelliteFailure: null,
    };
  }
}

export const mockSimulationGateway: SimulationGateway =
  new MockSimulationGateway();