import { test, expect } from '@playwright/test';

test.describe('CFR-App: Life Science Asset & GxP Restic Backup Management System E2E', () => {
  test('1. Authentication, Sign Out, Quick-Login, and RBAC Role Switcher', async ({ page }) => {
    await page.goto('/');

    // Auto-authenticates default QA_Compliance evaluation account
    await expect(page.getByRole('heading', { name: /Life Science GxP Asset & Restic Backup Compliance Overview/i })).toBeVisible();
    await expect(page.locator('#role-switcher')).toHaveValue('qa_director');

    // Sign out and verify login screen
    await page.getByRole('button', { name: 'Sign out' }).click();
    await expect(page.getByRole('heading', { name: /Life Science Asset & Restic Management Sign In/i })).toBeVisible();

    // Test invalid credentials alert
    await page.locator('input[name="password"]').fill('wrong-password');
    await page.getByRole('button', { name: /Sign In to Regulated Environment/i }).click();
    await expect(page.getByRole('alert')).toContainText(/Invalid username or password/i);

    // Quick-login as Admin
    await page.getByRole('button', { name: /admin — Dr\. Elena Vance/i }).click();
    await expect(page.locator('#role-switcher')).toHaveValue('admin');

    // Switch role to FDA Auditor (Read-Only) and verify write actions are hidden on Equipment tab
    await page.locator('#role-switcher').selectOption('fda_auditor');
    await expect(page.locator('#role-switcher')).toHaveValue('fda_auditor');
    await page.getByRole('button', { name: /Equipment & Criticality/i }).click();
    await expect(page.getByRole('button', { name: /Register New Equipment/i })).toHaveCount(0);

    // Switch back to QA_Compliance
    await page.locator('#role-switcher').selectOption('qa_director');
    await expect(page.getByRole('button', { name: /Register New Equipment/i })).toBeVisible();
  });

  test('2. Compliance Dashboard KPIs, Watchdog Alerts, and Recent Jobs/Drills', async ({ page }) => {
    await page.goto('/');
    await expect(page.getByText('Regulated Compliance Score')).toBeVisible();
    await expect(page.getByText('Lab Equipment Inventory')).toBeVisible();
    await expect(page.getByText('Restic Snapshots & Vaults')).toBeVisible();
    await expect(page.getByText('21 CFR Part 11 Audit Chain')).toBeVisible();

    // Verify seeded Watchdog Alerts are visible (SEQ-GEN-004 and MS-BIO-002)
    await expect(page.getByRole('heading', { name: /Active GxP Backup & Restore Compliance Watchdog Alerts/i })).toBeVisible();
    await expect(page.getByText('SEQ-GEN-004').first()).toBeVisible();
    await expect(page.getByText('HPLC-QC-001').first()).toBeVisible();
  });

  test('3. Equipment Register: Filtering, Restic Setup Script Bundle, and E-Signed Asset Registration', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Equipment & Criticality/i }).click();

    await expect(page.getByRole('heading', { name: /Life Science Equipment Register & Criticality Matrix/i })).toBeVisible();
    await expect(page.getByText('Waters Acquity UPLC H-Class (Empower 3 Node)')).toBeVisible();
    await expect(page.getByText('Sartorius Biostat STR 200L Single-Use Bioreactor')).toBeVisible();

    // Filter by search
    const searchInput = page.locator('input[name="q"]');
    await searchInput.fill('BIO-PLC-003');
    await expect(page.getByText('Sartorius Biostat STR 200L Single-Use Bioreactor')).toBeVisible();
    await expect(page.getByText('Waters Acquity UPLC H-Class (Empower 3 Node)')).toHaveCount(0);
    await searchInput.fill('');

    // Open Restic Setup Script modal for HPLC-QC-001
    const hplcRow = page.locator('tr', { hasText: 'HPLC-QC-001' });
    await hplcRow.getByRole('button', { name: /Restic Setup Script/i }).click();

    const bundleDialog = page.locator('dialog[open]');
    await expect(bundleDialog).toContainText('Restic Deployment Bundle: HPLC-QC-001');
    await expect(bundleDialog).toContainText('--use-fs-snapshot');

    // Switch script tabs inside modal
    await bundleDialog.getByRole('button', { name: /resticprofile \(profiles\.yaml\)/i }).click();
    await expect(bundleDialog).toContainText('hplc-qc-001:');
    await bundleDialog.getByRole('button', { name: /macOS \/ Linux Bash Agent/i }).click();
    await expect(bundleDialog).toContainText('#!/usr/bin/env bash');
    await bundleDialog.getByRole('button', { name: /Agentless Equipment/i }).click();
    await expect(bundleDialog).toContainText('Agentless / Legacy Equipment Gateway Configuration');
    await bundleDialog.getByRole('button', { name: 'Close modal' }).click();

    // Register a new GMP Critical equipment item with 21 CFR Part 11 Electronic Signature
    const uniqueTag = `QPCR-QC-${Date.now().toString().slice(-4)}`;
    await page.getByRole('button', { name: /Register New Equipment/i }).click();
    const createDialog = page.locator('dialog[open]');
    await createDialog.locator('input[name="asset_tag"]').fill(uniqueTag);
    await createDialog.locator('input[name="name"]').fill('QuantStudio 7 Pro Real-Time qPCR System');
    await createDialog.locator('input[name="vendor"]').fill('Thermo Fisher Applied Biosystems');
    await createDialog.locator('input[name="model"]').fill('QuantStudio 7 Pro');
    await createDialog.locator('input[name="serial_number"]').fill(`SN-QS7-${uniqueTag}`);
    await createDialog.locator('input[name="esig_reason"]').fill('IQ/OQ qualification of new qPCR instrument in QC Lab');
    await createDialog.getByRole('button', { name: /Register Equipment/i }).click();

    await expect(page.locator('tr', { hasText: uniqueTag })).toBeVisible();
  });

  test('4. Storage Backends: Verify Restic Local Vault Integrity and Initialize Restic REST Server', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Storage Backends \(S3\/REST\)/i }).click();

    await expect(page.getByRole('heading', { name: /Multi-Backend Restic Storage Repositories/i })).toBeVisible();
    await expect(page.getByText('OnPrem-GMP-Primary-Vault')).toBeVisible();
    await expect(page.getByText('Restic-REST-AppendOnly-Server')).toBeVisible();
    await expect(page.getByText('MinIO-OnPrem-S3-ObjectStore')).toBeVisible();

    // Run `restic check` on OnPrem-GMP-Primary-Vault
    const primaryCard = page
      .locator('div.rounded-xl')
      .filter({ has: page.getByRole('heading', { name: 'OnPrem-GMP-Primary-Vault' }) });
    await primaryCard.getByRole('button', { name: /Verify Integrity \(restic check\)/i }).click();
    await expect(page.getByRole('status')).toContainText(/OnPrem-GMP-Primary-Vault.*Status=HEALTHY/i);

    // Verify RBAC separation of duties: QA_Compliance cannot run `restic init` (requires Admin or Lab_Engineer)
    const restServerCard = page
      .locator('div.rounded-xl')
      .filter({ has: page.getByRole('heading', { name: 'Restic-REST-AppendOnly-Server' }) });
    await restServerCard.getByRole('button', { name: /restic init/i }).click();
    await expect(page.getByRole('status')).toContainText(/Role 'QA_Compliance' is not authorized\. Required: Admin, Lab_Engineer/i);

    // Switch role to Admin and run `restic init` against the live Dockerized Restic REST Server (--append-only)
    await page.locator('#role-switcher').selectOption('admin');
    await expect(page.locator('#role-switcher')).toHaveValue('admin');
    await restServerCard.getByRole('button', { name: /restic init/i }).click();
    await expect(page.getByRole('status')).toContainText(/Restic-REST-AppendOnly-Server.*Status=HEALTHY/i);
  });

  test('5. Backup Policies: Configure Policy for SEQ-GEN-004 and Trigger Live Restic Backup', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Backup Policies & Schedules/i }).click();

    await expect(page.getByRole('heading', { name: /Restic Backup Policies, Schedules & Retention Control/i })).toBeVisible();

    // Configure backup policy for SEQ-GEN-004
    await page.getByRole('button', { name: /Configure Asset Backup Policy/i }).click();
    const policyDialog = page.locator('dialog[open]');
    const seqOption = await policyDialog.locator('select[name="asset_id"] option', { hasText: 'SEQ-GEN-004' }).getAttribute('value');
    if (seqOption) {
      await policyDialog.locator('select[name="asset_id"]').selectOption(seqOption);
    }
    await policyDialog.locator('input[name="backup_paths"]').fill('/app/data/sample_instruments/SEQ-GEN-004');
    await policyDialog.locator('input[name="esig_reason"]').fill('Assigned daily Restic policy for NGS Sequencer per SOP-CSV-008');
    await policyDialog.getByRole('button', { name: /Sign & Save Backup Policy/i }).click();

    const seqRow = page.locator('tr', { hasText: 'SEQ-GEN-004' });
    await expect(seqRow).toBeVisible();

    // Inspect validated resticprofile configuration for HPLC-QC-001
    const hplcPolicyRow = page.locator('tr', { hasText: 'HPLC-QC-001' });
    await hplcPolicyRow.getByRole('button', { name: /resticprofile for HPLC-QC-001/i }).click();
    const rpDialog = page.locator('dialog[open]');
    await expect(rpDialog).toContainText('resticprofile Configuration: hplc-qc-001');
    await expect(rpDialog).toContainText('resticprofile Validated');
    await rpDialog.getByRole('button', { name: /Resolved Output \(resticprofile show\)/i }).click();
    await expect(rpDialog).toContainText('profile hplc-qc-001:');
    await rpDialog.getByRole('button', { name: 'Close modal' }).click();

    // Trigger a live Restic backup right now on HPLC-QC-001
    await hplcPolicyRow.getByRole('button', { name: /Run Backup Now/i }).click();
    await expect(page.getByRole('status')).toContainText(/Restic backup COMPLETED for HPLC-QC-001/i, { timeout: 15000 });
  });

  test('6. Snapshots & Restore Drills: Inspect Files, Run Live Restore Drill, and Apply QA E-Signature', async ({ page }) => {
    await page.goto('/');
    await page.getByRole('button', { name: /Snapshots & Restore Drills/i }).click();

    await expect(page.getByRole('heading', { name: /Restic Snapshots, Recovery Orchestrator & SOP Restore Drills/i })).toBeVisible();

    // Inspect backed-up files inside HPLC-QC-001 snapshot using live `restic ls`
    const hplcSnapRow = page.locator('tr', { hasText: 'HPLC-QC-001' }).first();
    await hplcSnapRow.getByRole('button', { name: /Inspect Files/i }).click();
    const filesDialog = page.locator('dialog[open]');
    await expect(filesDialog).toContainText('Empower3_Batch_20261109_mAb_Purity.arw');
    await expect(filesDialog).toContainText('SystemSuitability_USP_Method.meth');
    await filesDialog.getByRole('button', { name: 'Close modal' }).click();

    // Execute a live Restore Verification Drill on a snapshot
    await hplcSnapRow.getByRole('button', { name: /Restore \/ Drill/i }).click();
    const restoreDialog = page.locator('dialog[open]');
    await restoreDialog.getByRole('button', { name: /Execute Restic Restore Now/i }).click();
    await expect(page.getByRole('status')).toContainText(/Executed Restic Restore/i, { timeout: 15000 });
    await expect(page.getByRole('status')).toContainText(/verified SHA-256 manifest/i);

    // Apply QA 21 CFR Part 11 Electronic Signature to a pending Restore Drill (e.g. MS-BIO-002)
    const pendingSignBtn = page.getByRole('button', { name: /Apply QA E-Signature/i }).first();
    await expect(pendingSignBtn).toBeVisible();
    await pendingSignBtn.click();
    const signDialog = page.locator('dialog[open]');
    await signDialog.getByRole('button', { name: /Sign & Approve Restore Verification Drill/i }).click();
    await expect(page.getByRole('status')).toContainText(/QA Electronic Signature applied to Restore Drill/i);
  });

  test('7. Equipment Guides & SOPs and 21 CFR Part 11 Hash-Chained Audit Trail Verification', async ({ page }) => {
    await page.goto('/');

    // Navigate to Equipment Guides & SOPs
    await page.getByRole('button', { name: /Equipment Guides & SOPs/i }).click();
    await expect(page.getByRole('heading', { name: /Equipment Backup Guidelines & Approved QMS SOPs/i })).toBeVisible();
    await expect(page.getByText('SOP-CSV-008 (v3.0)')).toBeVisible();
    await expect(page.getByText('SOP-IT-014 (v1.2)')).toBeVisible();

    // Switch guide to Agentless & Legacy Equipment
    await page.getByRole('button', { name: /04-agentless-and-legacy-equipment\.md/i }).click();
    await expect(page.locator('article')).toContainText(/Agentless/i);

    // Navigate to 21 CFR Part 11 Audit Trail
    await page.getByRole('button', { name: /21 CFR Part 11 Audit Trail/i }).click();
    await expect(page.getByRole('heading', { name: /21 CFR Part 11 Cryptographic Hash-Chained Audit Trail/i })).toBeVisible();
    await expect(page.getByText(/Cryptographic Chain Verification: PASSED \(100% Intact & Tamper-Free\)/i)).toBeVisible();

    // Re-verify chain integrity via button click
    await page.getByRole('button', { name: /Verify SHA-256 Chain Integrity/i }).click();
    await expect(page.getByText(/Cryptographic Chain Verification: PASSED \(100% Intact & Tamper-Free\)/i)).toBeVisible();
    await expect(page.getByText('SYSTEM_INITIALIZED').first()).toBeVisible();
    await expect(page.getByText('RESTORE_DRILL_QA_SIGNED').first()).toBeVisible();
  });
});
