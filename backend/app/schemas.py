from datetime import datetime
from typing import Any, Dict, List, Optional
from pydantic import BaseModel, Field


class ElectronicSignatureInput(BaseModel):
    username: str
    password: str
    meaning: str = Field(default="Approved", description="Approved, Verified, Reviewed, Authored")
    reason: str = Field(min_length=3, description="21 CFR Part 11 mandatory reason for change/approval")


class LoginRequest(BaseModel):
    username: str
    password: str


class UserOut(BaseModel):
    id: int
    username: str
    full_name: str
    email: str
    role: str
    is_active: bool

    model_config = {"from_attributes": True}


class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"
    user: UserOut


class SOPCreate(BaseModel):
    sop_code: str
    title: str
    version: str = "1.0"
    status: str = "APPROVED"
    target_rpo_hours: int = 24
    target_rto_hours: int = 4
    drill_interval_days: int = 90
    content_markdown: str
    checklist: List[str] = []
    esignature: Optional[ElectronicSignatureInput] = None


class SOPOut(BaseModel):
    id: int
    sop_code: str
    title: str
    version: str
    status: str
    target_rpo_hours: int
    target_rto_hours: int
    drill_interval_days: int
    content_markdown: str
    checklist: List[str]
    approved_by: Optional[str] = None
    approved_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class StorageRepoCreate(BaseModel):
    name: str
    backend_type: str
    repo_uri: str
    password: str
    env_vars: Dict[str, str] = {}
    immutable_append_only: bool = False
    initialize_now: bool = True
    notes: Optional[str] = None
    esignature: Optional[ElectronicSignatureInput] = None


class StorageRepoOut(BaseModel):
    id: int
    name: str
    backend_type: str
    repo_uri: str
    env_keys: List[str]
    immutable_append_only: bool
    is_initialized: bool
    status: str
    last_check_output: Optional[str] = None
    last_checked_at: Optional[datetime] = None
    notes: Optional[str] = None
    created_at: Optional[datetime] = None


class AssetCreate(BaseModel):
    asset_tag: str
    name: str
    category: str
    vendor: str
    model: str
    serial_number: str
    software_version: Optional[str] = ""
    location: str
    hostname_or_ip: str
    os_type: str
    is_gmp: bool = True
    criticality: str = "CRITICAL"
    system_owner: str
    qa_owner: str
    sop_id: Optional[int] = None
    notes: Optional[str] = None
    esignature: Optional[ElectronicSignatureInput] = None


class AssetUpdate(BaseModel):
    name: Optional[str] = None
    category: Optional[str] = None
    vendor: Optional[str] = None
    model: Optional[str] = None
    serial_number: Optional[str] = None
    software_version: Optional[str] = None
    location: Optional[str] = None
    hostname_or_ip: Optional[str] = None
    os_type: Optional[str] = None
    is_gmp: Optional[bool] = None
    criticality: Optional[str] = None
    system_owner: Optional[str] = None
    qa_owner: Optional[str] = None
    sop_id: Optional[int] = None
    notes: Optional[str] = None
    esignature: Optional[ElectronicSignatureInput] = None


class AssetComplianceStatus(BaseModel):
    overall_status: str  # COMPLIANT, AT_RISK, NON_COMPLIANT, EXEMPT
    backup_required: bool
    has_active_policy: bool
    has_approved_sop: bool
    rpo_compliant: bool
    restore_drill_compliant: bool
    last_backup_at: Optional[datetime] = None
    last_restore_drill_at: Optional[datetime] = None
    issues: List[str] = []


class AssetOut(BaseModel):
    id: int
    asset_tag: str
    name: str
    category: str
    vendor: str
    model: str
    serial_number: str
    software_version: Optional[str] = None
    location: str
    hostname_or_ip: str
    os_type: str
    is_gmp: bool
    criticality: str
    system_owner: str
    qa_owner: str
    sop_id: Optional[int] = None
    sop_code: Optional[str] = None
    agent_token: str
    agent_last_seen_at: Optional[datetime] = None
    notes: Optional[str] = None
    policy_id: Optional[int] = None
    policy_schedule: Optional[str] = None
    repository_name: Optional[str] = None
    compliance: AssetComplianceStatus
    created_at: Optional[datetime] = None


class BackupPolicyCreateUpdate(BaseModel):
    asset_id: int
    repository_id: int
    name: str
    is_enabled: bool = True
    execution_mode: str = "CENTRAL_GATEWAY"  # ENDPOINT_AGENT or CENTRAL_GATEWAY
    schedule_preset: str = "DAILY"  # HOURLY, EVERY_4_HOURS, DAILY, WEEKLY, CUSTOM
    schedule_cron: str = "0 2 * * *"
    backup_paths: List[str]
    exclude_patterns: List[str] = ["*.tmp", "*.lck"]
    rpo_hours: int = 24
    rto_hours: int = 4
    retention_keep_last: int = 7
    retention_keep_daily: int = 14
    retention_keep_weekly: int = 8
    retention_keep_monthly: int = 12
    retention_keep_yearly: int = 7
    vss_enabled: bool = True
    pre_backup_hook: Optional[str] = None
    gateway_share_uri: Optional[str] = None
    esignature: Optional[ElectronicSignatureInput] = None


class BackupPolicyOut(BaseModel):
    id: int
    asset_id: int
    asset_tag: str
    asset_name: str
    is_gmp: bool
    criticality: str
    repository_id: int
    repository_name: str
    backend_type: str
    name: str
    is_enabled: bool
    execution_mode: str
    schedule_preset: str
    schedule_cron: str
    backup_paths: List[str]
    exclude_patterns: List[str]
    rpo_hours: int
    rto_hours: int
    retention_keep_last: int
    retention_keep_daily: int
    retention_keep_weekly: int
    retention_keep_monthly: int
    retention_keep_yearly: int
    vss_enabled: bool
    pre_backup_hook: Optional[str] = None
    gateway_share_uri: Optional[str] = None
    force_run_requested: bool
    config_version: int
    last_run_at: Optional[datetime] = None
    next_run_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None


class AgentReportInput(BaseModel):
    status: str  # COMPLETED, FAILED
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    snapshot_id: Optional[str] = None
    files_new: int = 0
    files_changed: int = 0
    files_unmodified: int = 0
    bytes_added: int = 0
    total_bytes_processed: int = 0
    log_output: Optional[str] = None
    error_message: Optional[str] = None


class RestoreExecuteRequest(BaseModel):
    asset_id: int
    snapshot_id: str
    restore_type: str = "SOP_DRILL"  # SOP_DRILL, EMERGENCY_RESTORE, QUARANTINE_VERIFY
    target_path: Optional[str] = None
    checklist_results: List[Dict[str, Any]] = []
    notes: Optional[str] = None
    esignature: Optional[ElectronicSignatureInput] = None


class RestoreSignOffRequest(BaseModel):
    notes: Optional[str] = None
    esignature: ElectronicSignatureInput
