import { render, screen } from "@testing-library/react";
import { describe, expect, it } from "vitest";
import { PrinterCapabilitySummary, printerCapabilityLabels } from "./PrinterCapabilitySummary";

describe("PrinterCapabilitySummary", () => {
  it("formats captured multi-head and multi-color capabilities", () => {
    const labels = printerCapabilityLabels(
      {
        capabilities: {
          toolhead_count: 4,
          color_count: 4,
          nozzle_diameter_mm: 0.4,
          max_nozzle_temp_c: 300,
          max_bed_temp_c: 100
        },
        buildVolumeXmm: 320,
        buildVolumeYmm: 320,
        buildVolumeZmm: 320
      },
      { includeBuildVolume: true }
    );

    expect(labels).toEqual([
      "Build 320 x 320 x 320 mm",
      "4 toolheads",
      "4 colors",
      "0.4 mm nozzle",
      "300 C nozzle",
      "100 C bed"
    ]);
  });

  it("renders an explicit unknown state when requested", () => {
    render(
      <PrinterCapabilitySummary
        emptyLabel="Capabilities unknown"
        printer={{ capabilities: {}, buildVolumeXmm: null, buildVolumeYmm: null, buildVolumeZmm: null }}
      />
    );

    expect(screen.getByText("Capabilities unknown")).toBeInTheDocument();
  });

  it("uses boolean multi-head and color changer labels when counts are absent", () => {
    expect(
      printerCapabilityLabels({
        capabilities: { multi_head: true, color_changer: "true" },
        buildVolumeXmm: null,
        buildVolumeYmm: null,
        buildVolumeZmm: null
      })
    ).toEqual(["Multi-head", "Color changer"]);
  });
});
