import { type PrintWorkflowState, type PrintWorkflowStep } from "../types";

export type PrintWorkflowAction =
  | { type: "select-model-file"; modelId: number; modelFileId: number }
  | { type: "select-slicer-artifact"; slicerArtifactId: number | null }
  | { type: "select-printer"; printerId: number | null }
  | { type: "go-to-step"; step: PrintWorkflowStep }
  | { type: "reset" };

export const initialPrintWorkflowState: PrintWorkflowState = {
  step: "select-file",
  modelId: null,
  modelFileId: null,
  slicerArtifactId: null,
  printerId: null
};

export function printWorkflowReducer(
  state: PrintWorkflowState,
  action: PrintWorkflowAction
): PrintWorkflowState {
  switch (action.type) {
    case "select-model-file":
      return {
        step: "select-slicer-artifact",
        modelId: action.modelId,
        modelFileId: action.modelFileId,
        slicerArtifactId: null,
        printerId: null
      };
    case "select-slicer-artifact":
      return {
        ...state,
        step: state.modelFileId === null ? "select-file" : "select-printer",
        slicerArtifactId: state.modelFileId === null ? null : action.slicerArtifactId,
        printerId: null
      };
    case "select-printer":
      return {
        ...state,
        step: state.modelFileId === null ? "select-file" : "review-print",
        printerId: state.modelFileId === null ? null : action.printerId
      };
    case "go-to-step":
      return stepBackTo(state, action.step);
    case "reset":
      return initialPrintWorkflowState;
  }
}

function stepBackTo(state: PrintWorkflowState, step: PrintWorkflowStep): PrintWorkflowState {
  if (step === "select-file") {
    return initialPrintWorkflowState;
  }
  if (state.modelFileId === null) {
    return initialPrintWorkflowState;
  }
  if (step === "select-slicer-artifact") {
    return {
      ...state,
      step,
      slicerArtifactId: null,
      printerId: null
    };
  }
  if (step === "select-printer") {
    return {
      ...state,
      step,
      printerId: null
    };
  }
  return {
    ...state,
    step
  };
}
