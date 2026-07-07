interface LoadingStateProps {
  label?: string;
  rows?: number;
}

export function LoadingState({ label = "Loading SpendLens data", rows = 3 }: LoadingStateProps) {
  return (
    <section className="loading-panel" aria-busy="true" aria-live="polite">
      <p>{label}</p>
      <div className="skeleton-stack">
        {Array.from({ length: rows }).map((_, index) => (
          <span className="skeleton-line" key={index} />
        ))}
      </div>
    </section>
  );
}
