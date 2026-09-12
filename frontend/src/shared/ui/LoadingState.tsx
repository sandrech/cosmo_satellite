export function LoadingState({ label = "Загрузка…" }: { label?: string }) {
  return (
    <div className="state-message">
      <span className="spinner" />
      {label}
    </div>
  );
}
