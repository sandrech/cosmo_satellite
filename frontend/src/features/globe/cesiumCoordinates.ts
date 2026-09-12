import { Cartesian3 } from "cesium";
import type { GroundSite, SatelliteFrame, SimulationFrame, Vector3Km } from "../../shared/model/types";

export function vectorToCartesian(position: Vector3Km) {
  return new Cartesian3(position.xKm * 1000, position.yKm * 1000, position.zKm * 1000);
}

export function groundToCartesian(site: GroundSite) {
  return vectorToCartesian(site.position);
}

export function createPositionIndex(frame: SimulationFrame) {
  const satellites = new Map(frame.satellites.map((satellite) => [satellite.id, vectorToCartesian(satellite.position)]));
  const ground = new Map(frame.groundSites.map((site) => [site.id, groundToCartesian(site)]));
  return new Map<string, Cartesian3>([...satellites, ...ground]);
}

export function satellitePosition(satellite: SatelliteFrame) {
  return vectorToCartesian(satellite.position);
}
