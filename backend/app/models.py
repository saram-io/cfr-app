from datetime import datetime, timezone
from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, String, Text
from sqlalchemy.orm import relationship
from .database import Base


def utcnow():
    return datetime.now(timezone.utc)


class User(Base):
    __tablename__ = "users"

    id = Column(Integer, primary_key=True, index=True)
    username = Column(String(64), unique=True, nullable=False, index=True)
    full_name = Column(String(128), nullable=False)
    email = Column(String(128), nullable=False)
    role = Column(String(32), nullable=False, default="Lab_Engineer")  # Admin, QA_Compliance, Lab_Engineer, Auditor
    password_hash = Column(String(256), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)


class SOPDocument(Base):
    __tablename__ = "sop_documents"

    id = Column(Integer, primary_key=True, index=True)
    sop_code = Column(String(64), unique=True, nullable=False, index=True)
    title = Column(String(256), nullable=False)
    version = Column(String(32), nullable=False, default="1.0")
    status = Column(String(32), nullable=False, default="APPROVED")  # DRAFT, APPROVED, SUPERSEDED
    target_rpo_hours = Column(Integer, nullable=False, default=24)
    target_rto_hours = Column(Integer, nullable=False, default=4)
    drill_interval_days = Column(Integer, nullable=False, default=90)
    content_markdown = Column(Text, nullable=False)
    checklist_json = Column(Text, nullable=False, default="[]")
    approved_by = Column(String(128), nullable=True)
    approved_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    assets = relationship("Asset", back_populates="sop")


class StorageRepository(Base):
    __tablename__ = "storage_repositories"

    id = Column(Integer, primary_key=True, index=True)
    name = Column(String(128), unique=True, nullable=False)
    backend_type = Column(String(32), nullable=False)
    # LOCAL_NAS, RESTIC_REST, S3_COMPATIBLE, MINIO, AZURE_BLOB, GCS, BACKBLAZE_B2, SFTP
    repo_uri = Column(String(512), nullable=False)
    encrypted_password = Column(Text, nullable=False)
    encrypted_env_json = Column(Text, nullable=False, default="")
    immutable_append_only = Column(Boolean, default=False)
    is_initialized = Column(Boolean, default=False)
    status = Column(String(32), default="UNINITIALIZED")  # HEALTHY, UNINITIALIZED, ERROR
    last_check_output = Column(Text, nullable=True)
    last_checked_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)

    policies = relationship("BackupPolicy", back_populates="repository")


class Asset(Base):
    __tablename__ = "assets"

    id = Column(Integer, primary_key=True, index=True)
    asset_tag = Column(String(64), unique=True, nullable=False, index=True)
    name = Column(String(128), nullable=False)
    category = Column(String(64), nullable=False)
    vendor = Column(String(128), nullable=False)
    model = Column(String(128), nullable=False)
    serial_number = Column(String(128), nullable=False)
    software_version = Column(String(64), nullable=True)
    location = Column(String(128), nullable=False)
    hostname_or_ip = Column(String(128), nullable=False)
    os_type = Column(String(32), nullable=False)
    # WINDOWS, MACOS, LINUX, AGENTLESS_SMB, AGENTLESS_SFTP, AGENTLESS_LANDING_ZONE, AIRGAPPED_USB
    is_gmp = Column(Boolean, nullable=False, default=True)
    criticality = Column(String(32), nullable=False, default="CRITICAL")  # CRITICAL, MAJOR, MINOR
    system_owner = Column(String(128), nullable=False)
    qa_owner = Column(String(128), nullable=False)
    sop_id = Column(Integer, ForeignKey("sop_documents.id"), nullable=True)
    agent_token = Column(String(128), unique=True, nullable=False)
    agent_last_seen_at = Column(DateTime(timezone=True), nullable=True)
    notes = Column(Text, nullable=True)
    created_at = Column(DateTime(timezone=True), default=utcnow)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    sop = relationship("SOPDocument", back_populates="assets")
    policy = relationship("BackupPolicy", back_populates="asset", uselist=False, cascade="all, delete-orphan")
    jobs = relationship("BackupJob", back_populates="asset", cascade="all, delete-orphan")
    snapshots = relationship("SnapshotRecord", back_populates="asset", cascade="all, delete-orphan")
    restore_drills = relationship("RestoreDrill", back_populates="asset", cascade="all, delete-orphan")


class BackupPolicy(Base):
    __tablename__ = "backup_policies"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), unique=True, nullable=False)
    repository_id = Column(Integer, ForeignKey("storage_repositories.id"), nullable=False)
    name = Column(String(128), nullable=False)
    is_enabled = Column(Boolean, default=True)
    execution_mode = Column(String(32), nullable=False, default="CENTRAL_GATEWAY")
    # ENDPOINT_AGENT or CENTRAL_GATEWAY
    schedule_preset = Column(String(32), nullable=False, default="DAILY")
    # HOURLY, EVERY_4_HOURS, DAILY, WEEKLY, CUSTOM
    schedule_cron = Column(String(64), nullable=False, default="0 2 * * *")
    backup_paths_json = Column(Text, nullable=False, default='["/app/data/sample_instruments"]')
    exclude_patterns_json = Column(Text, nullable=False, default='["*.tmp", "*.lck"]')
    rpo_hours = Column(Integer, nullable=False, default=24)
    rto_hours = Column(Integer, nullable=False, default=4)
    retention_keep_last = Column(Integer, nullable=False, default=7)
    retention_keep_daily = Column(Integer, nullable=False, default=14)
    retention_keep_weekly = Column(Integer, nullable=False, default=8)
    retention_keep_monthly = Column(Integer, nullable=False, default=12)
    retention_keep_yearly = Column(Integer, nullable=False, default=7)
    vss_enabled = Column(Boolean, default=True)
    pre_backup_hook = Column(String(512), nullable=True)
    gateway_share_uri = Column(String(512), nullable=True)
    force_run_requested = Column(Boolean, default=False)
    config_version = Column(Integer, default=1)
    last_run_at = Column(DateTime(timezone=True), nullable=True)
    next_run_at = Column(DateTime(timezone=True), nullable=True)
    updated_at = Column(DateTime(timezone=True), default=utcnow, onupdate=utcnow)

    asset = relationship("Asset", back_populates="policy")
    repository = relationship("StorageRepository", back_populates="policies")


class BackupJob(Base):
    __tablename__ = "backup_jobs"

    id = Column(Integer, primary_key=True, index=True)
    policy_id = Column(Integer, ForeignKey("backup_policies.id"), nullable=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    repository_id = Column(Integer, ForeignKey("storage_repositories.id"), nullable=False)
    triggered_by = Column(String(64), nullable=False, default="SCHEDULE")
    execution_mode = Column(String(32), nullable=False, default="CENTRAL_GATEWAY")
    status = Column(String(32), nullable=False, default="RUNNING")  # RUNNING, COMPLETED, FAILED
    started_at = Column(DateTime(timezone=True), default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    duration_seconds = Column(Float, default=0.0)
    snapshot_id = Column(String(128), nullable=True)
    files_new = Column(Integer, default=0)
    files_changed = Column(Integer, default=0)
    files_unmodified = Column(Integer, default=0)
    bytes_added = Column(Integer, default=0)
    total_bytes_processed = Column(Integer, default=0)
    log_output = Column(Text, nullable=True)
    error_message = Column(Text, nullable=True)

    asset = relationship("Asset", back_populates="jobs")


class SnapshotRecord(Base):
    __tablename__ = "snapshot_records"

    id = Column(Integer, primary_key=True, index=True)
    snapshot_id = Column(String(128), unique=True, nullable=False, index=True)
    short_id = Column(String(32), nullable=False)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    repository_id = Column(Integer, ForeignKey("storage_repositories.id"), nullable=False)
    job_id = Column(Integer, ForeignKey("backup_jobs.id"), nullable=True)
    hostname = Column(String(128), nullable=False)
    paths_json = Column(Text, nullable=False, default="[]")
    tags_json = Column(Text, nullable=False, default="[]")
    created_at = Column(DateTime(timezone=True), default=utcnow)
    size_bytes = Column(Integer, default=0)
    file_count = Column(Integer, default=0)
    is_verified = Column(Boolean, default=False)

    asset = relationship("Asset", back_populates="snapshots")


class RestoreDrill(Base):
    __tablename__ = "restore_drills"

    id = Column(Integer, primary_key=True, index=True)
    asset_id = Column(Integer, ForeignKey("assets.id"), nullable=False)
    repository_id = Column(Integer, ForeignKey("storage_repositories.id"), nullable=False)
    snapshot_id = Column(String(128), nullable=False)
    sop_id = Column(Integer, ForeignKey("sop_documents.id"), nullable=True)
    restore_type = Column(String(32), nullable=False, default="SOP_DRILL")
    # SOP_DRILL, EMERGENCY_RESTORE, QUARANTINE_VERIFY
    target_path = Column(String(512), nullable=False)
    status = Column(String(32), nullable=False, default="COMPLETED_PENDING_QA")
    # COMPLETED_PENDING_QA, QA_APPROVED, FAILED
    started_at = Column(DateTime(timezone=True), default=utcnow)
    completed_at = Column(DateTime(timezone=True), nullable=True)
    actual_rto_minutes = Column(Float, default=0.0)
    target_rto_minutes = Column(Float, default=240.0)
    restored_file_count = Column(Integer, default=0)
    restored_bytes = Column(Integer, default=0)
    checksum_verified = Column(Boolean, default=True)
    sha256_manifest_json = Column(Text, nullable=False, default="[]")
    checklist_results_json = Column(Text, nullable=False, default="[]")
    executed_by = Column(String(128), nullable=False)
    qa_signed_by = Column(String(128), nullable=True)
    qa_signed_at = Column(DateTime(timezone=True), nullable=True)
    qa_signature_meaning = Column(String(64), nullable=True)
    notes = Column(Text, nullable=True)

    asset = relationship("Asset", back_populates="restore_drills")


class AuditLog(Base):
    __tablename__ = "audit_logs"

    id = Column(Integer, primary_key=True, index=True)
    timestamp = Column(DateTime(timezone=True), default=utcnow, nullable=False)
    actor_username = Column(String(64), nullable=False)
    actor_role = Column(String(32), nullable=False)
    action = Column(String(64), nullable=False)
    entity_type = Column(String(64), nullable=False)
    entity_id = Column(String(64), nullable=False)
    summary = Column(String(512), nullable=False)
    old_value_json = Column(Text, nullable=True)
    new_value_json = Column(Text, nullable=True)
    reason = Column(Text, nullable=True)
    signature_meaning = Column(String(64), nullable=True)
    signature_verified = Column(Boolean, default=False)
    previous_hash = Column(String(64), nullable=False)
    record_hash = Column(String(64), nullable=False, index=True)
