export type PrintWorkflowStep = "select-file" | "select-slicer-artifact" | "select-printer" | "review-print";

export type PrintWorkflowSelection = {
  modelId: number | null;
  modelFileId: number | null;
  slicerArtifactId: number | null;
  printerId: number | null;
};

export type PrintWorkflowState = PrintWorkflowSelection & {
  step: PrintWorkflowStep;
};

export type PrintWorkflowView = {
  step: PrintWorkflowStep;
  routeSegment: string;
  owns: Array<keyof PrintWorkflowSelection>;
};
