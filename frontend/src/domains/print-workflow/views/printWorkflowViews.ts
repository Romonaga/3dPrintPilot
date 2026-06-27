import { type PrintWorkflowView } from "../types";

export const printWorkflowViews: PrintWorkflowView[] = [
  {
    step: "select-file",
    routeSegment: "file",
    owns: ["modelId", "modelFileId"]
  },
  {
    step: "select-slicer-artifact",
    routeSegment: "slicer-artifact",
    owns: ["slicerArtifactId"]
  },
  {
    step: "select-printer",
    routeSegment: "printer",
    owns: ["printerId"]
  },
  {
    step: "review-print",
    routeSegment: "review",
    owns: []
  }
];
