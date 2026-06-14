import { Search } from "lucide-react";
import { Spinner } from "../../../components/Spinner";

type ScanFormProps = {
  isScanning: boolean;
  onSubmit: () => void;
  onUrlChange: (value: string) => void;
  url: string;
};

export function ScanForm({ isScanning, onSubmit, onUrlChange, url }: ScanFormProps) {
  return (
    <form
      className="scan-form"
      onSubmit={(event) => {
        event.preventDefault();
        onSubmit();
      }}
    >
      <label className="field-label">
        <span>Source URL</span>
        <input
          type="url"
          value={url}
          onChange={(event) => onUrlChange(event.target.value)}
          placeholder="https://www.printables.com/"
          required
        />
      </label>
      <button className="primary-action icon-action" type="submit" disabled={isScanning}>
        {isScanning ? <Spinner size={16} /> : <Search size={16} aria-hidden="true" />}
        <span>{isScanning ? "Scanning" : "Scan"}</span>
      </button>
    </form>
  );
}
