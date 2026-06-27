from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.domains.models.entities import CompressedModelPayload, GeometryAnalysis
from backend.domains.models.models import Model, ModelFile, ModelFilePayload, ModelGeometry, SlicerArtifact, SourceProjectScan, SourceProjectScanFile
from backend.domains.resources.store import ResourceStore
from backend.domains.site_scanning.runners import SourceSiteProjectFiles


class ModelStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_models(self, limit: int = 50) -> list[Model]:
        statement = (
            select(Model)
            .options(
                selectinload(Model.files).selectinload(ModelFile.geometry),
                selectinload(Model.files).selectinload(ModelFile.payload),
            )
            .order_by(Model.created_at.desc(), Model.id.desc())
            .limit(max(1, min(limit, 100)))
        )
        return list(self._session.scalars(statement).all())

    def get_model(self, model_id: int) -> Model | None:
        statement = (
            select(Model)
            .options(
                selectinload(Model.files).selectinload(ModelFile.geometry),
                selectinload(Model.files).selectinload(ModelFile.payload),
            )
            .where(Model.id == model_id)
        )
        return self._session.scalars(statement).first()

    def get_model_file(self, model_id: int, file_id: int) -> ModelFile | None:
        statement = (
            select(ModelFile)
            .options(selectinload(ModelFile.payload))
            .where(ModelFile.model_id == model_id, ModelFile.id == file_id)
        )
        return self._session.scalars(statement).first()

    def list_slicer_artifacts(self, model_id: int, file_id: int) -> list[SlicerArtifact]:
        statement = (
            select(SlicerArtifact)
            .join(ModelFile, SlicerArtifact.model_file_id == ModelFile.id)
            .where(ModelFile.model_id == model_id, ModelFile.id == file_id)
            .order_by(SlicerArtifact.created_at.desc(), SlicerArtifact.id.desc())
        )
        return list(self._session.scalars(statement).all())

    def get_slicer_artifact(self, model_id: int, file_id: int, artifact_id: int) -> SlicerArtifact | None:
        statement = (
            select(SlicerArtifact)
            .join(ModelFile, SlicerArtifact.model_file_id == ModelFile.id)
            .where(ModelFile.model_id == model_id, ModelFile.id == file_id, SlicerArtifact.id == artifact_id)
        )
        return self._session.scalars(statement).first()

    def save_slicer_artifact(
        self,
        *,
        model_id: int,
        file_id: int,
        printer_id: int | None,
        output_filename: str,
        output_format: str,
        content_type: str | None,
        slicer_name: str,
        slicer_version: str | None,
        profile_name: str | None,
        settings: dict,
        settings_hash: str,
        payload: CompressedModelPayload,
        created_by_user_id: int | None,
    ) -> SlicerArtifact:
        model_file = self.get_model_file(model_id, file_id)
        if model_file is None:
            raise ValueError("Model file not found")
        artifact = SlicerArtifact(
            model_file_id=model_file.id,
            printer_id=printer_id,
            created_by_user_id=created_by_user_id,
            output_filename=output_filename,
            output_format=output_format,
            content_type=content_type,
            slicer_name=slicer_name,
            slicer_version=slicer_version,
            profile_name=profile_name,
            settings=settings,
            settings_hash=settings_hash,
            compression=payload.compression,
            compressed_bytes=payload.compressed_bytes,
            original_size_bytes=payload.original_size_bytes,
            compressed_size_bytes=payload.compressed_size_bytes,
            original_sha256=payload.original_sha256,
            compressed_sha256=payload.compressed_sha256,
        )
        self._session.add(artifact)
        self._session.commit()
        self._session.refresh(artifact)
        return artifact

    def list_source_project_scans(self, limit: int = 20) -> list[SourceProjectScan]:
        statement = (
            select(SourceProjectScan)
            .options(selectinload(SourceProjectScan.files))
            .order_by(SourceProjectScan.created_at.desc(), SourceProjectScan.id.desc())
            .limit(max(1, min(limit, 100)))
        )
        return list(self._session.scalars(statement).all())

    def save_source_project_scan(self, project_files: SourceSiteProjectFiles, *, requested_by_user_id: int | None) -> SourceProjectScan:
        scan = SourceProjectScan(
            site_key=project_files.site_key,
            source_project_url=project_files.source_project_url,
            external_project_id=project_files.external_project_id,
            project_title=project_files.project_title,
            requested_by_user_id=requested_by_user_id,
            raw_metadata={"file_count": len(project_files.files)},
        )
        self._session.add(scan)
        self._session.flush()
        for source_file in project_files.files:
            self._session.add(
                SourceProjectScanFile(
                    scan_id=scan.id,
                    file_id=source_file.file_id,
                    filename=source_file.filename,
                    file_format=source_file.file_format,
                    size_bytes=source_file.size_bytes,
                    source_file_url=source_file.source_file_url,
                    supported_model_file=source_file.supported_model_file,
                    source_created_at=source_file.created_at,
                    notes=source_file.notes,
                    raw_metadata={},
                )
            )
        self._session.commit()
        self._session.refresh(scan)
        return self.get_source_project_scan(scan.id) or scan

    def get_source_project_scan(self, scan_id: int) -> SourceProjectScan | None:
        statement = (
            select(SourceProjectScan)
            .options(selectinload(SourceProjectScan.files))
            .where(SourceProjectScan.id == scan_id)
        )
        return self._session.scalars(statement).first()

    def save_uploaded_model(
        self,
        *,
        title: str,
        source_url: str | None,
        filename: str,
        content_type: str | None,
        size_bytes: int,
        analysis: GeometryAnalysis,
        created_by_user_id: int | None,
    ) -> Model:
        return self._save_analyzed_model(
            title=title,
            source_url=source_url,
            filename=filename,
            content_type=content_type,
            size_bytes=size_bytes,
            analysis=analysis,
            created_by_user_id=created_by_user_id,
            storage_status="metadata_only",
            raw_metadata={"source_url": source_url},
        )

    def save_downloaded_model(
        self,
        *,
        title: str,
        source_project_url: str,
        source_file_url: str,
        filename: str,
        content_type: str | None,
        analysis: GeometryAnalysis,
        payload: CompressedModelPayload,
        created_by_user_id: int | None,
    ) -> Model:
        return self._save_analyzed_model(
            title=title,
            source_url=source_project_url,
            filename=filename,
            content_type=content_type,
            size_bytes=payload.original_size_bytes,
            analysis=analysis,
            created_by_user_id=created_by_user_id,
            storage_status="stored_compressed",
            raw_metadata={
                "source_project_url": source_project_url,
                "source_file_url": source_file_url,
                "compression": payload.compression,
                "original_sha256": payload.original_sha256,
            },
            payload=payload,
            source_project_url=source_project_url,
            source_file_url=source_file_url,
        )

    def _save_analyzed_model(
        self,
        *,
        title: str,
        source_url: str | None,
        filename: str,
        content_type: str | None,
        size_bytes: int,
        analysis: GeometryAnalysis,
        created_by_user_id: int | None,
        storage_status: str,
        raw_metadata: dict,
        payload: CompressedModelPayload | None = None,
        source_project_url: str | None = None,
        source_file_url: str | None = None,
    ) -> Model:
        model = Model(
            title=title,
            source_url=source_url,
            status="analyzed",
            created_by_user_id=created_by_user_id,
        )
        self._session.add(model)
        self._session.flush()
        model_file = ModelFile(
            model_id=model.id,
            filename=filename,
            content_type=content_type,
            file_format=analysis.file_format,
            size_bytes=size_bytes,
            storage_status=storage_status,
            analysis_status="completed",
            analysis_warnings=list(analysis.warnings),
            raw_metadata=raw_metadata,
        )
        self._session.add(model_file)
        self._session.flush()
        if payload is not None:
            if source_project_url is None or source_file_url is None:
                raise ValueError("Downloaded model payloads require source project and file URLs.")
            self._session.add(
                ModelFilePayload(
                    model_file_id=model_file.id,
                    source_project_url=source_project_url,
                    source_file_url=source_file_url,
                    compression=payload.compression,
                    compressed_bytes=payload.compressed_bytes,
                    original_size_bytes=payload.original_size_bytes,
                    compressed_size_bytes=payload.compressed_size_bytes,
                    original_sha256=payload.original_sha256,
                    compressed_sha256=payload.compressed_sha256,
                )
            )
        job = ResourceStore(self._session).enqueue_job(
            "model_analysis",
            {"model_id": model.id, "model_file_id": model_file.id, "mode": "geometry_metadata"},
            priority=50,
        )
        model_file.analysis_job_id = job.id
        self._session.add(
            ModelGeometry(
                model_file_id=model_file.id,
                units=analysis.units,
                size_x_mm=analysis.size_x_mm,
                size_y_mm=analysis.size_y_mm,
                size_z_mm=analysis.size_z_mm,
                min_x_mm=analysis.min_x_mm,
                min_y_mm=analysis.min_y_mm,
                min_z_mm=analysis.min_z_mm,
                max_x_mm=analysis.max_x_mm,
                max_y_mm=analysis.max_y_mm,
                max_z_mm=analysis.max_z_mm,
                volume_mm3=analysis.volume_mm3,
                triangle_count=analysis.triangle_count,
                warnings=list(analysis.warnings),
                raw_summary={
                    "file_format": analysis.file_format,
                    "triangle_count": analysis.triangle_count,
                    "warnings": list(analysis.warnings),
                },
            )
        )
        self._session.commit()
        return self.get_model(model.id) or model
