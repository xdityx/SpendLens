type ErrorStateProps = {
  title?: string;
  message: string;
  onRetry?: () => void;
};

export function ErrorState({ title = "Unable to load data", message, onRetry }: ErrorStateProps) {
  return (
    <section className="state-panel state-panel-error" role="alert">
      <div>
        <p className="eyebrow">Error</p>
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
      {onRetry ? (
        <button className="secondary-button" type="button" onClick={onRetry}>
          Retry
        </button>
      ) : null}
    </section>
  );
}
