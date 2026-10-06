interface LoadingStateProps {
  label?: string;
}

export function LoadingState({ label = "Loading…" }: LoadingStateProps) {
  return <div className="loading">{label}</div>;
}
