import { Cartesian2, Color } from "cesium";
import { Entity } from "resium";
import type { GroundSite } from "../../../shared/model/types";
import { groundToCartesian } from "../cesiumCoordinates";

interface Props {
  sites: GroundSite[];
  activeClientId: string;
  selectedId: string | null;
  hiddenNodeIds: Set<string>;
  onSelect: (site: GroundSite) => void;
}

export function GroundSitesLayer({
  sites,
  activeClientId,
  selectedId,
  hiddenNodeIds,
  onSelect,
}: Props) {
  return sites.map((site) => {
    const isGateway = site.role === "gateway";
    const active = site.id === activeClientId || site.id === selectedId;
    const visible =
      !hiddenNodeIds.has(`role:${site.role}`) &&
      !hiddenNodeIds.has(`site:${site.id}`);
    return (
      <Entity
        key={site.id}
        id={site.id}
        name={site.name}
        position={groundToCartesian(site)}
        show={visible}
        point={{
          pixelSize: active ? 14 : 10,
          color: isGateway
            ? Color.fromCssColorString("#68d391")
            : Color.fromCssColorString("#f4cd64"),
          outlineColor: Color.fromCssColorString("#101214"),
          outlineWidth: 3,
        }}
        label={{
          text: site.id,
          fillColor: Color.WHITE,
          outlineColor: Color.BLACK,
          outlineWidth: 4,
          font: "600 13px Inter, sans-serif",
          pixelOffset: new Cartesian2(0, -20),
        }}
        onClick={() => onSelect(site)}
      />
    );
  });
}
