import { ArcType, Color, type Cartesian3 } from "cesium";
import { Entity } from "resium";
import type { NetworkLink } from "../../../shared/model/types";

interface Props {
  links: NetworkLink[];
  positions: Map<string, Cartesian3>;
}

export function NetworkLayer({ links, positions }: Props) {
  return links
    .filter((link) => !link.inRoute)
    .map((link) => {
      const source = positions.get(link.sourceId);
      const target = positions.get(link.targetId);
      if (!source || !target) return null;
      return (
        <Entity
          key={link.id}
          id={link.id}
          polyline={{
            positions: [source, target],
            width: 1,
            material: Color.WHITE.withAlpha(0.14),
            arcType: ArcType.NONE,
          }}
        />
      );
    });
}
