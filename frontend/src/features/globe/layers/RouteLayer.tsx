import { ArcType, Color, type Cartesian3 } from "cesium";
import { Entity } from "resium";
import type { NetworkLink } from "../../../shared/model/types";

interface Props {
  links: NetworkLink[];
  positions: Map<string, Cartesian3>;
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
            positions: [source, target],
            width: 4,
            material: Color.fromCssColorString("#63b3ff"),
            arcType: ArcType.NONE,
          }}
        />
      );
    });
}
