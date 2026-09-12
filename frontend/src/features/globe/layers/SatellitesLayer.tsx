import { Cartesian2, Color, NearFarScalar } from "cesium";
import { Entity } from "resium";
import type { SatelliteFrame } from "../../../shared/model/types";
import { satellitePosition } from "../cesiumCoordinates";

interface Props {
  satellites: SatelliteFrame[];
  route: string[];
  selectedId: string | null;
  showLabels: boolean;
  hiddenNodeIds: Set<string>;
  onSelect: (id: string) => void;
}

export function SatellitesLayer({
  satellites,
  route,
  selectedId,
  showLabels,
  hiddenNodeIds,
  onSelect,
}: Props) {
  return satellites.map((satellite) => {
    const selected = satellite.id === selectedId;
    const inRoute = route.includes(satellite.id);
    const color = satellite.failed
      ? Color.fromCssColorString("#d85850")
      : inRoute
        ? Color.fromCssColorString("#e27a1d")
        : Color.WHITE;
    const visible =
      !hiddenNodeIds.has(`plane:${satellite.planeId}`) &&
      !hiddenNodeIds.has(`satellite:${satellite.id}`);
    return (
      <Entity
        key={satellite.id}
        id={satellite.id}
        name={satellite.id}
        position={satellitePosition(satellite)}
        show={visible && (satellite.active || satellite.failed)}
        point={{
          pixelSize: selected ? 12 : inRoute ? 9 : 6,
          color,
          outlineColor: selected
            ? Color.fromCssColorString("#e27a1d")
            : Color.fromCssColorString("#101112"),
          outlineWidth: selected ? 3 : 2,
          scaleByDistance: new NearFarScalar(2e6, 1.35, 2.4e7, 0.6),
        }}
        label={{
          text: satellite.failed ? `${satellite.id} ×` : satellite.id,
          show: showLabels && (selected || inRoute || satellite.active),
          fillColor: Color.WHITE,
          outlineColor: Color.BLACK,
          outlineWidth: 3,
          font: "12px Inter, sans-serif",
          pixelOffset: new Cartesian2(0, -16),
          scaleByDistance: new NearFarScalar(2e6, 1.1, 2.2e7, 0.65),
        }}
        onClick={() => onSelect(satellite.id)}
      />
    );
  });
}
