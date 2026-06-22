from __future__ import annotations

from backend.db.base import Base
from backend.domains.ai.models import AiUsageEvent
from backend.domains.compatibility.models import CompatibilityCheck, CompatibilityCheckItem
from backend.domains.models.models import Model, ModelFile, ModelFilePayload, ModelGeometry, SourceProjectScan, SourceProjectScanFile
from backend.domains.printers.models import NetworkScanResult
from backend.domains.resources.models import BackgroundJob, ResourceSample
from backend.domains.settings.models import ProviderSecret
from backend.domains.site_scanning.models import ModelSiteAdapter, ModelSiteScanResult, ModelSiteScanRun, SiteAuthProfile
from backend.domains.users.models import User, UserSession


def test_foundation_models_are_registered_by_domain():
    table_names = set(Base.metadata.tables)

    assert User.__tablename__ in table_names
    assert UserSession.__tablename__ in table_names
    assert AiUsageEvent.__tablename__ in table_names
    assert CompatibilityCheck.__tablename__ in table_names
    assert CompatibilityCheckItem.__tablename__ in table_names
    assert Model.__tablename__ in table_names
    assert ModelFile.__tablename__ in table_names
    assert ModelFilePayload.__tablename__ in table_names
    assert ModelGeometry.__tablename__ in table_names
    assert SourceProjectScan.__tablename__ in table_names
    assert SourceProjectScanFile.__tablename__ in table_names
    assert ResourceSample.__tablename__ in table_names
    assert BackgroundJob.__tablename__ in table_names
    assert ProviderSecret.__tablename__ in table_names
    assert ModelSiteAdapter.__tablename__ in table_names
    assert ModelSiteScanRun.__tablename__ in table_names
    assert ModelSiteScanResult.__tablename__ in table_names
    assert SiteAuthProfile.__tablename__ in table_names


def test_ai_usage_event_has_estimated_and_final_cost_columns():
    columns = AiUsageEvent.__table__.columns

    assert "estimated_cost_usd" in columns
    assert "final_cost_usd" in columns
    assert "cost_status" in columns
    assert "cost_reconciled_at" in columns
    assert "cost_discrepancy_usd" in columns


def test_provider_secret_stores_encrypted_value_metadata():
    columns = ProviderSecret.__table__.columns

    assert "encrypted_value" in columns
    assert "encryption_key_id" in columns
    assert "secret_fingerprint" in columns
    assert "last_four" in columns


def test_site_scan_run_has_chartable_status_and_timing_columns():
    columns = ModelSiteScanRun.__table__.columns

    assert "status" in columns
    assert "stop_reason" in columns
    assert "queued_url_count" in columns
    assert "scanned_url_count" in columns
    assert "accepted_result_count" in columns
    assert "rejected_url_count" in columns
    assert "duration_ms" in columns
    assert "started_at" in columns
    assert "finished_at" in columns


def test_model_site_adapter_stores_source_site_auth_metadata():
    columns = ModelSiteAdapter.__table__.columns

    assert "base_url" in columns
    assert "login_url" in columns
    assert "auth_capabilities" in columns


def test_site_auth_profile_stores_encrypted_secret_metadata():
    columns = SiteAuthProfile.__table__.columns

    assert "site_key" in columns
    assert "auth_mode" in columns
    assert "encrypted_value" in columns
    assert "encryption_key_id" in columns
    assert "secret_fingerprint" in columns
    assert "last_four" in columns
    assert "account_identifier" in columns
    assert "header_name" in columns


def test_compatibility_checks_are_persistable_with_items():
    check_columns = CompatibilityCheck.__table__.columns
    item_columns = CompatibilityCheckItem.__table__.columns

    assert "scan_result_id" in check_columns
    assert "printer_id" in check_columns
    assert "status" in check_columns
    assert "source_type" in check_columns
    assert "confidence_label" in check_columns
    assert "check_id" in item_columns
    assert "severity" in item_columns


def test_model_upload_geometry_tables_are_persistable():
    model_columns = Model.__table__.columns
    file_columns = ModelFile.__table__.columns
    payload_columns = ModelFilePayload.__table__.columns
    geometry_columns = ModelGeometry.__table__.columns

    assert "source_url" in model_columns
    assert "analysis_job_id" in file_columns
    assert "analysis_warnings" in file_columns
    assert "compressed_bytes" in payload_columns
    assert "source_project_url" in payload_columns
    assert "source_file_url" in payload_columns
    assert "original_sha256" in payload_columns
    assert "triangle_count" in geometry_columns
    assert "volume_mm3" in geometry_columns


def test_source_project_scan_tables_store_file_listing_metadata():
    scan_columns = SourceProjectScan.__table__.columns
    file_columns = SourceProjectScanFile.__table__.columns

    assert "site_key" in scan_columns
    assert "source_project_url" in scan_columns
    assert "external_project_id" in scan_columns
    assert "requested_by_user_id" in scan_columns
    assert "file_id" in file_columns
    assert "source_file_url" in file_columns
    assert "supported_model_file" in file_columns


def test_network_scan_results_store_discovered_capabilities():
    columns = NetworkScanResult.__table__.columns

    assert "capabilities" in columns
    assert "build_volume_x_mm" in columns
    assert "build_volume_y_mm" in columns
    assert "build_volume_z_mm" in columns
