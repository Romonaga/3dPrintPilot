import { FileDown } from "lucide-react";
import { type SiteScanCandidate } from "../types";

type CandidateImportActionProps = {
  candidate: SiteScanCandidate;
  importSiteKey: string | null;
  onImportCandidate: (candidate: SiteScanCandidate) => void;
};

export function CandidateImportAction({
  candidate,
  importSiteKey,
  onImportCandidate
}: CandidateImportActionProps) {
  if (candidate.status !== "needs_file" || !importSiteKey) {
    return <span className="muted-copy">None</span>;
  }
  return (
    <button className="text-button icon-action scan-candidate-action" type="button" onClick={() => onImportCandidate(candidate)}>
      <FileDown size={15} aria-hidden="true" />
      <span>Import files</span>
    </button>
  );
}
