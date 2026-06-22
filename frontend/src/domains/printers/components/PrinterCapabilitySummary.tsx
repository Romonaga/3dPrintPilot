import { type Printer, type DiscoveredPrinter } from "../types";

type CapabilitySource = Pick<
  Printer | DiscoveredPrinter,
  "capabilities" | "buildVolumeXmm" | "buildVolumeYmm" | "buildVolumeZmm"
>;

type PrinterCapabilitySummaryProps = {
  ariaLabel?: string;
  className?: string;
  emptyLabel?: string;
  includeBuildVolume?: boolean;
  printer: CapabilitySource;
};

type CapabilityLabelOptions = {
  emptyLabel?: string;
  includeBuildVolume?: boolean;
};

export function PrinterCapabilitySummary({
  ariaLabel = "Printer capabilities",
  className = "",
  emptyLabel,
  includeBuildVolume = false,
  printer
}: PrinterCapabilitySummaryProps) {
  const labels = printerCapabilityLabels(printer, { emptyLabel, includeBuildVolume });

  if (labels.length === 0) {
    return null;
  }

  return (
    <div className={`printer-capability-summary capability-list ${className}`.trim()} aria-label={ariaLabel}>
      {labels.map((label) => (
        <span className="capability-pill" key={label}>
          {label}
        </span>
      ))}
    </div>
  );
}

export function printerCapabilityLabels(
  printer: CapabilitySource,
  { emptyLabel, includeBuildVolume = false }: CapabilityLabelOptions = {}
) {
  const capabilities = printer.capabilities ?? {};
  const labels: string[] = [];
  const buildVolume = includeBuildVolume
    ? formatBuildVolume(printer.buildVolumeXmm, printer.buildVolumeYmm, printer.buildVolumeZmm)
    : null;

  if (buildVolume) {
    labels.push(`Build ${buildVolume}`);
  }

  const toolheadCount = firstPositiveInteger(
    capabilities.toolhead_count,
    capabilities.tool_count,
    capabilities.head_count
  );
  const extruderCount = firstPositiveInteger(capabilities.extruder_count);
  if (toolheadCount !== null) {
    labels.push(`${toolheadCount} ${pluralize("toolhead", toolheadCount)}`);
  } else if (extruderCount !== null) {
    labels.push(`${extruderCount} ${pluralize("extruder", extruderCount)}`);
  }

  const colorCount = firstPositiveInteger(
    capabilities.color_count,
    capabilities.colour_count,
    capabilities.material_slot_count,
    capabilities.ams_slot_count,
    capabilities.filament_slot_count
  );
  if (colorCount !== null) {
    labels.push(`${colorCount} ${pluralize("color", colorCount)}`);
  }

  if (toolheadCount === null && isTruthyCapability(capabilities.multi_head)) {
    labels.push("Multi-head");
  }
  if (colorCount === null && isTruthyCapability(capabilities.multi_color)) {
    labels.push("Multi-color");
  }
  if (colorCount === null && isTruthyCapability(capabilities.color_changer)) {
    labels.push("Color changer");
  }

  const nozzleDiameter = firstPositiveNumber(capabilities.nozzle_diameter_mm);
  if (nozzleDiameter !== null) {
    labels.push(`${formatNumber(nozzleDiameter)} mm nozzle`);
  }

  const maxNozzleTemp = firstPositiveInteger(capabilities.max_nozzle_temp_c);
  if (maxNozzleTemp !== null) {
    labels.push(`${maxNozzleTemp} C nozzle`);
  }

  const maxBedTemp = firstPositiveInteger(capabilities.max_bed_temp_c);
  if (maxBedTemp !== null) {
    labels.push(`${maxBedTemp} C bed`);
  }

  return labels.length > 0 || emptyLabel === undefined ? labels : [emptyLabel];
}

function firstPositiveInteger(...values: unknown[]) {
  for (const value of values) {
    const parsed = typeof value === "number" ? value : typeof value === "string" ? Number(value) : NaN;
    if (Number.isInteger(parsed) && parsed > 0) {
      return parsed;
    }
  }
  return null;
}

function firstPositiveNumber(...values: unknown[]) {
  for (const value of values) {
    const parsed = typeof value === "number" ? value : typeof value === "string" ? Number(value) : NaN;
    if (Number.isFinite(parsed) && parsed > 0) {
      return parsed;
    }
  }
  return null;
}

function isTruthyCapability(value: unknown) {
  if (typeof value === "boolean") {
    return value;
  }
  if (typeof value === "string") {
    return ["true", "yes", "1"].includes(value.trim().toLowerCase());
  }
  return value === 1;
}

function formatBuildVolume(x: number | null, y: number | null, z: number | null) {
  if (!x || !y || !z) {
    return null;
  }
  return `${x} x ${y} x ${z} mm`;
}

function formatNumber(value: number) {
  return Number.isInteger(value) ? String(value) : String(Number(value.toFixed(2)));
}

function pluralize(label: string, count: number) {
  return count === 1 ? label : `${label}s`;
}
