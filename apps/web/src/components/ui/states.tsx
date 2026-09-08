import type { ReactNode } from "react";

/**
 * The shared loading, empty and failure states.
 *
 * Every state says what happened in words. Colour and icons are never the only
 * signal, and a failure is never rendered as an empty success.
 */

export function Panel({ children }: { children: ReactNode }) {
  return (
    <div className="rounded-lg border border-emerald-950/15 bg-white/60 p-5">{children}</div>
  );
}

export function LoadingState({ label }: { label: string }) {
  return (
    <Panel>
      <p role="status" aria-live="polite" className="text-sm text-emerald-950/70">
        {label}
      </p>
      <div className="mt-3 h-2 w-40 animate-pulse rounded bg-emerald-950/10" />
    </Panel>
  );
}

export function EmptyState({ title, detail }: { title: string; detail: string }) {
  return (
    <Panel>
      <p className="font-medium">{title}</p>
      <p className="mt-2 text-sm leading-6 text-emerald-950/65">{detail}</p>
    </Panel>
  );
}

export function ErrorState({
  title,
  detail,
  onRetry,
}: {
  title: string;
  detail: string;
  onRetry?: () => void;
}) {
  return (
    <Panel>
      <p role="alert" className="font-medium text-red-900">
        {title}
      </p>
      <p className="mt-2 text-sm leading-6 text-emerald-950/65">{detail}</p>
      {onRetry ? (
        <button
          type="button"
          onClick={onRetry}
          className="mt-4 rounded border border-emerald-950/25 px-3 py-1.5 text-sm hover:bg-emerald-950/5"
        >
          Try again
        </button>
      ) : null}
    </Panel>
  );
}
