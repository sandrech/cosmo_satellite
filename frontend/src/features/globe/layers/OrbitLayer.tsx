import { ArcType, Color } from "cesium";
import { Entity } from "resium";
import type { OrbitPath } from "../../../shared/model/types";
import { vectorToCartesian } from "../cesiumCoordinates";

export function OrbitLayer({
  orbits,
  hiddenNodeIds,
}: {
  orbits: OrbitPath[];
  hiddenNodeIds: Set<string>;
}) {
  return orbits
    .filter((orbit) => !hiddenNodeIds.has(`plane:${orbit.planeId}`))
    .map((orbit, index) => (
    <Entity
      key={orbit.planeId}
      id={`orbit-${orbit.planeId}`}
      polyline={{
        positions: orbit.positions.map(vectorToCartesian),
        width: 1.2,
        material: [
          Color.fromCssColorString("#5aa7ff"),
          Color.fromCssColorString("#90c2ff"),
          Color.fromCssColorString("#d2e6ff"),
        ][index].withAlpha(0.42),
        arcType: ArcType.NONE,
      }}
    />
    ));
}
