from __future__ import annotations

import math
import struct
import zipfile
from io import BytesIO
from pathlib import PurePath
from xml.etree import ElementTree

from backend.domains.models.entities import GeometryAnalysis, GeometryParseError

MAX_UPLOAD_BYTES = 50 * 1024 * 1024
MAX_3MF_UNCOMPRESSED_BYTES = 100 * 1024 * 1024
SUPPORTED_EXTENSIONS = {".stl": "stl", ".3mf": "3mf"}
THREE_MF_UNIT_SCALE_TO_MM = {
    None: 1.0,
    "millimeter": 1.0,
    "micron": 0.001,
    "centimeter": 10.0,
    "meter": 1000.0,
    "inch": 25.4,
    "foot": 304.8,
}


def safe_filename(filename: str | None) -> str:
    name = PurePath(filename or "uploaded-model").name.strip()
    return name[:255] or "uploaded-model"


def infer_model_format(filename: str | None, content_type: str | None = None) -> str:
    suffix = PurePath(filename or "").suffix.lower()
    if suffix in SUPPORTED_EXTENSIONS:
        return SUPPORTED_EXTENSIONS[suffix]
    if content_type in {"model/stl", "application/sla"}:
        return "stl"
    if content_type in {"model/3mf", "application/vnd.ms-package.3dmanufacturing-3dmodel+xml"}:
        return "3mf"
    raise GeometryParseError("Unsupported model file type. Upload STL or 3MF.")


def analyze_model_bytes(data: bytes, *, filename: str | None = None, content_type: str | None = None) -> GeometryAnalysis:
    if not data:
        raise GeometryParseError("Uploaded model file is empty.")
    if len(data) > MAX_UPLOAD_BYTES:
        raise GeometryParseError(f"Model file exceeds the {MAX_UPLOAD_BYTES // (1024 * 1024)} MB upload limit.")
    file_format = infer_model_format(filename, content_type)
    if file_format == "stl":
        return _analyze_stl(data)
    if file_format == "3mf":
        return _analyze_3mf(data)
    raise GeometryParseError("Unsupported model file type. Upload STL or 3MF.")


def _analyze_stl(data: bytes) -> GeometryAnalysis:
    binary = _try_parse_binary_stl(data)
    if binary is not None:
        return binary
    return _parse_ascii_stl(data)


def _try_parse_binary_stl(data: bytes) -> GeometryAnalysis | None:
    if len(data) < 84:
        return None
    triangle_count = struct.unpack_from("<I", data, 80)[0]
    expected_length = 84 + triangle_count * 50
    if triangle_count == 0 or expected_length > len(data):
        return None
    warnings: list[str] = []
    if expected_length != len(data):
        warnings.append("Binary STL contains trailing bytes after declared triangles.")
    triangles = []
    offset = 84
    for _ in range(triangle_count):
        vertices = struct.unpack_from("<9f", data, offset + 12)
        triangles.append(
            (
                (vertices[0], vertices[1], vertices[2]),
                (vertices[3], vertices[4], vertices[5]),
                (vertices[6], vertices[7], vertices[8]),
            )
        )
        offset += 50
    return _analysis_from_triangles("stl", "millimeter", triangles, warnings)


def _parse_ascii_stl(data: bytes) -> GeometryAnalysis:
    try:
        text = data.decode("utf-8")
    except UnicodeDecodeError:
        text = data.decode("latin-1", errors="ignore")
    vertices: list[tuple[float, float, float]] = []
    warnings: list[str] = []
    for line in text.splitlines():
        parts = line.strip().split()
        if len(parts) == 4 and parts[0].lower() == "vertex":
            try:
                vertices.append((float(parts[1]), float(parts[2]), float(parts[3])))
            except ValueError:
                warnings.append("Skipped an STL vertex with non-numeric coordinates.")
    if len(vertices) < 3:
        raise GeometryParseError("STL file does not contain any parseable triangles.")
    if len(vertices) % 3 != 0:
        warnings.append("ASCII STL had incomplete vertex groups; trailing vertices were ignored.")
    triangles = [tuple(vertices[index : index + 3]) for index in range(0, len(vertices) - 2, 3)]
    return _analysis_from_triangles("stl", "millimeter", triangles, warnings)


def _analyze_3mf(data: bytes) -> GeometryAnalysis:
    try:
        archive = zipfile.ZipFile(BytesIO(data))
    except zipfile.BadZipFile as exc:
        raise GeometryParseError("3MF file is not a valid ZIP package.") from exc
    uncompressed_total = sum(item.file_size for item in archive.infolist())
    if uncompressed_total > MAX_3MF_UNCOMPRESSED_BYTES:
        raise GeometryParseError("3MF package expands beyond the safe analysis limit.")
    model_name = _find_3mf_model_name(archive)
    if model_name is None:
        raise GeometryParseError("3MF package does not contain a 3D model document.")
    try:
        xml_data = archive.read(model_name)
    except KeyError as exc:
        raise GeometryParseError("3MF model document could not be read.") from exc
    try:
        root = ElementTree.fromstring(xml_data)
    except ElementTree.ParseError as exc:
        raise GeometryParseError("3MF model document is malformed XML.") from exc

    unit = root.attrib.get("unit")
    scale = THREE_MF_UNIT_SCALE_TO_MM.get(unit)
    warnings: list[str] = []
    if scale is None:
        scale = 1.0
        warnings.append(f"Unsupported 3MF unit {unit}; treated coordinates as millimeters.")
    vertices_by_object: dict[str, list[tuple[float, float, float]]] = {}
    triangles = []
    for object_element in _iter_elements(root, "object"):
        object_id = object_element.attrib.get("id")
        mesh = next(_iter_elements(object_element, "mesh"), None)
        if object_id is None or mesh is None:
            continue
        vertices = []
        for vertex in _iter_elements(mesh, "vertex"):
            try:
                vertices.append(
                    (
                        float(vertex.attrib["x"]) * scale,
                        float(vertex.attrib["y"]) * scale,
                        float(vertex.attrib["z"]) * scale,
                    )
                )
            except (KeyError, ValueError):
                warnings.append("Skipped a 3MF vertex with missing or invalid coordinates.")
        vertices_by_object[object_id] = vertices
        for triangle in _iter_elements(mesh, "triangle"):
            try:
                triangles.append(
                    (
                        vertices[int(triangle.attrib["v1"])],
                        vertices[int(triangle.attrib["v2"])],
                        vertices[int(triangle.attrib["v3"])],
                    )
                )
            except (KeyError, ValueError, IndexError):
                warnings.append("Skipped a 3MF triangle with invalid vertex references.")
    if any(True for _ in _iter_elements(root, "components")):
        warnings.append("3MF component transforms are not expanded yet; mesh triangles were analyzed directly.")
    if not vertices_by_object and not triangles:
        raise GeometryParseError("3MF model does not contain parseable mesh geometry.")
    return _analysis_from_triangles("3mf", "millimeter", triangles, warnings)


def _find_3mf_model_name(archive: zipfile.ZipFile) -> str | None:
    if "3D/3dmodel.model" in archive.namelist():
        return "3D/3dmodel.model"
    return next((name for name in archive.namelist() if name.lower().endswith(".model")), None)


def _iter_elements(element: ElementTree.Element, local_name: str):
    for candidate in element.iter():
        if candidate.tag.rsplit("}", 1)[-1] == local_name:
            yield candidate


def _analysis_from_triangles(
    file_format: str,
    units: str,
    triangles: list[tuple[tuple[float, float, float], tuple[float, float, float], tuple[float, float, float]]],
    warnings: list[str],
) -> GeometryAnalysis:
    vertices = [vertex for triangle in triangles for vertex in triangle]
    if not vertices:
        raise GeometryParseError("Model file does not contain any parseable triangles.")
    min_x = min(vertex[0] for vertex in vertices)
    min_y = min(vertex[1] for vertex in vertices)
    min_z = min(vertex[2] for vertex in vertices)
    max_x = max(vertex[0] for vertex in vertices)
    max_y = max(vertex[1] for vertex in vertices)
    max_z = max(vertex[2] for vertex in vertices)
    volume = abs(sum(_signed_tetrahedron_volume(*triangle) for triangle in triangles))
    if not math.isfinite(volume):
        warnings.append("Computed volume was not finite and was discarded.")
        volume = None
    elif volume == 0:
        warnings.append("Model volume is zero; mesh may be open or degenerate.")
    return GeometryAnalysis(
        file_format=file_format,
        units=units,
        size_x_mm=max_x - min_x,
        size_y_mm=max_y - min_y,
        size_z_mm=max_z - min_z,
        min_x_mm=min_x,
        min_y_mm=min_y,
        min_z_mm=min_z,
        max_x_mm=max_x,
        max_y_mm=max_y,
        max_z_mm=max_z,
        volume_mm3=volume,
        triangle_count=len(triangles),
        warnings=tuple(dict.fromkeys(warnings)),
    )


def _signed_tetrahedron_volume(
    a: tuple[float, float, float],
    b: tuple[float, float, float],
    c: tuple[float, float, float],
) -> float:
    return (
        a[0] * (b[1] * c[2] - b[2] * c[1])
        - a[1] * (b[0] * c[2] - b[2] * c[0])
        + a[2] * (b[0] * c[1] - b[1] * c[0])
    ) / 6.0
