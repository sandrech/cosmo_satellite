export function ErrorState({ message }: { message: string }) {
  return (
    <div className="state-message error">
      <strong>Не удалось получить кадр</strong>
      <span>{message}</span>
    </div>
  );
}
