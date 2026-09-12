import { useMemo, useState } from "react";
import { useAppState } from "../../shared/model/store";
import { OutlinerTreeNode, type SceneTreeNode } from "./OutlinerTreeNode";

export function Outliner() {
  const {
    frame,
    scenario,
    selectedId,
    setSelectedId,
    setClientId,
    layers,
    setLayerVisibility,
    hiddenNodeIds,
    toggleNodeVisibility,
  } = useAppState();
  const [query, setQuery] = useState("");
  const hidden = useMemo(() => new Set(hiddenNodeIds), [hiddenNodeIds]);

  const tree = useMemo<SceneTreeNode[]>(() => {
    if (!frame) return [];
    const satellitesVisible = layers.satellites || layers.orbits;
    const linksVisible = layers.network || layers.route;
    const planes = scenario.planes.map((plane) => {
      const satellites = frame.satellites.filter((satellite) => satellite.planeId === plane.id);
      return {
        id: `plane:${plane.id}`,
        label: `${plane.id} · RAAN ${plane.raanDeg}° · φ ${plane.phaseDeg}°`,
        kind: "plane" as const,
        badge: satellites.length,
        visible: !hidden.has(`plane:${plane.id}`),
        onToggleVisibility: () => toggleNodeVisibility(`plane:${plane.id}`),
        children: satellites.map((satellite) => ({
          id: `satellite:${satellite.id}`,
          label: satellite.id,
          kind: "satellite" as const,
          badge: satellite.failed ? "отказ" : satellite.active ? `B${satellite.launchBatch}` : "не запущен",
          selectableId: satellite.id,
          visible: !hidden.has(`satellite:${satellite.id}`),
          onToggleVisibility: () => toggleNodeVisibility(`satellite:${satellite.id}`),
        })),
      };
    });

    const groundNodes = (role: "client" | "gateway") =>
      frame.groundSites
        .filter((site) => site.role === role)
        .map((site) => ({
          id: `site:${site.id}`,
          label: `${site.id} · ${site.name}`,
          kind: site.role === "gateway" ? ("gateway" as const) : ("ground" as const),
          selectableId: site.id,
          visible: !hidden.has(`site:${site.id}`),
          onToggleVisibility: () => toggleNodeVisibility(`site:${site.id}`),
        }));

    const clientNodes = groundNodes("client");
    const gatewayNodes = groundNodes("gateway");

    return [
      {
        id: "collection:satellites",
        label: "Спутники",
        kind: "collection",
        badge: frame.satellites.length,
        visible: satellitesVisible,
        onToggleVisibility: () => {
          const next = !satellitesVisible;
          setLayerVisibility("satellites", next);
          setLayerVisibility("orbits", next);
        },
        children: planes,
      },
      {
        id: "collection:ground-sites",
        label: "Наземные пункты",
        kind: "collection",
        badge: frame.groundSites.length,
        visible: layers.groundSites,
        onToggleVisibility: () => setLayerVisibility("groundSites", !layers.groundSites),
        children: [
          {
            id: "role:client",
            label: "Клиентские пункты",
            kind: "collection",
            badge: clientNodes.length,
            visible: !hidden.has("role:client"),
            onToggleVisibility: () => toggleNodeVisibility("role:client"),
            children: clientNodes,
          },
          {
            id: "role:gateway",
            label: "Шлюзы",
            kind: "collection",
            badge: gatewayNodes.length,
            visible: !hidden.has("role:gateway"),
            onToggleVisibility: () => toggleNodeVisibility("role:gateway"),
            children: gatewayNodes,
          },
        ],
      },
      {
        id: "collection:links",
        label: "Связи",
        kind: "collection",
        badge: frame.links.length,
        visible: linksVisible,
        onToggleVisibility: () => {
          const next = !linksVisible;
          setLayerVisibility("network", next);
          setLayerVisibility("route", next);
        },
        children: [
          {
            id: "layer:network",
            label: "Линии сети",
            kind: "link",
            badge: frame.links.filter((link) => !link.inRoute).length,
            visible: layers.network,
            onToggleVisibility: () => setLayerVisibility("network", !layers.network),
          },
          {
            id: "layer:route",
            label: "Активный маршрут",
            kind: "link",
            badge: frame.route.length ? frame.route.length - 1 : 0,
            visible: layers.route,
            onToggleVisibility: () => setLayerVisibility("route", !layers.route),
          },
        ],
      },
    ];
  }, [frame, hidden, layers, scenario.planes, setLayerVisibility, toggleNodeVisibility]);

  const selectNode = (id: string) => {
    setSelectedId(id);
    if (frame?.groundSites.some((site) => site.id === id && site.role === "client")) {
      setClientId(id);
    }
  };

  const filteredTree = useMemo(() => {
    const normalized = query.trim().toLowerCase();
    if (!normalized) return tree;
    const filter = (node: SceneTreeNode): SceneTreeNode | null => {
      const children = node.children?.map(filter).filter((child): child is SceneTreeNode => Boolean(child));
      if (node.label.toLowerCase().includes(normalized) || children?.length) return { ...node, children };
      return null;
    };
    return tree.map(filter).filter((node): node is SceneTreeNode => Boolean(node));
  }, [query, tree]);

  return (
    <section className="sidebar-section outliner">
      <h2>▤ Сцена</h2>
      <div className="outliner-search">
        <span>⌕</span>
        <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Поиск объектов" aria-label="Поиск объектов" />
      </div>
      <div className="sidebar-scroll">
        {filteredTree.map((node) => (
          <OutlinerTreeNode key={node.id} node={node} selectedId={selectedId} onSelect={selectNode} />
        ))}
      </div>
    </section>
  );
}
