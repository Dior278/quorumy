import type { ComponentType } from "react";

export type WorkspaceView =
  | "flow"
  | "board"
  | "notes"
  | "transcript"
  | "minutes";

type Item = {
  view: WorkspaceView;
  label: string;
  icon: ComponentType<{ size?: number }>;
};

type Props = {
  active: WorkspaceView;
  items: Item[];
  onSelect: (view: WorkspaceView) => void;
};

export function WorkspaceNavigation(props: Props) {
  return (
    <nav className="view-nav" aria-label="Session views">
      {props.items.map((item) => {
        const Icon = item.icon;
        return (
          <button
            className={props.active === item.view ? "active" : ""}
            onClick={() => props.onSelect(item.view)}
            key={item.view}
            title={item.label}
            aria-pressed={props.active === item.view}
          >
            <Icon size={16} />
            <span>{item.label}</span>
          </button>
        );
      })}
    </nav>
  );
}
