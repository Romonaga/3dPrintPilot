from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.domains.models.entities import CompressedModelPayload, GeometryAnalysis
from backend.domains.models.models import Model, ModelFile, ModelFilePayload, ModelGeometry
from backend.domains.resources.store import ResourceStore


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
