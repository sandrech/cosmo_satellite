import { useState, type MouseEvent } from "react";

export type SceneNodeKind =
  | "collection"
  | "plane"
  | "satellite"
  | "ground"
  | "gateway"
  | "link";

export interface SceneTreeNode {
  id: string;
  label: string;
  kind: SceneNodeKind;
  badge?: string | number;
  selectableId?: string;
  visible: boolean;
  onToggleVisibility: () => void;
  children?: SceneTreeNode[];
}

interface Props {
  node: SceneTreeNode;
  level?: number;
  ancestorVisible?: boolean;
  selectedId: string | null;
  onSelect: (id: string) => void;
}

function EyeIcon({ open }: { open: boolean }) {
  return open ? (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="M2.5 12s3.4-6 9.5-6 9.5 6 9.5 6-3.4 6-9.5 6-9.5-6-9.5-6Z" />
      <circle cx="12" cy="12" r="2.8" />
    </svg>
  ) : (
    <svg viewBox="0 0 24 24" aria-hidden="true">
      <path d="m4 4 16 16M9.6 6.3A10.8 10.8 0 0 1 12 6c6.1 0 9.5 6 9.5 6a15 15 0 0 1-2.3 3M6.2 7.4C3.8 9.2 2.5 12 2.5 12s3.4 6 9.5 6c1 0 2-.2 2.8-.4" />
    </svg>
  );
}

function NodeIcon({ kind }: { kind: SceneNodeKind }) {
  const symbols: Record<SceneNodeKind, string> = {
    collection: "▣",
    plane: "◇",
    satellite: "⌾",
    ground: "⌂",
    gateway: "◆",
    link: "⌁",
  };
  return <span className={`tree-kind tree-kind-${kind}`}>{symbols[kind]}</span>;
}

export function OutlinerTreeNode({
  node,
  level = 0,
  ancestorVisible = true,
  selectedId,
  onSelect,
}: Props) {
  const [expanded, setExpanded] = useState(true);
  const hasChildren = Boolean(node.children?.length);
  const effectiveVisible = ancestorVisible && node.visible;
  const selected = node.selectableId === selectedId;

  function toggleEye(event: MouseEvent<HTMLButtonElement>) {
    event.stopPropagation();
    node.onToggleVisibility();
  }

  return (
    <div className={`tree-node ${effectiveVisible ? "" : "tree-node-hidden"}`}>
      <div
        className={`tree-row ${selected ? "selected" : ""}`}
        style={{ paddingLeft: 8 + level * 17 }}
        onClick={() => node.selectableId && onSelect(node.selectableId)}
      >
        <button
          className={`tree-expander ${hasChildren ? "" : "placeholder"}`}
          onClick={(event) => {
            event.stopPropagation();
            if (hasChildren) setExpanded((value) => !value);
          }}
          aria-label={expanded ? "Свернуть" : "Развернуть"}
        >
          {hasChildren ? (expanded ? "⌄" : "›") : "·"}
        </button>
        <NodeIcon kind={node.kind} />
        <span className="tree-label">{node.label}</span>
        {node.badge !== undefined && <small className="tree-badge">{node.badge}</small>}
        <button
          className="tree-eye"
          onClick={toggleEye}
          aria-label={node.visible ? "Скрыть" : "Показать"}
          title={node.visible ? "Скрыть" : "Показать"}
        >
          <EyeIcon open={node.visible} />
        </button>
      </div>
      {hasChildren && expanded && (
        <div className="tree-children">
          {node.children!.map((child) => (
            <OutlinerTreeNode
              key={child.id}
              node={child}
              level={level + 1}
              ancestorVisible={effectiveVisible}
              selectedId={selectedId}
              onSelect={onSelect}
            />
          ))}
        </div>
      )}
    </div>
  );
}
