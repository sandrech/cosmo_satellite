import {
  ArcType,
  Cartesian3,
  Color,
  Ellipsoid,
  EllipsoidGeodesic,
  Math as CesiumMath,
  type Cartographic,
} from "cesium";
import { Entity } from "resium";
import type { NetworkLink } from "../../../shared/model/types";

interface Props {
  links: NetworkLink[];
  positions: Map<string, Cartesian3>;
}

const EARTH = Ellipsoid.WGS84;
const ROUTE_SAMPLES = 72;
const MIN_ROUTE_CLEARANCE_M = 18_000;
const MAX_ROUTE_BULGE_M = 140_000;

function lerp(a: number, b: number, t: number) {
  return a + (b - a) * t;
}

/**
 * Builds a route that follows the outside of the Earth instead of drawing
 * a straight Cartesian chord through the globe.
 *
 * Cesium positions are first converted to geodetic coordinates. We then
 * interpolate along the WGS84 surface geodesic and separately interpolate
 * altitude. A small smooth lift is added between the endpoints so ground
 * links remain clearly visible and never z-fight with the Earth texture.
 */
function buildSurfaceFollowingRoute(
  source: Cartesian3,
  target: Cartesian3,
): Cartesian3[] {
  const start = EARTH.cartesianToCartographic(source);
  const end = EARTH.cartesianToCartographic(target);

  if (!start || !end) return [source, target];

  const geodesic = new EllipsoidGeodesic(start, end, EARTH);
  const surfaceDistance = geodesic.surfaceDistance;

  if (!Number.isFinite(surfaceDistance) || surfaceDistance <= 0) {
    return [source, target];
  }

  const sampleCount = Math.max(
    24,
    Math.min(
      ROUTE_SAMPLES,
      Math.ceil(surfaceDistance / 250_000),
    ),
  );

  // Long routes get a little more visual clearance, but the curve remains
  // close to the globe instead of becoming a huge parabolic arch.
  const bulge = Math.min(
    MAX_ROUTE_BULGE_M,
    Math.max(MIN_ROUTE_CLEARANCE_M, surfaceDistance * 0.012),
  );

  const points: Cartesian3[] = [];

  for (let i = 0; i <= sampleCount; i += 1) {
    const t = i / sampleCount;
    const point: Cartographic = geodesic.interpolateUsingFraction(t);

    const interpolatedHeight = lerp(start.height, end.height, t);
    const smoothLift = Math.sin(Math.PI * t) * bulge;

    point.height = Math.max(0, interpolatedHeight) + smoothLift;

    points.push(
      Cartesian3.fromRadians(
        CesiumMath.negativePiToPi(point.longitude),
        point.latitude,
        point.height,
        EARTH,
      ),
    );
  }

  // Keep the exact real endpoints so the line visually connects to the
  // selected satellite / ground station without a tiny offset.
  points[0] = source;
  points[points.length - 1] = target;

  return points;
}

export function RouteLayer({ links, positions }: Props) {
  return links
    .filter((link) => link.inRoute)
    .map((link) => {
      const source = positions.get(link.sourceId);
      const target = positions.get(link.targetId);
      if (!source || !target) return null;

      return (
        <Entity
          key={link.id}
          id={link.id}
          name={`${link.sourceId} ↔ ${link.targetId}`}
          polyline={{
            positions: buildSurfaceFollowingRoute(source, target),
            width: 2.8,
            material: Color.fromCssColorString("#e27a1d"),
            // The curve is already sampled explicitly. NONE prevents Cesium
            // from trying to reinterpret our prepared 3D arc a second time.
            arcType: ArcType.NONE,
          }}
        />
      );
    });
}
