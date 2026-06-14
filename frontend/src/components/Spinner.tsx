type SpinnerProps = {
  size?: number;
};

export function Spinner({ size = 16 }: SpinnerProps) {
  return <span aria-hidden="true" className="spinner" style={{ width: size, height: size }} />;
}
