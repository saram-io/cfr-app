export interface User {
  id: number;
  username: string;
  full_name: string;
  email: string;
  role: 'Admin' | 'QA_Compliance' | 'Lab_Engineer' | 'Auditor';
  is_active: boolean;
}

export interface ElectronicSignatureInput {
  username: string;
  password: string;
  meaning: 'Approved' | 'Verified' | 'Reviewed' | 'Authored';
  reason: string;
}

export interface AssetComplianceStatus {
  overall_status: 'COMPLIANT' | 'AT_RISK' | 'NON_COMPLIANT' | 'EXEMPT';
  backup_required: boolean;
  has_active_policy: boolean;
  has_approved_sop: boolean;
  rpo_compliant: boolean;
  restore_drill_compliant: boolean;
  last_backup_at?: string | null;
  last_restore_drill_at?: string | null;
  issues: string[];
}

export interface Asset {
  id: number;
  asset_tag: string;
  name: string;
  category: string;
  vendor: string;
  model: string;
  serial_number: string;
  software_version?: string | null;
  location: string;
  hostname_or_ip: string;
  os_type: string;
  is_gmp: boolean;
  criticality: 'CRITICAL' | 'MAJOR' | 'MINOR';
  system_owner: string;
  qa_owner: string;
  sop_id?: number | null;
  sop_code?: string | null;
  agent_token: string;
  agent_last_seen_at?: string | null;
  notes?: string | null;
  policy_id?: number | null;
  policy_schedule?: string | null;
  repository_name?: string | null;
  compliance: AssetComplianceStatus;
  created_at?: string | null;
}

export interface StorageRepo {
  id: number;
  name: string;
  backend_type: string;
  repo_uri: string;
  env_keys: string[];
  immutable_append_only: boolean;
  is_initialized: boolean;
  status: string;
  last_check_output?: string | null;
  last_checked_at?: string | null;
  notes?: string | null;
  created_at?: string | null;
}

export interface BackupPolicy {
  id: number;
  asset_id: number;
  asset_tag: string;
  asset_name: string;
  is_gmp: boolean;
  criticality: string;
  repository_id: number;
  repository_name: string;
  backend_type: string;
  name: string;
  is_enabled: boolean;
  execution_mode: 'ENDPOINT_AGENT' | 'CENTRAL_GATEWAY';
  schedule_preset: 'HOURLY' | 'EVERY_4_HOURS' | 'DAILY' | 'WEEKLY' | 'CUSTOM';
  schedule_cron: string;
  backup_paths: string[];
  exclude_patterns: string[];
  rpo_hours: number;
  rto_hours: number;
  retention_keep_last: number;
  retention_keep_daily: number;
  retention_keep_weekly: number;
  retention_keep_monthly: number;
  retention_keep_yearly: number;
  vss_enabled: boolean;
  pre_backup_hook?: string | null;
  gateway_share_uri?: string | null;
  force_run_requested: boolean;
  config_version: number;
  last_run_at?: string | null;
  next_run_at?: string | null;
  updated_at?: string | null;
}

export interface SnapshotRecord {
  id: number;
  snapshot_id: string;
  short_id: string;
  asset_id: number;
  asset_tag: string;
  asset_name: string;
  is_gmp: boolean;
  criticality: string;
  repository_id: number;
  repository_name: string;
  hostname: string;
  paths: string[];
  tags: string[];
  created_at: string;
  size_bytes: number;
  file_count: number;
  is_verified: boolean;
}

export interface RestoreDrill {
  id: number;
  asset_id: number;
  asset_tag: string;
  asset_name: string;
  is_gmp: boolean;
  criticality: string;
  repository_id: number;
  snapshot_id: string;
  sop_id?: number | null;
  restore_type: string;
  target_path: string;
  status: 'COMPLETED_PENDING_QA' | 'QA_APPROVED' | 'FAILED';
  started_at: string;
  completed_at?: string | null;
  actual_rto_minutes: number;
  target_rto_minutes: number;
  restored_file_count: number;
  restored_bytes: number;
  checksum_verified: boolean;
  sha256_manifest: Array<{ file: string; size_bytes: number; sha256: string }>;
  checklist_results: Array<{ step: string; passed: boolean }>;
  executed_by: string;
  qa_signed_by?: string | null;
  qa_signed_at?: string | null;
  qa_signature_meaning?: string | null;
  notes?: string | null;
}

export interface SOPDocument {
  id: number;
  sop_code: string;
  title: string;
  version: string;
  status: string;
  target_rpo_hours: number;
  target_rto_hours: number;
  drill_interval_days: number;
  content_markdown: string;
  checklist: string[];
  approved_by?: string | null;
  approved_at?: string | null;
  updated_at?: string | null;
}

export interface EquipmentGuide {
  slug: string;
  filename: string;
  title: string;
  content_markdown: string;
}

export interface AuditLogEntry {
  id: number;
  timestamp: string;
  actor_username: string;
  actor_role: string;
  action: string;
  entity_type: string;
  entity_id: string;
  summary: string;
  old_value?: Record<string, unknown> | null;
  new_value?: Record<string, unknown> | null;
  reason?: string | null;
  signature_meaning?: string | null;
  signature_verified: boolean;
  previous_hash: string;
  record_hash: string;
}
