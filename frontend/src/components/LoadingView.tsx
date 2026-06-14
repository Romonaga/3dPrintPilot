type LoadingViewProps = {
  label: string;
};

export function LoadingView({ label }: LoadingViewProps) {
  return <div className="loading-view">Loading {label}</div>;
}

