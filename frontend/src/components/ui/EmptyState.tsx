import Link from "next/link";

interface EmptyStateProps {
  title: string;
  message: string;
  actionHref?: string;
  actionLabel?: string;
}

export function EmptyState({ title, message, actionHref, actionLabel }: EmptyStateProps) {
  return (
    <section className="state-panel">
      <div>
        <p className="eyebrow">Empty state</p>
        <h2>{title}</h2>
        <p>{message}</p>
      </div>
      {actionHref && actionLabel ? (
        <Link className="secondary-button" href={actionHref}>
          {actionLabel}
        </Link>
      ) : null}
    </section>
  );
}
