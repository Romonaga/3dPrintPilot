import { describe, expect, it } from "vitest";
import { initialPrintWorkflowState, printWorkflowReducer } from "./printWorkflowState";

describe("printWorkflowReducer", () => {
  it("starts a workflow from a selected model file and clears stale downstream choices", () => {
    const state = printWorkflowReducer(
      {
        step: "review-print",
        modelId: 1,
        modelFileId: 10,
        slicerArtifactId: 100,
        printerId: 200
      },
      { type: "select-model-file", modelId: 2, modelFileId: 20 }
    );

    expect(state).toEqual({
      step: "select-slicer-artifact",
      modelId: 2,
      modelFileId: 20,
      slicerArtifactId: null,
      printerId: null
    });
  });

  it("keeps slicer and printer choices behind a model file selection", () => {
    const withoutFile = printWorkflowReducer(initialPrintWorkflowState, {
      type: "select-slicer-artifact",
      slicerArtifactId: 100
    });

    expect(withoutFile).toEqual(initialPrintWorkflowState);

    const withFile = printWorkflowReducer(
      {
        step: "select-slicer-artifact",
        modelId: 2,
        modelFileId: 20,
        slicerArtifactId: null,
        printerId: null
      },
      { type: "select-slicer-artifact", slicerArtifactId: 100 }
    );

    expect(withFile).toMatchObject({
      step: "select-printer",
      slicerArtifactId: 100,
      printerId: null
    });
  });

  it("clears only downstream state when moving back through the workflow", () => {
    const state = printWorkflowReducer(
      {
        step: "review-print",
        modelId: 2,
        modelFileId: 20,
        slicerArtifactId: 100,
        printerId: 200
      },
      { type: "go-to-step", step: "select-slicer-artifact" }
    );

    expect(state).toEqual({
      step: "select-slicer-artifact",
      modelId: 2,
      modelFileId: 20,
      slicerArtifactId: null,
      printerId: null
    });
  });
});
