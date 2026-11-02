/**
 * Linux Infrastructure Drift Detection & Auto Repair System
 * Frontend Client Application
 */

const App = (() => {
  // Global State
  const state = {
    currentTab: 'overview',
    dashboard: null,
    configuration: null,
    drift: null,
    backups: [],
    reports: [],
    logs: [],
    pendingRestoreFile: null,
    isScanning: false,
    isRepairing: false,
  };

  // DOM Elements cache
  let dom = {};

  function init() {
    cacheDom();
    initTheme();
    bindEvents();
    handleInitialRoute();
    refreshAllData();
  }

  function cacheDom() {
    dom = {
      navItems: document.querySelectorAll('.nav-item'),
      viewSections: document.querySelectorAll('.view-section'),
      pageTitle: document.getElementById('pageTitle'),
      statusBadge: document.getElementById('systemStatusBadge'),
      statusText: document.getElementById('systemStatusText'),
      refreshBtn: document.getElementById('globalRefreshBtn'),
      themeToggleBtn: document.getElementById('themeToggleBtn'),
      themeToggleText: document.getElementById('themeToggleText'),
      themeIcon: document.getElementById('themeIcon'),
      toastContainer: document.getElementById('toastContainer'),
      
      // Overview elements
      metricCompliance: document.getElementById('metricCompliance'),
      metricDriftCount: document.getElementById('metricDriftCount'),
      metricMonitoredKeys: document.getElementById('metricMonitoredKeys'),
      metricBackupsCount: document.getElementById('metricBackupsCount'),
      metricReportsCount: document.getElementById('metricReportsCount'),
      overviewConfigTable: document.getElementById('overviewConfigTableBody'),
      overviewLogsTable: document.getElementById('overviewLogsTableBody'),
      chartCanvas: document.getElementById('complianceDoughnutCanvas'),
      chartPercentage: document.getElementById('chartPercentageText'),
      chartLegendCompliant: document.getElementById('legendCompliantCount'),
      chartLegendDrifted: document.getElementById('legendDriftedCount'),
      overviewDetectBtn: document.getElementById('overviewDetectBtn'),
      overviewSimulateSelect: document.getElementById('overviewSimulateSelect'),
      overviewSimulateBtn: document.getElementById('overviewSimulateBtn'),
      
      // Configuration elements
      configTableBody: document.getElementById('configTableBody'),
      configSimulateSelect: document.getElementById('configSimulateSelect'),
      configSimulateBtn: document.getElementById('configSimulateBtn'),
      
      // Drift Detection elements
      driftScanBtn: document.getElementById('driftScanBtn'),
      driftStatusAlert: document.getElementById('driftStatusAlert'),
      driftTableBody: document.getElementById('driftTableBody'),
      driftLastScanTime: document.getElementById('driftLastScanTime'),
      driftReportNotice: document.getElementById('driftReportNotice'),
      driftGoRepairBtn: document.getElementById('driftGoRepairBtn'),
      
      // Auto Repair elements
      repairStatusCard: document.getElementById('repairStatusCard'),
      repairPreviewTable: document.getElementById('repairPreviewTableBody'),
      repairConfirmCheckbox: document.getElementById('repairConfirmCheckbox'),
      executeRepairBtn: document.getElementById('executeRepairBtn'),
      repairResultCard: document.getElementById('repairResultCard'),
      repairResultBody: document.getElementById('repairResultBody'),
      
      // Backups elements
      backupsTableBody: document.getElementById('backupsTableBody'),
      restoreModal: document.getElementById('restoreModal'),
      restoreModalFile: document.getElementById('restoreModalFile'),
      restoreConfirmCheckbox: document.getElementById('restoreConfirmCheckbox'),
      confirmRestoreBtn: document.getElementById('confirmRestoreBtn'),
      cancelRestoreBtn: document.getElementById('cancelRestoreBtn'),
      
      // Reports elements
      reportsTableBody: document.getElementById('reportsTableBody'),
      reportModal: document.getElementById('reportModal'),
      reportModalTitle: document.getElementById('reportModalTitle'),
      reportModalJson: document.getElementById('reportModalJson'),
      closeReportModalBtn: document.getElementById('closeReportModalBtn'),
      
      // Audit Logs elements
      logsTableBody: document.getElementById('logsTableBody'),
      logSearchInput: document.getElementById('logSearchInput'),
      logsCountBadge: document.getElementById('logsCountBadge'),
      refreshLogsBtn: document.getElementById('refreshLogsBtn'),
    };
  }

  function bindEvents() {
    // Nav tab clicks
    dom.navItems.forEach(item => {
      item.addEventListener('click', (e) => {
        e.preventDefault();
        const tab = item.getAttribute('data-tab');
        switchTab(tab);
      });
    });

    // Global refresh
    if (dom.refreshBtn) {
      dom.refreshBtn.addEventListener('click', () => {
        refreshAllData();
        showToast('System data refreshed', 'info');
      });
    }

    // Apple Theme toggle
    if (dom.themeToggleBtn) {
      dom.themeToggleBtn.addEventListener('click', toggleTheme);
    }

    // Hash navigation
    window.addEventListener('hashchange', () => {
      const hash = window.location.hash.replace('#', '');
      if (hash) switchTab(hash, false);
    });

    // Overview buttons
    if (dom.overviewDetectBtn) {
      dom.overviewDetectBtn.addEventListener('click', () => runDriftScan(true));
    }
    if (dom.overviewSimulateBtn) {
      dom.overviewSimulateBtn.addEventListener('click', () => {
        const opt = dom.overviewSimulateSelect.value;
        if (opt) triggerSimulation(opt);
      });
    }

    // Config simulate
    if (dom.configSimulateBtn) {
      dom.configSimulateBtn.addEventListener('click', () => {
        const opt = dom.configSimulateSelect.value;
        if (opt) triggerSimulation(opt);
      });
    }

    // Drift page scan
    if (dom.driftScanBtn) {
      dom.driftScanBtn.addEventListener('click', () => runDriftScan(false));
    }
    if (dom.driftGoRepairBtn) {
      dom.driftGoRepairBtn.addEventListener('click', () => switchTab('repair'));
    }

    // Repair checkbox and execute button
    if (dom.repairConfirmCheckbox) {
      dom.repairConfirmCheckbox.addEventListener('change', () => {
        dom.executeRepairBtn.disabled = !dom.repairConfirmCheckbox.checked || state.isRepairing;
      });
    }
    if (dom.executeRepairBtn) {
      dom.executeRepairBtn.addEventListener('click', executeRepair);
    }

    // Backups restore modal
    if (dom.cancelRestoreBtn) {
      dom.cancelRestoreBtn.addEventListener('click', closeRestoreModal);
    }
    if (dom.restoreConfirmCheckbox) {
      dom.restoreConfirmCheckbox.addEventListener('change', () => {
        dom.confirmRestoreBtn.disabled = !dom.restoreConfirmCheckbox.checked;
      });
    }
    if (dom.confirmRestoreBtn) {
      dom.confirmRestoreBtn.addEventListener('click', executeRestore);
    }

    // Report modal close
    if (dom.closeReportModalBtn) {
      dom.closeReportModalBtn.addEventListener('click', () => {
        dom.reportModal.classList.remove('active');
      });
    }

    // Log search input
    if (dom.logSearchInput) {
      dom.logSearchInput.addEventListener('input', (e) => {
        renderLogsTable(e.target.value);
      });
    }
    if (dom.refreshLogsBtn) {
      dom.refreshLogsBtn.addEventListener('click', loadLogs);
    }
  }

  function handleInitialRoute() {
    const hash = window.location.hash.replace('#', '');
    if (hash && document.getElementById(`view-${hash}`)) {
      switchTab(hash, false);
    } else {
      switchTab('overview', false);
    }
  }

  function switchTab(tabId, updateHash = true) {
    if (!document.getElementById(`view-${tabId}`)) return;
    state.currentTab = tabId;

    dom.navItems.forEach(item => {
      item.classList.toggle('active', item.getAttribute('data-tab') === tabId);
    });

    dom.viewSections.forEach(section => {
      section.classList.toggle('active', section.id === `view-${tabId}`);
    });

    // Update Header title
    const titles = {
      overview: 'System Overview',
      configuration: 'Configuration Inspector',
      drift: 'Drift Detection & Analysis',
      repair: 'Automated Configuration Repair',
      backups: 'Backup Management',
      reports: 'Historical Drift Reports',
      logs: 'System Audit Logs',
      about: 'About Project & Architecture',
    };
    dom.pageTitle.textContent = titles[tabId] || 'Dashboard';

    if (updateHash) {
      window.location.hash = tabId;
    }

    // Refresh context if opening tab
    if (tabId === 'backups') loadBackups();
    if (tabId === 'reports') loadReports();
    if (tabId === 'logs') loadLogs();
    if (tabId === 'configuration') loadConfiguration();
  }

  // --------------------------------------------------------------------------
  // API Calls & Data Loading
  // --------------------------------------------------------------------------

  async function refreshAllData() {
    try {
      await Promise.all([
        loadDashboard(),
        loadConfiguration(),
        loadBackups(),
        loadReports(),
        loadLogs(),
      ]);
    } catch (err) {
      console.error('Error refreshing system data:', err);
    }
  }

  async function loadDashboard() {
    try {
      const res = await fetch('/api/dashboard');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      state.dashboard = data;

      updateStatusHeader(data.is_compliant, data.system_status);
      renderOverviewCards(data);
      renderOverviewTables(data);
      renderComplianceChart(data.total_baseline_settings, data.drift_count);
      renderAutoRepairState(data);
      renderDriftPage(data);
    } catch (err) {
      console.error('Failed to load dashboard:', err);
      showToast('Failed to load dashboard data from API', 'danger');
    }
  }

  async function loadConfiguration() {
    try {
      const res = await fetch('/api/configuration');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      state.configuration = data;
      renderConfigTable(data.settings);
    } catch (err) {
      console.error('Failed to load configuration:', err);
    }
  }

  async function loadBackups() {
    try {
      const res = await fetch('/api/backups');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      state.backups = data.backups || [];
      renderBackupsTable(state.backups);
      if (dom.metricBackupsCount) dom.metricBackupsCount.textContent = state.backups.length;
    } catch (err) {
      console.error('Failed to load backups:', err);
    }
  }

  async function loadReports() {
    try {
      const res = await fetch('/api/reports');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      state.reports = data.reports || [];
      renderReportsTable(state.reports);
      if (dom.metricReportsCount) dom.metricReportsCount.textContent = state.reports.length;
    } catch (err) {
      console.error('Failed to load reports:', err);
    }
  }

  async function loadLogs() {
    try {
      const res = await fetch('/api/logs?limit=100');
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();
      state.logs = data.logs || [];
      renderLogsTable();
    } catch (err) {
      console.error('Failed to load logs:', err);
    }
  }

  // --------------------------------------------------------------------------
  // User Actions (Scan, Simulate, Repair, Restore)
  // --------------------------------------------------------------------------

  async function runDriftScan(goToTab = false) {
    if (state.isScanning) return;
    state.isScanning = true;
    updateScanButtonStates(true);

    try {
      const res = await fetch('/api/drift/detect', { method: 'POST' });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      showToast(`Scan complete: ${data.drift_count} drift issue(s) detected.`, data.is_compliant ? 'success' : 'danger');

      // Refresh all views with fresh scan result
      await refreshAllData();

      if (goToTab) {
        switchTab('drift');
      }
    } catch (err) {
      console.error('Drift scan failed:', err);
      showToast('Drift scan failed: ' + err.message, 'danger');
    } finally {
      state.isScanning = false;
      updateScanButtonStates(false);
    }
  }

  async function triggerSimulation(option) {
    try {
      const res = await fetch('/api/drift/simulate', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ option }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Failed to simulate drift');

      showToast(`Simulated drift applied: ${data.simulation.label}`, 'warning');
      await refreshAllData();
      switchTab('drift');
    } catch (err) {
      showToast('Simulation error: ' + err.message, 'danger');
    }
  }

  async function executeRepair() {
    if (!dom.repairConfirmCheckbox.checked || state.isRepairing) return;
    state.isRepairing = true;
    dom.executeRepairBtn.disabled = true;
    dom.executeRepairBtn.innerHTML = '<span class="spinner"></span> Applying Repair...';

    try {
      const res = await fetch('/api/repair', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ confirm: true }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Repair operation failed');

      const result = data.repair_result;
      displayRepairSuccess(result);
      showToast('Configuration successfully repaired and verified compliant!', 'success');

      // Reset checkbox
      dom.repairConfirmCheckbox.checked = false;

      // Refresh data
      await refreshAllData();
    } catch (err) {
      console.error('Repair error:', err);
      showToast('Repair failed: ' + err.message, 'danger');
      displayRepairError(err.message);
    } finally {
      state.isRepairing = false;
      dom.executeRepairBtn.disabled = true;
      dom.executeRepairBtn.innerHTML = 'Execute Auto Repair';
    }
  }

  function displayRepairSuccess(result) {
    if (!dom.repairResultCard) return;
    dom.repairResultCard.style.display = 'block';

    let html = `
      <div class="alert-box alert-success">
        <svg width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
        <div>
          <strong>Repair Executed Successfully</strong>
          <div>Repaired <strong>${result.repaired_count}</strong> configuration parameter(s) back to golden baseline.</div>
        </div>
      </div>
      <div style="margin-top: 14px; font-size: 0.88rem; line-height: 1.6;">
        <div><strong>Pre-Repair Backup:</strong> <code>${escapeHtml(result.backup_filename || 'Created')}</code></div>
        <div><strong>Post-Repair Verification:</strong> <span class="badge badge-compliant">PASSED - 100% COMPLIANT</span></div>
        ${result.report_generated ? `<div><strong>Generated Report:</strong> <code>${escapeHtml(result.report_generated)}</code></div>` : ''}
      </div>
    `;
    dom.repairResultBody.innerHTML = html;
  }

  function displayRepairError(errMsg) {
    if (!dom.repairResultCard) return;
    dom.repairResultCard.style.display = 'block';
    dom.repairResultBody.innerHTML = `
      <div class="alert-box alert-danger">
        <strong>Repair Failed:</strong> ${escapeHtml(errMsg)}
      </div>
    `;
  }

  function openRestoreModal(filename) {
    state.pendingRestoreFile = filename;
    dom.restoreModalFile.textContent = filename;
    dom.restoreConfirmCheckbox.checked = false;
    dom.confirmRestoreBtn.disabled = true;
    dom.restoreModal.classList.add('active');
  }

  function closeRestoreModal() {
    state.pendingRestoreFile = null;
    dom.restoreModal.classList.remove('active');
  }

  async function executeRestore() {
    if (!state.pendingRestoreFile || !dom.restoreConfirmCheckbox.checked) return;
    dom.confirmRestoreBtn.disabled = true;
    dom.confirmRestoreBtn.innerHTML = '<span class="spinner"></span> Restoring...';

    try {
      const res = await fetch('/api/backups/restore', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          confirm: true,
          filename: state.pendingRestoreFile,
        }),
      });
      const data = await res.json();
      if (!res.ok) throw new Error(data.error || 'Restore failed');

      showToast(`Successfully restored configuration from ${state.pendingRestoreFile}`, 'success');
      closeRestoreModal();
      await refreshAllData();
      switchTab('configuration');
    } catch (err) {
      showToast('Restore failed: ' + err.message, 'danger');
    } finally {
      dom.confirmRestoreBtn.disabled = false;
      dom.confirmRestoreBtn.innerHTML = 'Restore Configuration';
    }
  }

  async function openReportModal(filename) {
    try {
      const res = await fetch(`/api/reports/${encodeURIComponent(filename)}`);
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      const data = await res.json();

      dom.reportModalTitle.textContent = filename;
      dom.reportModalJson.textContent = JSON.stringify(data.report, null, 2);
      dom.reportModal.classList.add('active');
    } catch (err) {
      showToast('Failed to load report: ' + err.message, 'danger');
    }
  }

  // --------------------------------------------------------------------------
  // Render Helpers
  // --------------------------------------------------------------------------

  function updateStatusHeader(isCompliant, statusText) {
    if (!dom.statusBadge) return;
    dom.statusBadge.className = 'status-indicator-badge ' + (isCompliant ? 'compliant' : 'drifted');
    dom.statusText.textContent = isCompliant ? 'SYSTEM COMPLIANT' : `${state.dashboard ? state.dashboard.drift_count : 1} DRIFT DETECTED`;
  }

  function renderOverviewCards(data) {
    if (dom.metricCompliance) {
      dom.metricCompliance.textContent = data.system_status;
      dom.metricCompliance.style.color = data.is_compliant ? 'var(--success)' : 'var(--danger)';
    }
    if (dom.metricDriftCount) {
      dom.metricDriftCount.textContent = data.drift_count;
      dom.metricDriftCount.style.color = data.drift_count > 0 ? 'var(--danger)' : 'var(--text-main)';
    }
    if (dom.metricMonitoredKeys) {
      dom.metricMonitoredKeys.textContent = data.total_baseline_settings;
    }
    if (dom.metricBackupsCount) {
      dom.metricBackupsCount.textContent = data.backup_count;
    }
    if (dom.metricReportsCount) {
      dom.metricReportsCount.textContent = data.report_count;
    }
  }

  function renderOverviewTables(data) {
    // Config quick glance
    if (dom.overviewConfigTable && data.baseline_config && data.current_config) {
      const allKeys = Object.keys(data.baseline_config);
      let html = '';
      allKeys.forEach(key => {
        const exp = data.baseline_config[key];
        const act = data.current_config[key];
        const isMatch = exp === act;
        html += `
          <tr class="${isMatch ? '' : 'row-drifted'}">
            <td><strong><code>${escapeHtml(key)}</code></strong></td>
            <td><code>${escapeHtml(String(exp))}</code></td>
            <td><code>${escapeHtml(String(act))}</code></td>
            <td>
              <span class="badge ${isMatch ? 'badge-compliant' : 'badge-drifted'}">
                ${isMatch ? 'Compliant' : 'Drifted'}
              </span>
            </td>
          </tr>
        `;
      });
      dom.overviewConfigTable.innerHTML = html;
    }

    // Recent logs glance
    if (dom.overviewLogsTable && data.recent_logs) {
      const recent = data.recent_logs.slice(-5).reverse();
      let html = '';
      if (recent.length === 0) {
        html = '<tr><td colspan="2" class="empty-state">No recent activity</td></tr>';
      } else {
        recent.forEach(line => {
          const match = line.match(/^\[(.*?)\] (.*)$/);
          const time = match ? match[1] : '';
          const msg = match ? match[2] : line;
          html += `
            <tr>
              <td style="white-space:nowrap; font-size:0.78rem; color:var(--text-muted); font-family:monospace;">${escapeHtml(time)}</td>
              <td style="font-size:0.85rem;">${escapeHtml(msg)}</td>
            </tr>
          `;
        });
      }
      dom.overviewLogsTable.innerHTML = html;
    }
  }

  function renderConfigTable(settings) {
    if (!dom.configTableBody || !settings) return;
    let html = '';
    settings.forEach(s => {
      const isMatch = !s.is_drifted;
      html += `
        <tr class="${isMatch ? '' : 'row-drifted'}">
          <td>
            <strong><code>${escapeHtml(s.key)}</code></strong>
          </td>
          <td><code>${escapeHtml(String(s.expected))}</code></td>
          <td><code>${escapeHtml(String(s.actual))}</code></td>
          <td>
            <span class="badge ${isMatch ? 'badge-compliant' : 'badge-drifted'}">
              ${isMatch ? 'COMPLIANT' : 'DRIFT DETECTED'}
            </span>
          </td>
        </tr>
      `;
    });
    dom.configTableBody.innerHTML = html;
  }

  function renderDriftPage(data) {
    if (!dom.driftTableBody) return;
    const hasDrift = data.drift && data.drift.length > 0;

    if (dom.driftLastScanTime) {
      dom.driftLastScanTime.textContent = new Date().toLocaleTimeString();
    }

    if (!hasDrift) {
      dom.driftStatusAlert.innerHTML = `
        <div class="alert-box alert-success" style="margin-bottom:0;">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
          <div>
            <strong style="font-size: 1rem;">System is Fully Compliant</strong>
            <div>All ${data.total_baseline_settings} monitored settings match golden baseline parameters. No drift detected.</div>
          </div>
        </div>
      `;
      dom.driftTableBody.innerHTML = `
        <tr>
          <td colspan="4" class="empty-state">
            <svg class="empty-icon" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="12" cy="12" r="10"></circle><polyline points="12 6 12 12 14 14"></polyline></svg>
            <div class="empty-title">No Configuration Drift</div>
            <div class="empty-desc">The test configuration matches baseline.json perfectly.</div>
          </td>
        </tr>
      `;
      if (dom.driftGoRepairBtn) dom.driftGoRepairBtn.style.display = 'none';
    } else {
      dom.driftStatusAlert.innerHTML = `
        <div class="alert-box alert-danger" style="margin-bottom:0;">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
          <div>
            <strong style="font-size: 1rem;">Configuration Drift Detected: ${data.drift.length} Issue(s)</strong>
            <div>Security-sensitive differences exist between the baseline and active test configuration.</div>
          </div>
        </div>
      `;

      let html = '';
      data.drift.forEach(d => {
        html += `
          <tr class="row-drifted">
            <td><strong><code>${escapeHtml(d.key)}</code></strong></td>
            <td><code>${escapeHtml(String(d.expected))}</code></td>
            <td><code>${escapeHtml(String(d.actual))}</code></td>
            <td><span class="badge badge-drifted">Requires Remediation</span></td>
          </tr>
        `;
      });
      dom.driftTableBody.innerHTML = html;
      if (dom.driftGoRepairBtn) dom.driftGoRepairBtn.style.display = 'inline-flex';
    }
  }

  function renderAutoRepairState(data) {
    if (!dom.repairStatusCard) return;
    const hasDrift = data.drift && data.drift.length > 0;

    if (!hasDrift) {
      dom.repairStatusCard.innerHTML = `
        <div class="alert-box alert-success" style="margin:0;">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M22 11.08V12a10 10 0 1 1-5.93-9.14"></path><polyline points="22 4 12 14.01 9 11.01"></polyline></svg>
          <div>
            <strong>No Repair Required</strong>
            <div>System is in full compliance with baseline.json. No drifted settings to remediate.</div>
          </div>
        </div>
      `;
      dom.repairPreviewTable.innerHTML = '<tr><td colspan="3" class="empty-state">No settings require repair</td></tr>';
      dom.repairConfirmCheckbox.disabled = true;
      dom.repairConfirmCheckbox.checked = false;
      dom.executeRepairBtn.disabled = true;
    } else {
      dom.repairStatusCard.innerHTML = `
        <div class="alert-box alert-warning" style="margin:0;">
          <svg width="22" height="22" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
          <div>
            <strong>${data.drift.length} Drifted Setting(s) Eligible for Auto-Repair</strong>
            <div>Executing repair will automatically save a backup to <code>backups/</code> before restoring compliant baseline values.</div>
          </div>
        </div>
      `;

      let html = '';
      data.drift.forEach(d => {
        html += `
          <tr>
            <td><strong><code>${escapeHtml(d.key)}</code></strong></td>
            <td><code>${escapeHtml(String(d.actual))}</code></td>
            <td><strong style="color:var(--success);"><code>${escapeHtml(String(d.expected))}</code></strong></td>
          </tr>
        `;
      });
      dom.repairPreviewTable.innerHTML = html;
      dom.repairConfirmCheckbox.disabled = false;
      dom.executeRepairBtn.disabled = !dom.repairConfirmCheckbox.checked;
    }
  }

  function renderBackupsTable(backups) {
    if (!dom.backupsTableBody) return;
    if (backups.length === 0) {
      dom.backupsTableBody.innerHTML = `
        <tr><td colspan="4" class="empty-state">No backups available in backups/</td></tr>
      `;
      return;
    }

    let html = '';
    backups.forEach(b => {
      html += `
        <tr>
          <td><strong><code>${escapeHtml(b.filename)}</code></strong></td>
          <td style="font-family:monospace; font-size:0.84rem;">${escapeHtml(b.created_at)}</td>
          <td>${formatBytes(b.size_bytes)}</td>
          <td>
            <button class="btn btn-outline btn-sm btn-restore-trigger" data-filename="${escapeHtml(b.filename)}">
              Restore...
            </button>
          </td>
        </tr>
      `;
    });
    dom.backupsTableBody.innerHTML = html;

    // Bind restore buttons
    dom.backupsTableBody.querySelectorAll('.btn-restore-trigger').forEach(btn => {
      btn.addEventListener('click', () => {
        const file = btn.getAttribute('data-filename');
        openRestoreModal(file);
      });
    });
  }

  function renderReportsTable(reports) {
    if (!dom.reportsTableBody) return;
    if (reports.length === 0) {
      dom.reportsTableBody.innerHTML = `
        <tr><td colspan="5" class="empty-state">No reports generated in reports/</td></tr>
      `;
      return;
    }

    let html = '';
    reports.forEach(r => {
      const isComp = r.status === 'COMPLIANT';
      html += `
        <tr>
          <td><strong><code>${escapeHtml(r.filename)}</code></strong></td>
          <td style="font-family:monospace; font-size:0.84rem;">${escapeHtml(r.created_at)}</td>
          <td>
            <span class="badge ${isComp ? 'badge-compliant' : 'badge-drifted'}">
              ${escapeHtml(r.status)}
            </span>
          </td>
          <td>${r.issue_count} issue(s)</td>
          <td>
            <button class="btn btn-outline btn-sm btn-view-report" data-filename="${escapeHtml(r.filename)}">
              View JSON
            </button>
          </td>
        </tr>
      `;
    });
    dom.reportsTableBody.innerHTML = html;

    dom.reportsTableBody.querySelectorAll('.btn-view-report').forEach(btn => {
      btn.addEventListener('click', () => {
        const file = btn.getAttribute('data-filename');
        openReportModal(file);
      });
    });
  }

  function renderLogsTable(filterText = '') {
    if (!dom.logsTableBody) return;
    const filter = filterText.toLowerCase().trim();
    const filtered = state.logs.filter(line => !filter || line.toLowerCase().includes(filter));

    if (dom.logsCountBadge) {
      dom.logsCountBadge.textContent = `${filtered.length} entries`;
    }

    if (filtered.length === 0) {
      dom.logsTableBody.innerHTML = `
        <tr><td colspan="2" class="empty-state">No matching log entries found</td></tr>
      `;
      return;
    }

    let html = '';
    // Show newest logs at top
    filtered.slice().reverse().forEach(line => {
      const match = line.match(/^\[(.*?)\] (.*)$/);
      const time = match ? match[1] : '';
      const msg = match ? match[2] : line;

      let badgeType = 'badge-neutral';
      if (msg.includes('passed') || msg.includes('COMPLIANT')) badgeType = 'badge-compliant';
      else if (msg.includes('Drift scan completed') && !msg.includes('0 issue')) badgeType = 'badge-drifted';
      else if (msg.includes('Simulated drift')) badgeType = 'badge-warning';
      else if (msg.includes('Repair completed')) badgeType = 'badge-compliant';

      html += `
        <tr>
          <td style="width: 180px; font-family:monospace; font-size:0.8rem; color:var(--text-muted);">${escapeHtml(time)}</td>
          <td>
            <span class="badge ${badgeType}" style="margin-right:8px;">${getLogCategory(msg)}</span>
            <span style="font-size:0.88rem;">${escapeHtml(msg)}</span>
          </td>
        </tr>
      `;
    });
    dom.logsTableBody.innerHTML = html;
  }

  function getLogCategory(msg) {
    if (msg.includes('System initialized')) return 'INIT';
    if (msg.includes('Simulated drift')) return 'SIMULATE';
    if (msg.includes('Drift scan')) return 'SCAN';
    if (msg.includes('repair') || msg.includes('Repair')) return 'REPAIR';
    if (msg.includes('verification')) return 'VERIFY';
    if (msg.includes('Restored')) return 'RESTORE';
    return 'EVENT';
  }

  // --------------------------------------------------------------------------
  // Apple Theme Management (Light / Dark Mode)
  // --------------------------------------------------------------------------

  function initTheme() {
    const savedTheme = localStorage.getItem('driftguard_theme') || 'light';
    applyTheme(savedTheme);
  }

  function toggleTheme() {
    const current = document.documentElement.getAttribute('data-theme') === 'dark' ? 'dark' : 'light';
    const nextTheme = current === 'dark' ? 'light' : 'dark';
    applyTheme(nextTheme);
    localStorage.setItem('driftguard_theme', nextTheme);
    showToast(`Switched to Apple ${nextTheme.toUpperCase()} mode`, 'info');
  }

  function applyTheme(theme) {
    if (theme === 'dark') {
      document.documentElement.setAttribute('data-theme', 'dark');
      if (dom.themeToggleText) dom.themeToggleText.textContent = 'Dark';
      if (dom.themeIcon) {
        dom.themeIcon.innerHTML = '<path d="M21 12.79A9 9 0 1 1 11.21 3 7 7 0 0 0 21 12.79z"></path>';
      }
    } else {
      document.documentElement.removeAttribute('data-theme');
      if (dom.themeToggleText) dom.themeToggleText.textContent = 'Light';
      if (dom.themeIcon) {
        dom.themeIcon.innerHTML = '<circle cx="12" cy="12" r="5"></circle><line x1="12" y1="1" x2="12" y2="3"></line><line x1="12" y1="21" x2="12" y2="23"></line><line x1="4.22" y1="4.22" x2="5.64" y2="5.64"></line><line x1="18.36" y1="18.36" x2="19.78" y2="19.78"></line><line x1="1" y1="12" x2="3" y2="12"></line><line x1="21" y1="12" x2="23" y2="12"></line><line x1="4.22" y1="19.78" x2="5.64" y2="18.36"></line><line x1="18.36" y1="5.64" x2="19.78" y2="4.22"></line>';
      }
    }

    if (state.dashboard) {
      renderComplianceChart(state.dashboard.total_baseline_settings, state.dashboard.drift_count);
    }
  }

  // --------------------------------------------------------------------------
  // Offline Native Canvas Doughnut Chart
  // --------------------------------------------------------------------------

  function renderComplianceChart(total, driftCount) {
    const canvas = dom.chartCanvas;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    const width = canvas.width;
    const height = canvas.height;
    const centerX = width / 2;
    const centerY = height / 2;
    const radius = 64;
    const lineWidth = 16;

    ctx.clearRect(0, 0, width, height);

    if (total === 0) total = 6;
    const compliantCount = Math.max(0, total - driftCount);
    const compliantRatio = compliantCount / total;
    const percentage = Math.round(compliantRatio * 100);

    // Dynamic track color according to current theme
    const isDark = document.documentElement.getAttribute('data-theme') === 'dark';
    const trackColor = isDark ? 'rgba(255, 255, 255, 0.08)' : '#e2e8f0';

    // Background track
    ctx.beginPath();
    ctx.arc(centerX, centerY, radius, 0, 2 * Math.PI);
    ctx.strokeStyle = trackColor;
    ctx.lineWidth = lineWidth;
    ctx.stroke();

    // Compliant segment (Vibrant Emerald)
    const startAngle = -Math.PI / 2;
    const compliantAngle = startAngle + compliantRatio * (2 * Math.PI);

    if (compliantCount > 0) {
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius, startAngle, compliantAngle);
      ctx.strokeStyle = '#10b981';
      ctx.lineWidth = lineWidth;
      ctx.lineCap = 'round';
      ctx.stroke();
    }

    // Drift segment (Vibrant Rose)
    if (driftCount > 0) {
      ctx.beginPath();
      ctx.arc(centerX, centerY, radius, compliantAngle, startAngle + 2 * Math.PI);
      ctx.strokeStyle = '#f43f5e';
      ctx.lineWidth = lineWidth;
      ctx.lineCap = 'round';
      ctx.stroke();
    }

    if (dom.chartPercentage) dom.chartPercentage.textContent = `${percentage}%`;
    if (dom.chartLegendCompliant) dom.chartLegendCompliant.textContent = compliantCount;
    if (dom.chartLegendDrifted) dom.chartLegendDrifted.textContent = driftCount;
  }

  // --------------------------------------------------------------------------
  // UI Helpers
  // --------------------------------------------------------------------------

  function updateScanButtonStates(scanning) {
    const btns = [dom.overviewDetectBtn, dom.driftScanBtn];
    btns.forEach(btn => {
      if (!btn) return;
      btn.disabled = scanning;
      btn.innerHTML = scanning
        ? '<span class="spinner"></span> Scanning...'
        : '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><circle cx="11" cy="11" r="8"></circle><line x1="21" y1="21" x2="16.65" y2="16.65"></line></svg> Run Drift Scan';
    });
  }

  function showToast(message, type = 'info') {
    if (!dom.toastContainer) return;
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.innerHTML = `
      <span>${escapeHtml(message)}</span>
    `;
    dom.toastContainer.appendChild(toast);

    setTimeout(() => {
      toast.style.transition = 'opacity 0.3s ease, transform 0.3s ease';
      toast.style.opacity = '0';
      toast.style.transform = 'translateY(10px)';
      setTimeout(() => toast.remove(), 300);
    }, 4000);
  }

  function escapeHtml(str) {
    if (typeof str !== 'string') return String(str);
    return str
      .replace(/&/g, '&amp;')
      .replace(/</g, '&lt;')
      .replace(/>/g, '&gt;')
      .replace(/"/g, '&quot;')
      .replace(/'/g, '&#039;');
  }

  function formatBytes(bytes) {
    if (bytes === 0) return '0 B';
    const k = 1024;
    const sizes = ['B', 'KB', 'MB', 'GB'];
    const i = Math.floor(Math.log(bytes) / Math.log(k));
    return parseFloat((bytes / Math.pow(k, i)).toFixed(1)) + ' ' + sizes[i];
  }

  return { init, switchTab };
})();

document.addEventListener('DOMContentLoaded', App.init);
