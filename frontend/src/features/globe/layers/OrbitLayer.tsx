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
    .map((orbit) => (
      <Entity
        key={orbit.planeId}
        id={`orbit-${orbit.planeId}`}
        polyline={{
          positions: orbit.positions.map(vectorToCartesian),
          width: 1.05,
          material: Color.fromCssColorString("#c4c4c4").withAlpha(0.38),
          arcType: ArcType.NONE,
        }}
      />
    ));
}
