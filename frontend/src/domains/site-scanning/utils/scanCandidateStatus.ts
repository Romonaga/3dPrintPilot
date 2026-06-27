type CandidateStatusView = {
  label: string;
  nextStep: string;
  tone: "bad" | "ok" | "warn";
};

export function candidateStatusView(status: string): CandidateStatusView {
  if (status === "needs_file") {
    return {
      label: "Needs model file",
      nextStep: "Import or upload geometry.",
      tone: "warn"
    };
  }
  if (status === "ready" || status === "complete" || status === "completed") {
    return {
      label: statusLabel(status),
      nextStep: "Ready for compatibility.",
      tone: "ok"
    };
  }
  if (status === "rejected" || status === "failed") {
    return {
      label: statusLabel(status),
      nextStep: "Review scan evidence.",
      tone: "bad"
    };
  }
  return {
    label: statusLabel(status),
    nextStep: "Review scan evidence.",
    tone: "warn"
  };
}

function statusLabel(status: string) {
  return status
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}
