import { ArcType, Color, type Cartesian3 } from "cesium";
import { Entity } from "resium";
import type { NetworkLink } from "../../../shared/model/types";

interface Props {
  links: NetworkLink[];
  positions: Map<string, Cartesian3>;
}

/**
 * Route highlighting uses the exact same straight physical segment as the
 * network layer. A selected link must never be redrawn as an Earth-following
 * curve: that would visually turn an impossible line-of-sight link into an
 * apparently valid route.
 */
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
          id={`route:${link.id}`}
          name={`${link.sourceId} ↔ ${link.targetId}`}
          polyline={{
            positions: [source, target],
            width: 2.8,
            material: Color.fromCssColorString("#e27a1d"),
            arcType: ArcType.NONE,
          }}
        />
      );
    });
}
