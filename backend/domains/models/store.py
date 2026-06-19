from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session, selectinload

from backend.domains.models.entities import GeometryAnalysis
from backend.domains.models.models import Model, ModelFile, ModelGeometry
from backend.domains.resources.store import ResourceStore


class ModelStore:
    def __init__(self, session: Session) -> None:
        self._session = session

    def list_models(self, limit: int = 50) -> list[Model]:
        statement = (
            select(Model)
            .options(selectinload(Model.files).selectinload(ModelFile.geometry))
            .order_by(Model.created_at.desc(), Model.id.desc())
            .limit(max(1, min(limit, 100)))
        )
        return list(self._session.scalars(statement).all())

    def get_model(self, model_id: int) -> Model | None:
        statement = (
            select(Model)
            .options(selectinload(Model.files).selectinload(ModelFile.geometry))
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
            storage_status="metadata_only",
            analysis_status="completed",
            analysis_warnings=list(analysis.warnings),
            raw_metadata={"source_url": source_url},
        )
        self._session.add(model_file)
        self._session.flush()
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
