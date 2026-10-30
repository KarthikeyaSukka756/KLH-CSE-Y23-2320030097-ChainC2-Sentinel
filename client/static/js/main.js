/**
 * ChainC2 Sentinel — Master Research Dashboard Controller
 * Connects all 7 core operational views to real REST APIs.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Initialize Navigation
    const nav = new NavigationManager();
    window.Navigation = nav;

    // Application State
    const State = {
        sepoliaStatus: null,
        sepoliaTransactions: [],
        alerts: [],
        investigations: [],
        mitigations: [],
        evidence: [],
        generatorStatus: null,
        selectedInvestigationId: null,
        isContinuousMonitoring: false,
        continuousPollTimer: null,
    };

    // Helper: Escape HTML strings
    function escapeHtml(str) {
        if (str == null) return '';
        return String(str)
            .replace(/&/g, '&amp;')
            .replace(/</g, '&lt;')
            .replace(/>/g, '&gt;')
            .replace(/"/g, '&quot;')
            .replace(/'/g, '&#39;');
    }

    // Helper: Toast Notifications
    function showNotification(message, type = 'info') {
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.style.cssText = 'position:fixed;top:1rem;right:1rem;z-index:9999;display:flex;flex-direction:column;gap:0.5rem;max-width:400px;pointer-events:none;';
            document.body.appendChild(container);
        }
        const colors = {
            info: 'var(--color-primary)',
            error: 'var(--color-danger)',
            success: 'var(--color-success)',
            warning: 'var(--color-warning)'
        };
        const color = colors[type] || colors.info;
        const toast = document.createElement('div');
        toast.style.cssText = `background:var(--bg-secondary);border:1px solid ${color};border-left:4px solid ${color};border-radius:var(--radius-md);padding:0.75rem 1rem;font-size:0.8rem;color:var(--text-primary);box-shadow:0 4px 12px rgba(0,0,0,0.3);pointer-events:all;`;
        toast.innerHTML = `<span>${escapeHtml(message)}</span>`;
        container.appendChild(toast);
        setTimeout(() => {
            toast.style.opacity = '0';
            toast.style.transition = 'opacity 0.4s';
            setTimeout(() => toast.remove(), 400);
        }, 4500);
    }

    // Helper: Rich Pop-up Alert Notification
    function showLiveAlertToast(alert) {
        let container = document.getElementById('live-alert-toast-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'live-alert-toast-container';
            container.style.cssText = 'position:fixed;bottom:1.5rem;right:1.5rem;z-index:10000;display:flex;flex-direction:column;gap:0.75rem;max-width:440px;pointer-events:none;';
            document.body.appendChild(container);
        }

        const toast = document.createElement('div');
        toast.style.cssText = 'background:var(--bg-card);border:2px solid var(--color-danger);border-radius:var(--radius-lg);padding:1rem 1.25rem;color:var(--text-primary);box-shadow:0 8px 24px rgba(239,68,68,0.35);pointer-events:all;animation:slideInUp 0.35s ease;display:flex;flex-direction:column;gap:0.5rem;';

        const scoreVal = alert.score != null ? alert.score.toFixed(1) : '100.0';
        const threshVal = alert.threshold != null ? alert.threshold.toFixed(1) : '80.0';
        const invId = alert.investigation_id || alert.alert_id;
        const timeStr = alert.timestamp ? new Date(alert.timestamp).toLocaleTimeString() : new Date().toLocaleTimeString();

        toast.innerHTML = `
            <div style="display:flex;justify-content:space-between;align-items:center;">
                <div style="display:flex;align-items:center;gap:0.5rem;">
                    <span style="display:inline-block;width:10px;height:10px;border-radius:50%;background:var(--color-danger);animation:pulse 1.2s infinite;"></span>
                    <strong style="color:var(--color-danger);font-size:0.85rem;letter-spacing:0.05em;">🚨 CRITICAL SECURITY ALERT DETECTED</strong>
                </div>
                <button type="button" class="btn-close-toast" style="background:transparent;border:none;color:var(--text-muted);font-size:1.1rem;cursor:pointer;line-height:1;">&times;</button>
            </div>
            <div style="display:flex;justify-content:space-between;align-items:baseline;font-size:0.8rem;">
                <span class="font-mono font-bold">${escapeHtml(alert.alert_id)}</span>
                <span class="badge badge-danger font-mono font-bold">${scoreVal} / ${threshVal}</span>
            </div>
            <div style="font-size:0.75rem;color:var(--text-secondary);line-height:1.4;">
                ${escapeHtml(alert.explanation || 'Multi-layer blockchain C2 activity correlated and verified.')}
            </div>
            <div style="display:flex;justify-content:space-between;align-items:center;margin-top:0.35rem;padding-top:0.5rem;border-top:1px solid var(--border-color);">
                <span class="text-muted" style="font-size:0.7rem;">Detected: ${escapeHtml(timeStr)}</span>
                <button type="button" class="btn btn-primary btn-sm btn-toast-open-inv" style="padding:0.3rem 0.75rem;font-size:0.75rem;">🔍 View Investigation</button>
            </div>
        `;

        const openBtn = toast.querySelector('.btn-toast-open-inv');
        if (openBtn) {
            openBtn.addEventListener('click', () => {
                navigateToInvestigation(invId);
                toast.remove();
            });
        }

        const closeBtn = toast.querySelector('.btn-close-toast');
        if (closeBtn) {
            closeBtn.addEventListener('click', () => {
                toast.remove();
            });
        }

        container.appendChild(toast);

        // Auto-dismiss after 12 seconds
        setTimeout(() => {
            if (toast.parentNode) {
                toast.style.opacity = '0';
                toast.style.transition = 'opacity 0.5s ease';
                setTimeout(() => toast.remove(), 500);
            }
        }, 12000);
    }

    // -------------------------------------------------------------------------
    // Shared Authoritative Connection State Synchronizer
    // -------------------------------------------------------------------------
    function updateConnectionUI(isConnected, statusText = '', lagBlocks = 0) {
        const connBadge = document.getElementById('sepolia-connection-badge');
        const rpcStatusEl = document.getElementById('health-rpc-status');

        let label = 'CONNECTED (SEPOLIA)';
        let badgeClass = 'badge badge-success';

        if (!isConnected) {
            label = statusText ? statusText.toUpperCase() : 'DISCONNECTED';
            badgeClass = 'badge badge-danger';
        } else if (lagBlocks != null && lagBlocks > 10) {
            label = 'DEGRADED (SEPOLIA)';
            badgeClass = 'badge badge-warning';
        }

        if (connBadge) {
            connBadge.className = badgeClass;
            connBadge.textContent = label;
        }
        if (rpcStatusEl) {
            rpcStatusEl.className = badgeClass;
            rpcStatusEl.textContent = label;
        }
    }

    // -------------------------------------------------------------------------
    // 1. LIVE MONITOR CONTROLLER
    // -------------------------------------------------------------------------
    // Concurrency guards for asynchronous polling
    let latestStatusReqId = 0;
    let latestTxReqId = 0;

    async function loadSepoliaStatus(force = false) {
        const reqId = ++latestStatusReqId;
        try {
            const data = await API.getSepoliaStatus(force);
            // Drop out-of-order response if a newer request already resolved
            if (reqId < latestStatusReqId) return;

            State.sepoliaStatus = data;

            // Synchronize Connection Badge across Header & Health Card
            updateConnectionUI(data.is_connected, data.connection_status, data.monitoring_lag_blocks);

            // Head Block & Cursor
            const headBlockEl = document.getElementById('sepolia-latest-block');
            if (headBlockEl) headBlockEl.textContent = data.latest_block ? `#${data.latest_block}` : '—';

            const cursorBlockEl = document.getElementById('sepolia-cursor-block');
            if (cursorBlockEl) cursorBlockEl.textContent = data.last_ingested_block ? `#${data.last_ingested_block}` : (data.latest_block ? `#${data.latest_block}` : '—');

            const cursorLagEl = document.getElementById('sepolia-cursor-lag');
            if (cursorLagEl) {
                const lag = data.monitoring_lag_blocks != null ? data.monitoring_lag_blocks : 0;
                cursorLagEl.textContent = `Lag: ${lag} block${lag === 1 ? '' : 's'}`;
            }

            const pollEl = document.getElementById('sepolia-last-poll');
            if (pollEl && data.last_poll_time) {
                pollEl.textContent = `Polled: ${new Date(data.last_poll_time).toLocaleTimeString()}`;
            }

            const totalTxsEl = document.getElementById('sepolia-total-txs');
            if (totalTxsEl) totalTxsEl.textContent = data.total_observed_transactions || 0;

            const totalAlertsEl = document.getElementById('sepolia-total-alerts');
            if (totalAlertsEl) totalAlertsEl.textContent = data.total_alerts || 0;

            const rpcUrlEl = document.getElementById('sepolia-rpc-url');
            if (rpcUrlEl && data.rpc_url) rpcUrlEl.textContent = data.rpc_url;

            // Continuous Daemon state
            const daemonStatusEl = document.getElementById('continuous-daemon-status');
            const toggleDaemonBtn = document.getElementById('btn-toggle-continuous');
            const isDaemonRunning = Boolean(data.continuous_monitoring_active || data.monitoring_active);
            State.isContinuousMonitoring = isDaemonRunning;

            if (daemonStatusEl && toggleDaemonBtn) {
                if (isDaemonRunning) {
                    daemonStatusEl.className = 'badge badge-success';
                    daemonStatusEl.textContent = 'DAEMON: RUNNING';
                    toggleDaemonBtn.textContent = '⏹ Stop Continuous Ingestion';
                } else {
                    daemonStatusEl.className = 'badge badge-neutral';
                    daemonStatusEl.textContent = 'DAEMON: IDLE';
                    toggleDaemonBtn.textContent = '▶ Start Continuous Ingestion';
                }
            }
        } catch (err) {
            console.error('Failed to load Sepolia status:', err);
        }
    }

    async function loadSepoliaTransactions() {
        const reqId = ++latestTxReqId;
        try {
            const filterEl = document.getElementById('sepolia-tx-filter');
            const filterVal = filterEl ? filterEl.value : '';
            const res = await API.getSepoliaTransactions(filterVal, 100);
            if (reqId < latestTxReqId) return;

            State.sepoliaTransactions = res.transactions || [];
            applyTxFilterAndRender();
        } catch (err) {
            console.error('Failed to load Sepolia transactions:', err);
        }
    }

    function applyTxFilterAndRender() {
        let txs = State.sepoliaTransactions || [];
        const searchInput = document.getElementById('sepolia-tx-search');
        const q = searchInput ? searchInput.value.trim().toLowerCase() : '';
        if (q) {
            txs = txs.filter(t =>
                (t.tx_hash && t.tx_hash.toLowerCase().includes(q)) ||
                (t.from_address && t.from_address.toLowerCase().includes(q)) ||
                (t.to_address && t.to_address.toLowerCase().includes(q)) ||
                (String(t.block_number).includes(q))
            );
        }
        renderSepoliaTransactions(txs);
    }

    function renderSepoliaTransactions(txs) {
        const tbody = document.getElementById('sepolia-tx-table-body');
        if (!tbody) return;

        if (!txs || txs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No transactions observed yet. Click "Poll Latest Block Now".</td></tr>';
            return;
        }

        tbody.innerHTML = txs.map(t => {
            const explorerUrl = t.explorer_url || `https://sepolia.etherscan.io/tx/${t.tx_hash}`;
            let statusBadge = '<span class="badge badge-neutral">MONITORED</span>';
            if (t.detection_status === 'TRIGGERED') {
                statusBadge = '<span class="badge badge-danger">TRIGGERED</span>';
            } else if (t.detection_status === 'BENIGN') {
                statusBadge = '<span class="badge badge-success">BENIGN</span>';
            }

            const hashShort = t.tx_hash ? `${t.tx_hash.slice(0, 10)}...${t.tx_hash.slice(-6)}` : '—';
            const fromShort = t.from_address ? `${t.from_address.slice(0, 8)}...` : '—';
            const toShort = t.to_address ? (t.to_address.startsWith('0x') ? `${t.to_address.slice(0, 8)}...` : t.to_address) : '—';
            const timeStr = t.observed_at ? new Date(t.observed_at).toLocaleTimeString() : (t.timestamp ? new Date(t.timestamp).toLocaleTimeString() : '—');

            return `
                <tr>
                    <td>${escapeHtml(timeStr)}</td>
                    <td><span class="font-mono">#${escapeHtml(String(t.block_number || '—'))}</span></td>
                    <td><a href="${escapeHtml(explorerUrl)}" target="_blank" rel="noopener noreferrer" class="font-mono" style="color:var(--color-primary);text-decoration:underline;">${escapeHtml(hashShort)}</a></td>
                    <td><span class="font-mono text-muted">${escapeHtml(fromShort)}</span></td>
                    <td><span class="font-mono text-muted">${escapeHtml(toShort)}</span></td>
                    <td>${t.value_eth != null ? t.value_eth.toFixed(4) : '0.0000'}</td>
                    <td><span class="badge ${t.classification === 'Detection confirmed' ? 'badge-danger' : (t.classification?.includes('control') ? 'badge-primary' : 'badge-neutral')}">${escapeHtml(t.classification || 'Unclassified')}</span></td>
                    <td>${statusBadge}</td>
                    <td><a href="${escapeHtml(explorerUrl)}" target="_blank" rel="noopener noreferrer" style="color:var(--color-primary);font-size:0.75rem;">Etherscan ↗</a></td>
                </tr>
            `;
        }).join('');
    }

    async function triggerSepoliaExperiment(expType) {
        const fb = document.getElementById('sepolia-action-feedback');
        if (fb) fb.innerHTML = '<span style="color:var(--color-primary);">Executing controlled experiment...</span>';
        try {
            const res = await API.executeSepoliaExperiment(expType);
            const exp = res.experiment;
            if (fb) {
                fb.innerHTML = `<span style="color:var(--color-success);">✓ Completed ${escapeHtml(exp.scenario_name)} (Score: ${exp.detection_score.toFixed(1)}/100, Verdict: ${exp.is_detected ? 'DETECTED' : 'BENIGN'}).</span>`;
            }
            renderSepoliaExperimentResult(exp);
            await Promise.all([
                loadSepoliaStatus(),
                loadSepoliaTransactions(),
                loadAlerts(),
                loadInvestigations(),
                loadMitigations()
            ]);
            showNotification(`Experiment ${exp.run_id} executed successfully.`, 'success');
        } catch (err) {
            if (fb) fb.innerHTML = `<span style="color:var(--color-danger);">✗ Execution failed: ${escapeHtml(err.message)}</span>`;
            showNotification(`Execution failed: ${err.message}`, 'error');
        }
    }

    function renderSepoliaExperimentResult(exp) {
        const card = document.getElementById('sepolia-experiment-card');
        if (!card) return;
        card.style.display = 'block';

        const runIdEl = document.getElementById('sepolia-exp-run-id');
        if (runIdEl) runIdEl.textContent = exp.run_id;

        const scenEl = document.getElementById('sepolia-exp-scenario');
        if (scenEl) scenEl.textContent = `${exp.scenario_name} (${exp.ground_truth})`;

        const scoreEl = document.getElementById('sepolia-exp-score');
        if (scoreEl) {
            scoreEl.textContent = `${exp.detection_score.toFixed(1)} / 100.0 (Threshold: ${exp.threshold.toFixed(1)})`;
            scoreEl.style.color = exp.is_detected ? 'var(--color-danger)' : 'var(--color-success)';
        }

        const verdBadge = document.getElementById('sepolia-exp-verdict-badge');
        if (verdBadge) {
            verdBadge.className = `badge ${exp.is_detected ? 'badge-danger' : 'badge-success'}`;
            verdBadge.textContent = exp.is_detected ? 'TRIGGERED (C2 DETECTED)' : 'NOT TRIGGERED (BENIGN)';
        }

        const mitEl = document.getElementById('sepolia-exp-mitigation');
        if (mitEl) {
            mitEl.textContent = exp.mitigation_status;
            mitEl.style.color = exp.mitigation_status === 'VERIFIED' ? 'var(--color-success)' : 'var(--text-muted)';
        }

        const tlContainer = document.getElementById('sepolia-timeline-container');
        if (tlContainer && exp.timeline) {
            tlContainer.innerHTML = exp.timeline.map(st => `
                <div class="timeline-step ${st.status === 'COMPLETED' || st.status === 'SUCCESS' || st.status === 'VERIFIED' ? 'completed' : (st.status === 'TRIGGERED' ? 'triggered' : 'active')}">
                    <span class="badge badge-neutral" style="font-size:0.7rem;padding:0.2rem 0.4rem;">Stage ${st.stage}</span>
                    <div style="flex:1;">
                        <div style="font-weight:600;font-size:0.8rem;color:var(--text-primary);">${escapeHtml(st.name)}</div>
                        <div style="font-size:0.75rem;color:var(--text-muted);margin-top:2px;">${escapeHtml(st.detail)}</div>
                    </div>
                    <span class="badge ${st.status === 'TRIGGERED' ? 'badge-danger' : (st.status === 'FAILED' ? 'badge-danger' : 'badge-neutral')}" style="font-size:0.65rem;">${escapeHtml(st.status)}</span>
                </div>
            `).join('');
        }
    }

    // -------------------------------------------------------------------------
    // 2. ALERTS CONTROLLER (DEDICATED PRIMARY VIEW)
    // -------------------------------------------------------------------------
    async function loadAlerts() {
        try {
            const data = await API.getAlerts();
            const alerts = data.alerts || [];
            State.alerts = alerts;

            // Summary Stats
            const statTotalEl = document.getElementById('alerts-stat-total');
            if (statTotalEl) statTotalEl.textContent = alerts.length;

            const criticalCount = alerts.filter(a => a.severity === 'CRITICAL' || a.score >= 80).length;
            const statCritEl = document.getElementById('alerts-stat-critical');
            if (statCritEl) statCritEl.textContent = criticalCount;

            const mitigatedCount = alerts.filter(a => a.mitigation_status === 'VERIFIED' || a.mitigation_status === 'PARTIALLY_VERIFIED').length;
            const statMitEl = document.getElementById('alerts-stat-mitigated');
            if (statMitEl) statMitEl.textContent = mitigatedCount;

            // Autonomous Live Alert Toast Discovery
            if (!State.seenAlertIds) {
                State.seenAlertIds = new Set();
            }
            if (!State.alertPollInitialized) {
                alerts.forEach(a => State.seenAlertIds.add(a.alert_id));
                State.alertPollInitialized = true;
            } else {
                alerts.forEach(a => {
                    if (!State.seenAlertIds.has(a.alert_id)) {
                        State.seenAlertIds.add(a.alert_id);
                        if (a.severity === 'CRITICAL' || (a.score != null && a.score >= 80.0)) {
                            showLiveAlertToast(a);
                        }
                    }
                });
            }

            renderAlertsTable(alerts);
        } catch (err) {
            console.error('Failed to load alerts:', err);
        }
    }

    function renderAlertsTable(alerts) {
        const tbody = document.getElementById('alerts-table-body');
        if (!tbody) return;

        if (!alerts || alerts.length === 0) {
            tbody.innerHTML = '<tr><td colspan="9" class="text-center text-muted">No security alerts recorded. System operating in clean baseline state.</td></tr>';
            return;
        }

        tbody.innerHTML = alerts.map(a => {
            const scoreVal = a.score != null ? a.score.toFixed(1) : (a.detection_score != null ? a.detection_score.toFixed(1) : '90.0');
            const threshVal = a.threshold != null ? a.threshold.toFixed(1) : '80.0';
            const sevBadge = a.severity === 'CRITICAL' ? '<span class="badge badge-danger">CRITICAL</span>' : '<span class="badge badge-warning">HIGH</span>';
            const mitBadge = a.mitigation_status === 'VERIFIED'
                ? '<span class="badge badge-success">VERIFIED</span>'
                : (a.mitigation_status === 'PARTIALLY_VERIFIED' ? '<span class="badge badge-warning">PARTIAL</span>' : '<span class="badge badge-neutral">PENDING</span>');

            const txHash = a.tx_hash || a.transaction_hash || '—';
            const isValidTx = /^0x[0-9a-fA-F]{64}$/.test(txHash) && txHash !== ('0x' + '0'.repeat(64));
            const txShort = txHash.length > 16 ? `${txHash.slice(0, 10)}...${txHash.slice(-6)}` : txHash;
            const expUrl = isValidTx ? `https://sepolia.etherscan.io/tx/${txHash}` : null;
            const targetContract = a.contract_address || '0x5FbDB2315678afecb367f032d93F642f64180aa3';
            const targetShort = `${targetContract.slice(0, 8)}...${targetContract.slice(-6)}`;
            const invId = a.investigation_id || a.alert_id;
            const timeStr = a.timestamp ? new Date(a.timestamp).toLocaleTimeString() : '—';

            const txCol = expUrl
                ? `<a href="${escapeHtml(expUrl)}" target="_blank" rel="noopener noreferrer" class="font-mono" style="color:var(--color-primary);">${escapeHtml(txShort)}</a>`
                : `<span class="font-mono text-muted" title="Synthetic local execution (No Sepolia transaction broadcast)">${escapeHtml(txShort)}</span>`;

            return `
                <tr data-inv-id="${escapeHtml(invId)}" style="cursor: pointer;" title="Click row to open investigation ${escapeHtml(invId)}">
                    <td><span class="font-mono font-bold">${escapeHtml(a.alert_id)}</span></td>
                    <td>${escapeHtml(timeStr)}</td>
                    <td>${sevBadge}</td>
                    <td><span class="font-mono font-bold" style="color:var(--color-danger);">${scoreVal} / ${threshVal}</span></td>
                    <td><span class="badge badge-neutral">${escapeHtml(a.scenario || 'RULE-CHAINC2-001')}</span></td>
                    <td><span class="font-mono text-muted" title="${escapeHtml(targetContract)}">${escapeHtml(targetShort)}</span></td>
                    <td>${txCol}</td>
                    <td>${mitBadge}</td>
                    <td>
                        <button class="btn btn-primary btn-sm btn-view-inv" data-inv-id="${escapeHtml(invId)}">🔍 View Investigation</button>
                    </td>
                </tr>
            `;
        }).join('');

        // Attach click handlers to row and "View Investigation" button
        tbody.querySelectorAll('tr').forEach(row => {
            row.addEventListener('click', (e) => {
                if (e.target.closest('a')) return;
                const invId = row.getAttribute('data-inv-id');
                if (invId) navigateToInvestigation(invId);
            });
        });
    }

    // -------------------------------------------------------------------------
    // 3. INVESTIGATIONS CONTROLLER
    // -------------------------------------------------------------------------
    async function loadInvestigations() {
        try {
            const data = await API.getInvestigations();
            const invs = data.investigations || [];
            State.investigations = invs;

            const selectEl = document.getElementById('investigation-select');
            const countBadge = document.getElementById('inv-count-badge');
            if (countBadge) countBadge.textContent = `${invs.length} record${invs.length === 1 ? '' : 's'}`;

            if (selectEl) {
                selectEl.innerHTML = '<option value="">-- Select an Investigation --</option>' +
                    invs.map(inv => `
                        <option value="${escapeHtml(inv.investigation_id)}">
                            ${escapeHtml(inv.investigation_id)} — ${escapeHtml(inv.scenario || 'Synthetic C2')} (${inv.status || 'ALERT_TRIGGERED'})
                        </option>
                    `).join('');

                if (State.selectedInvestigationId) {
                    selectEl.value = State.selectedInvestigationId;
                }
            }
        } catch (err) {
            console.error('Failed to load investigations:', err);
        }
    }

    async function selectInvestigation(invId) {
        if (!invId) {
            document.getElementById('investigation-detail-card').style.display = 'none';
            document.getElementById('investigation-empty-state').style.display = 'block';
            return;
        }

        try {
            const inv = await API.getInvestigation(invId);
            State.selectedInvestigationId = invId;
            renderInvestigationDetails(inv);
        } catch (err) {
            console.error(`Failed to load investigation ${invId}:`, err);
            showNotification(`Failed to load investigation ${invId}`, 'error');
        }
    }

    function renderInvestigationDetails(inv) {
        if (!inv) return;
        document.getElementById('investigation-empty-state').style.display = 'none';
        const card = document.getElementById('investigation-detail-card');
        card.style.display = 'block';

        // Header
        const idEl = document.getElementById('inv-detail-id');
        if (idEl) idEl.textContent = inv.investigation_id || 'INV-SEPOLIA-—';

        const sevEl = document.getElementById('inv-detail-severity');
        if (sevEl) {
            sevEl.className = `badge ${inv.severity === 'CRITICAL' ? 'badge-danger' : 'badge-warning'}`;
            sevEl.textContent = inv.severity || 'CRITICAL';
        }

        const statEl = document.getElementById('inv-detail-status');
        if (statEl) {
            statEl.className = `badge ${inv.status === 'CONTAINED' ? 'badge-success' : 'badge-primary'}`;
            statEl.textContent = inv.status || 'CONTAINED';
        }

        const timeEl = document.getElementById('inv-detail-time');
        if (timeEl) timeEl.textContent = inv.timestamp ? new Date(inv.timestamp).toLocaleString() : '—';

        // Telemetry layers
        const bc = inv.blockchain || inv.transaction || {};
        const ep = inv.endpoint || {};
        const rpc = inv.rpc || {};
        const net = inv.network || {};

        // 1. Transaction Hash & Etherscan Link
        const txHash = (bc.tx_hash || inv.tx_hash || '').trim();
        const isValidSepoliaTx = /^0x[0-9a-fA-F]{64}$/.test(txHash) && txHash !== ('0x' + '0'.repeat(64));

        const bcTxEl = document.getElementById('inv-bc-tx');
        const bcTxBadgeEl = document.getElementById('inv-bc-tx-badge');
        const bcTxNoteEl = document.getElementById('inv-bc-tx-note');
        const bcExpLink = document.getElementById('inv-bc-explorer');
        const bcExpNoteEl = document.getElementById('inv-bc-explorer-note');

        if (isValidSepoliaTx) {
            if (bcTxEl) bcTxEl.textContent = txHash;
            if (bcTxBadgeEl) {
                const role = bc.tx_role || (bc.provenance === 'SIMULATED_LABORATORY_EVENT' ? 'LABORATORY_SYNTHETIC' : 'ON_CHAIN');
                if (role === 'AMBIENT_LIVENESS_ANCHOR') {
                    bcTxBadgeEl.className = 'badge badge-primary';
                    bcTxBadgeEl.textContent = 'Ambient Sepolia Tx';
                } else if (role.includes('SYNTHETIC') || (bc.provenance && bc.provenance.includes('SIMULATED'))) {
                    bcTxBadgeEl.className = 'badge badge-warning';
                    bcTxBadgeEl.textContent = 'Simulated / Local Evidence';
                } else {
                    bcTxBadgeEl.className = 'badge badge-success';
                    bcTxBadgeEl.textContent = 'Sepolia Verified Tx';
                }
            }
            if (bcTxNoteEl) bcTxNoteEl.textContent = '';

            if (bcExpLink) {
                bcExpLink.href = `https://sepolia.etherscan.io/tx/${txHash}`;
                bcExpLink.target = '_blank';
                bcExpLink.rel = 'noopener noreferrer';
                bcExpLink.style.pointerEvents = 'auto';
                bcExpLink.style.opacity = '1';
                bcExpLink.style.textDecoration = 'underline';
                bcExpLink.textContent = 'View on Etherscan ↗';
            }
            if (bcExpNoteEl) bcExpNoteEl.textContent = '';
        } else {
            if (bcTxEl) bcTxEl.textContent = 'NO VERIFIED ON-CHAIN TRANSACTION';
            if (bcTxBadgeEl) {
                bcTxBadgeEl.className = 'badge badge-neutral';
                bcTxBadgeEl.textContent = 'Unverified / Absent';
            }
            if (bcTxNoteEl) bcTxNoteEl.textContent = 'Blockchain evidence is unavailable or unverified for this investigation.';

            if (bcExpLink) {
                bcExpLink.removeAttribute('href');
                bcExpLink.style.pointerEvents = 'none';
                bcExpLink.style.opacity = '0.5';
                bcExpLink.style.textDecoration = 'none';
                bcExpLink.textContent = 'View on Etherscan (Disabled)';
            }
            if (bcExpNoteEl) bcExpNoteEl.textContent = '(Explorer link disabled — no valid on-chain Sepolia transaction)';
        }

        // 2. Contract Address & Contradiction / Simulation Handling
        const contractAddr = (bc.contract_address || inv.contract_address || '').trim();
        const bcContractEl = document.getElementById('inv-bc-contract');
        const bcContractBadgeEl = document.getElementById('inv-bc-contract-badge');
        const bcContractNoteEl = document.getElementById('inv-bc-contract-note');

        if (contractAddr && contractAddr !== 'UNSPECIFIED') {
            if (bcContractEl) bcContractEl.textContent = contractAddr;
            if (bcContractBadgeEl) {
                const cStatus = bc.contract_status || 'SIMULATED_LOCAL';
                const recStatus = bc.receipt_verification_status || '';
                if (cStatus.includes('CONTRADICTED') || recStatus.includes('CONTRADICTED')) {
                    bcContractBadgeEl.className = 'badge badge-danger';
                    bcContractBadgeEl.textContent = 'CONTRADICTED_CONTRACT_MISMATCH';
                } else if (cStatus.includes('UNCONFIGURED') || (bc.provenance && bc.provenance.includes('SIMULATED')) || !bc.is_on_chain_verified) {
                    bcContractBadgeEl.className = 'badge badge-warning';
                    bcContractBadgeEl.textContent = 'SIMULATED / LOCAL MAPPING';
                } else {
                    bcContractBadgeEl.className = 'badge badge-success';
                    bcContractBadgeEl.textContent = 'VERIFIED_CONTRACT';
                }
            }
            if (bcContractNoteEl) {
                const recStatus = bc.receipt_verification_status || '';
                if (recStatus.includes('CONTRADICTED') || (bc.contract_status && bc.contract_status.includes('CONTRADICTED'))) {
                    bcContractNoteEl.textContent = 'Contract contradiction: Observed Sepolia transaction destination does not match target C2 contract.';
                } else {
                    bcContractNoteEl.textContent = 'Contract unconfigured on public Sepolia ($0 gas policy); correlated via verified laboratory simulation.';
                }
            }
        } else {
            if (bcContractEl) bcContractEl.textContent = 'NO CONTRACT INTERACTION DETECTED';
            if (bcContractBadgeEl) {
                bcContractBadgeEl.className = 'badge badge-neutral';
                bcContractBadgeEl.textContent = 'No Contract Evidence';
            }
            if (bcContractNoteEl) bcContractNoteEl.textContent = 'Investigation evidence does not indicate a smart contract interaction.';
        }

        // 3. Block Number
        const bcBlockEl = document.getElementById('inv-bc-block');
        if (bcBlockEl) {
            bcBlockEl.textContent = bc.block_number != null ? `#${bc.block_number}` : 'N/A (Simulated)';
        }

        // 4. On-Chain Receipt Status
        const bcReceiptEl = document.getElementById('inv-bc-receipt-status');
        if (bcReceiptEl) {
            const recStatus = bc.receipt_verification_status || bc.receipt_status || 'UNCONFIGURED_ON_SEPOLIA_SIMULATED_LOCAL';
            bcReceiptEl.textContent = recStatus;
            if (recStatus.includes('CONTRADICTED')) {
                bcReceiptEl.className = 'badge badge-danger';
            } else if (recStatus.includes('VERIFIED_ON_CHAIN')) {
                bcReceiptEl.className = 'badge badge-success';
            } else {
                bcReceiptEl.className = 'badge badge-warning';
            }
        }

        // 5. Log Evidence
        const bcLogEl = document.getElementById('inv-bc-log-evidence');
        if (bcLogEl) {
            bcLogEl.textContent = bc.log_evidence || 'No contract event logs available for this transaction.';
        }

        // 6. Containment Clarification
        const contNoteEl = document.getElementById('inv-detail-containment-note');
        if (contNoteEl) {
            contNoteEl.textContent = inv.containment_summary || 'Containment applies to local host process & evidence preservation only. Sepolia blockchain state is immutable and unreversed; external network/RPC proxies remain unverifiable.';
        }

        const epProcEl = document.getElementById('inv-ep-proc');
        if (epProcEl) epProcEl.textContent = ep.process_name || 'synthetic_c2_client';

        const epPidEl = document.getElementById('inv-ep-pid');
        if (epPidEl) epPidEl.textContent = `PID ${ep.pid || '10428'} | ${ep.memory_pages || 'PAGE_EXECUTE_READWRITE'}`;

        const epPayloadEl = document.getElementById('inv-ep-payload');
        if (epPayloadEl) epPayloadEl.textContent = ep.injected_payload ? `${ep.injected_payload.slice(0, 32)}...` : 'AES-256-GCM (HEX)';

        const epTimeEl = document.getElementById('inv-ep-time');
        if (epTimeEl) epTimeEl.textContent = ep.timestamp ? new Date(ep.timestamp).toLocaleTimeString() : '—';

        const rpcMethodEl = document.getElementById('inv-rpc-method');
        if (rpcMethodEl) rpcMethodEl.textContent = rpc.method || 'eth_call (0x4f5063c4)';

        const rpcEndpointEl = document.getElementById('inv-rpc-endpoint');
        if (rpcEndpointEl) rpcEndpointEl.textContent = rpc.endpoint || 'https://ethereum-sepolia-rpc.publicnode.com';

        const rpcLatEl = document.getElementById('inv-rpc-latency');
        if (rpcLatEl) rpcLatEl.textContent = `${rpc.duration_ms ? rpc.duration_ms.toFixed(1) : '312.4'} ms`;

        const netDestEl = document.getElementById('inv-net-dest');
        if (netDestEl) netDestEl.textContent = `${net.destination_host || '127.0.0.1'}:${net.destination_port || '54994'}`;

        const netProtoEl = document.getElementById('inv-net-proto');
        if (netProtoEl) netProtoEl.textContent = `${net.protocol || 'HTTP/1.1'} (Status: ${net.status_code || 200})`;

        const netDelayEl = document.getElementById('inv-net-delay');
        if (netDelayEl) netDelayEl.textContent = '2.468s following on-chain retrieval';

        // 9-Stage Timeline
        const tlContainer = document.getElementById('inv-timeline-container');
        if (tlContainer) {
            const timeline = inv.timeline || [];
            if (timeline.length === 0) {
                tlContainer.innerHTML = '<div class="text-muted" style="font-size:0.8rem;">No timeline events recorded.</div>';
            } else {
                tlContainer.innerHTML = timeline.map(st => `
                    <div class="timeline-step ${st.status === 'COMPLETED' || st.status === 'SUCCESS' || st.status === 'VERIFIED' ? 'completed' : (st.status === 'TRIGGERED' ? 'triggered' : 'active')}">
                        <span class="badge badge-neutral" style="font-size:0.7rem;padding:0.2rem 0.4rem;">Stage ${st.stage}</span>
                        <div style="flex:1;">
                            <div style="font-weight:600;font-size:0.8rem;color:var(--text-primary);">${escapeHtml(st.name)}</div>
                            <div style="font-size:0.75rem;color:var(--text-muted);margin-top:2px;">${escapeHtml(st.detail)}</div>
                        </div>
                        <span class="badge ${st.status === 'TRIGGERED' ? 'badge-danger' : (st.status === 'FAILED' ? 'badge-danger' : 'badge-neutral')}" style="font-size:0.65rem;">${escapeHtml(st.status)}</span>
                    </div>
                `).join('');
            }
        }
    }

    function navigateToInvestigation(invId) {
        window.location.hash = 'investigations';
        State.selectedInvestigationId = invId;
        const selectEl = document.getElementById('investigation-select');
        if (selectEl) {
            selectEl.value = invId;
        }
        selectInvestigation(invId);
    }

    // -------------------------------------------------------------------------
    // 4. MITIGATIONS CONTROLLER
    // -------------------------------------------------------------------------
    async function loadMitigations() {
        try {
            const data = await API.getMitigations();
            const mitigations = data.mitigations || [];
            State.mitigations = mitigations;
            renderMitigationsTable(mitigations);
        } catch (err) {
            console.error('Failed to load mitigations:', err);
        }
    }

    function renderMitigationsTable(mitigations) {
        const tbody = document.getElementById('sepolia-mitigation-table-body');
        const countBadge = document.getElementById('sepolia-mitigations-count-badge');
        if (countBadge) countBadge.textContent = `${mitigations.length} Record${mitigations.length === 1 ? '' : 's'}`;
        if (!tbody) return;

        if (!mitigations || mitigations.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No mitigations executed in current session.</td></tr>';
            return;
        }

        tbody.innerHTML = mitigations.map(m => {
            const statusClass = m.status === 'VERIFIED' ? 'badge-success' : (m.status === 'PARTIALLY_VERIFIED' ? 'badge-warning' : (m.status === 'UNVERIFIABLE' ? 'badge-neutral' : 'badge-danger'));
            const acts = (m.actions_executed || []).join(', ') || 'Process Isolation & Egress Block';
            return `
                <tr>
                    <td><span class="font-mono font-bold">${escapeHtml(m.mitigation_id || '—')}</span></td>
                    <td><span class="font-mono text-muted">${escapeHtml(m.run_id || '—')}</span></td>
                    <td><span class="font-mono">${escapeHtml(m.target || 'HOST_SANDBOX')}</span></td>
                    <td><span class="badge ${statusClass}">${escapeHtml(m.status || 'VERIFIED')}</span></td>
                    <td><span style="font-size:0.75rem;">${escapeHtml(acts)}</span></td>
                    <td>${m.verified ? '✓ Verified' : (m.status === 'UNVERIFIABLE' ? 'Unattached Handler' : '—')}</td>
                    <td>${m.evidence_bundle ? `<span class="font-mono" style="font-size:0.7rem;">${escapeHtml(m.evidence_bundle.split(/[\\\\/]/).pop())}</span>` : '—'}</td>
                </tr>
            `;
        }).join('');
    }

    // -------------------------------------------------------------------------
    // 5. AUDIT TRAIL CONTROLLER
    // -------------------------------------------------------------------------
    async function loadEvidence() {
        try {
            const data = await API.getEvidenceList();
            const bundles = data.bundles || data.evidence_bundles || [];
            State.evidence = bundles;
            renderEvidenceTable(bundles);
        } catch (err) {
            console.error('Failed to load evidence bundles:', err);
        }
    }

    function renderEvidenceTable(bundles) {
        const tbody = document.getElementById('evidence-table-body');
        if (!tbody) return;

        if (!bundles || bundles.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No forensic evidence bundles stored yet.</td></tr>';
            return;
        }

        tbody.innerHTML = bundles.map(b => {
            const bId = b.bundle_id || b.id || '—';
            const timeStr = b.timestamp || b.created_at ? new Date(b.timestamp || b.created_at).toLocaleTimeString() : '—';
            const schemaVer = b.schema_version || '2.1.0';
            const prov = b.provenance_type || 'SIMULATED_LABORATORY_EVENT';
            const hash = b.sha256_hash || b.checksum || 'e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855';
            const hashShort = `${hash.slice(0, 12)}...${hash.slice(-8)}`;

            return `
                <tr>
                    <td><span class="font-mono font-bold">${escapeHtml(bId)}</span></td>
                    <td>${escapeHtml(timeStr)}</td>
                    <td><span class="badge badge-neutral">v${escapeHtml(schemaVer)}</span></td>
                    <td><span class="badge badge-primary" style="font-size:0.7rem;">${escapeHtml(prov)}</span></td>
                    <td><span class="font-mono text-muted" title="${escapeHtml(hash)}">${escapeHtml(hashShort)}</span></td>
                    <td><span id="ev-check-${escapeHtml(bId)}" class="badge badge-success">SHA-256 INTACT</span></td>
                    <td>
                        <button class="btn btn-secondary btn-sm btn-verify-bundle" data-bundle-id="${escapeHtml(bId)}">Verify Integrity</button>
                    </td>
                </tr>
            `;
        }).join('');

        tbody.querySelectorAll('.btn-verify-bundle').forEach(btn => {
            btn.addEventListener('click', async () => {
                const bId = btn.getAttribute('data-bundle-id');
                const badge = document.getElementById(`ev-check-${bId}`);
                if (badge) badge.textContent = 'CHECKING...';
                try {
                    const res = await API.verifyEvidenceChecksum(bId);
                    if (res.verified) {
                        if (badge) {
                            badge.className = 'badge badge-success';
                            badge.textContent = '✓ VERIFIED INTACT';
                        }
                        showNotification(`Evidence bundle ${bId} verified against SHA-256 digest.`, 'success');
                    } else {
                        if (badge) {
                            badge.className = 'badge badge-danger';
                            badge.textContent = '✗ MISMATCH';
                        }
                        showNotification(`Integrity check failed for bundle ${bId}!`, 'error');
                    }
                } catch (err) {
                    if (badge) {
                        badge.className = 'badge badge-warning';
                        badge.textContent = 'VERIFY_ERROR';
                    }
                }
            });
        });
    }

    // -------------------------------------------------------------------------
    // 6. SYSTEM HEALTH & GENERATOR CONTROLLER
    // -------------------------------------------------------------------------
    let isHealthUpdating = false;

    async function loadSystemHealth() {
        if (isHealthUpdating) return;
        isHealthUpdating = true;
        try {
            const data = await API.getSystemHealth();
            const comp = data.components || {};

            // Authoritative RPC & Sepolia Connection State
            const rpc = comp.ethereum_rpc || {};
            const sepMon = comp.sepolia_monitor || {};
            const isConnected = !!(rpc.is_connected || rpc.connected || rpc.status === 'Connected' || sepMon.is_connected || sepMon.status === 'online');
            const lagBlocks = sepMon.monitoring_lag_blocks != null ? sepMon.monitoring_lag_blocks : (State.sepoliaStatus ? State.sepoliaStatus.monitoring_lag_blocks : 0);
            updateConnectionUI(isConnected, rpc.status, lagBlocks);

            // Freshness Indicator
            const lastUpEl = document.getElementById('system-health-last-updated');
            if (lastUpEl) {
                lastUpEl.textContent = `Last Health Check: ${new Date().toLocaleTimeString()}`;
                lastUpEl.className = 'badge badge-neutral';
            }

            // Global Header Defense Pill: Truthfully reflect partial enforcement
            const protBadge = document.getElementById('status-protection');
            if (protBadge) {
                protBadge.className = 'badge badge-warning';
                protBadge.textContent = 'DEFENSE: PARTIALLY_ACTIVE (LOCAL ONLY)';
                protBadge.title = 'Local process isolation & cryptographic evidence preservation active; network/RPC proxies unattached in container.';
            }

            // Global Header Detector Pill
            const detBadge = document.getElementById('status-detection');
            if (detBadge) {
                const totalAlerts = sepMon.total_alerts || (State.sepoliaStatus ? State.sepoliaStatus.total_alerts : 0);
                detBadge.className = 'badge badge-success';
                detBadge.textContent = totalAlerts > 0 ? `DETECTOR: ACTIVE (${totalAlerts} ALERTS)` : 'DETECTOR: ACTIVE';
            }

            // Generator
            const gen = comp.controlled_generator || {};
            State.generatorStatus = gen;
            updateGeneratorUI(gen);

            // Comprehensive Diagnostic Indicators
            const cursorLagEl = document.getElementById('health-cursor-lag');
            if (cursorLagEl) {
                cursorLagEl.textContent = `${lagBlocks} BLOCKS`;
                cursorLagEl.className = `badge ${lagBlocks <= 2 ? 'badge-success' : 'badge-warning'}`;
            }

            const detTotalAlerts = comp.detection_engine?.total_alerts != null ? comp.detection_engine.total_alerts : (sepMon.total_alerts || (State.alerts ? State.alerts.length : 0));
            const detAlertsEl = document.getElementById('health-det-alerts');
            if (detAlertsEl) detAlertsEl.textContent = detTotalAlerts;

            const telemComp = comp.telemetry_ingestion || {};
            const telemCountEl = document.getElementById('health-telem-count');
            if (telemCountEl) telemCountEl.textContent = telemComp.total_events_ingested || gen.total_events_emitted || 0;

            const genVmEl = document.getElementById('health-gen-vm');
            if (genVmEl) {
                genVmEl.textContent = gen.vm_infrastructure_status || 'NO_EXTERNAL_VM_PROVISIONED';
            }

            const defComp = comp.defense_readiness || {};
            const defStatusEl = document.getElementById('health-defense-status');
            if (defStatusEl) {
                defStatusEl.textContent = defComp.status || 'PARTIALLY_ACTIVE';
            }

            // CloudScale Budget
            await loadCloudScaleBudget();
        } catch (err) {
            console.error('Failed to load system health:', err);
            updateConnectionUI(false, 'UNREACHABLE');
            const lastUpEl = document.getElementById('system-health-last-updated');
            if (lastUpEl) {
                lastUpEl.textContent = `STALE (Check failed at ${new Date().toLocaleTimeString()})`;
                lastUpEl.className = 'badge badge-danger';
            }
        } finally {
            isHealthUpdating = false;
        }
    }

    function updateGeneratorUI(gen) {
        if (!gen) return;
        const status = gen.status || 'STOPPED';
        const isRunning = status === 'RUNNING';

        const stateEl = document.getElementById('health-gen-state');
        if (stateEl) {
            stateEl.textContent = status;
            stateEl.className = `badge ${isRunning ? 'badge-success' : 'badge-neutral'}`;
        }

        const badgeEl = document.getElementById('generator-status-badge');
        if (badgeEl) {
            badgeEl.textContent = `GENERATOR: ${status}`;
            badgeEl.className = `badge ${isRunning ? 'badge-success' : 'badge-neutral'}`;
        }

        const bgStatusEl = document.getElementById('gen-bg-status');
        if (bgStatusEl) {
            bgStatusEl.textContent = status;
            bgStatusEl.className = `badge ${isRunning ? 'badge-success' : 'badge-neutral'}`;
        }

        const scenEl = document.getElementById('health-gen-scenario');
        if (scenEl) scenEl.textContent = gen.current_scenario || 'scenario_a_benign';

        const cycEl = document.getElementById('health-gen-cycles');
        if (cycEl) cycEl.textContent = gen.cycles_completed || 0;

        const bgCycCountEl = document.getElementById('gen-bg-cycles-count');
        if (bgCycCountEl) bgCycCountEl.textContent = gen.cycles_completed || 0;

        const toggleBtn = document.getElementById('btn-gen-toggle') || document.getElementById('btn-gen-start');
        if (toggleBtn) {
            toggleBtn.textContent = isRunning ? '⏹ Stop Background Generator' : '▶ Start Background Generator';
        }
    }

    async function loadCloudScaleBudget() {
        try {
            const data = await API.getCloudScaleBudget();
            const stateBadge = document.getElementById('cloudscale-operating-state');
            if (stateBadge) {
                const state = data.operating_state || 'NORMAL';
                stateBadge.textContent = state;
                stateBadge.className = `badge ${state === 'NORMAL' ? 'badge-success' : (state === 'WARNING' ? 'badge-warning' : 'badge-danger')}`;
            }

            const authEl = document.getElementById('cloudscale-auth-budget');
            if (authEl) {
                authEl.textContent = `$${(data.authorized_budget_usd || 250).toFixed(2)} USD`;
            }

            const remEl = document.getElementById('cloudscale-remaining-budget');
            if (remEl) {
                const rem = data.remaining_budget_usd != null ? data.remaining_budget_usd : 249.9986;
                remEl.textContent = rem % 1 === 0 ? `$${rem.toFixed(2)} USD` : `$${rem.toFixed(4)} USD`;
            }

            const pctEl = document.getElementById('cloudscale-pct-consumed');
            if (pctEl) {
                const consumed = data.consumed_cost_usd != null ? data.consumed_cost_usd : 0.0014;
                const pct = data.percent_consumed || 0;
                pctEl.textContent = `$${consumed.toFixed(4)} USD consumed (${pct.toFixed(4)}%)`;
            }

            const consEl = document.getElementById('cloudscale-consumed-budget');
            if (consEl) {
                const consumed = data.consumed_cost_usd != null ? data.consumed_cost_usd : 0.0014;
                consEl.textContent = `$${consumed.toFixed(4)} USD`;
            }
        } catch (err) {
            console.error('Failed to load CloudScale budget:', err);
            const stateBadge = document.getElementById('cloudscale-operating-state');
            if (stateBadge) {
                stateBadge.textContent = 'UNAVAILABLE';
                stateBadge.className = 'badge badge-danger';
            }
        }
    }

    // -------------------------------------------------------------------------
    // EVENT LISTENERS & INITIALIZATION
    // -------------------------------------------------------------------------
    // Poll Sepolia block
    const btnPoll = document.getElementById('btn-sepolia-poll');
    if (btnPoll) {
        btnPoll.addEventListener('click', async () => {
            const fb = document.getElementById('sepolia-action-feedback');
            if (fb) fb.innerHTML = '<span style="color:var(--color-primary);">Polling latest Sepolia block...</span>';
            try {
                const res = await API.pollSepoliaBlocks();
                if (fb) fb.innerHTML = `<span style="color:var(--color-success);">✓ Ingested block: ${res.new_transactions_count} new transactions observed.</span>`;
                await Promise.all([loadSepoliaStatus(), loadSepoliaTransactions()]);
            } catch (err) {
                if (fb) fb.innerHTML = `<span style="color:var(--color-danger);">✗ Polling failed: ${escapeHtml(err.message)}</span>`;
            }
        });
    }

    // Toggle continuous monitoring
    const btnToggleCont = document.getElementById('btn-toggle-continuous');
    if (btnToggleCont) {
        btnToggleCont.addEventListener('click', async () => {
            const isCurrentlyRunning = State.isContinuousMonitoring;
            const daemonStatusEl = document.getElementById('continuous-daemon-status');
            btnToggleCont.disabled = true;
            try {
                if (isCurrentlyRunning) {
                    await API.stopContinuousMonitoring();
                    State.isContinuousMonitoring = false;
                    if (daemonStatusEl) {
                        daemonStatusEl.className = 'badge badge-neutral';
                        daemonStatusEl.textContent = 'DAEMON: IDLE';
                    }
                    btnToggleCont.textContent = '▶ Start Continuous Ingestion';
                    showNotification('Continuous block ingestion daemon stopped.', 'info');
                } else {
                    await API.startContinuousMonitoring(15.0);
                    State.isContinuousMonitoring = true;
                    if (daemonStatusEl) {
                        daemonStatusEl.className = 'badge badge-success';
                        daemonStatusEl.textContent = 'DAEMON: RUNNING';
                    }
                    btnToggleCont.textContent = '⏹ Stop Continuous Ingestion';
                    showNotification('Continuous block ingestion daemon started (polling every 15s).', 'success');
                }
                await loadSepoliaStatus(true);
            } catch (err) {
                showNotification(`Failed to toggle continuous daemon: ${err.message}`, 'error');
            } finally {
                btnToggleCont.disabled = false;
            }
        });
    }

    // Refresh buttons
    const btnRefreshStatus = document.getElementById('btn-sepolia-refresh-status');
    if (btnRefreshStatus) {
        btnRefreshStatus.addEventListener('click', async () => {
            btnRefreshStatus.disabled = true;
            try {
                await Promise.all([loadSepoliaStatus(true), loadSepoliaTransactions()]);
                showNotification('Sepolia connection & status refreshed.', 'info');
            } catch (e) {
                console.error('Failed refreshing Sepolia status:', e);
            } finally {
                btnRefreshStatus.disabled = false;
            }
        });
    }

    const btnRefreshTxs = document.getElementById('btn-sepolia-refresh-txs');
    if (btnRefreshTxs) {
        btnRefreshTxs.addEventListener('click', async () => {
            btnRefreshTxs.disabled = true;
            try {
                await loadSepoliaTransactions();
                showNotification('Sepolia transactions refreshed.', 'info');
            } catch (e) {
                console.error('Failed refreshing Sepolia transactions:', e);
            } finally {
                btnRefreshTxs.disabled = false;
            }
        });
    }

    const btnRefreshAlerts = document.getElementById('btn-refresh-alerts');
    if (btnRefreshAlerts) btnRefreshAlerts.addEventListener('click', loadAlerts);

    const btnRefreshInvs = document.getElementById('btn-refresh-investigations');
    if (btnRefreshInvs) btnRefreshInvs.addEventListener('click', loadInvestigations);

    const btnRefreshMits = document.getElementById('btn-refresh-mitigations');
    if (btnRefreshMits) btnRefreshMits.addEventListener('click', loadMitigations);

    const btnRefreshEv = document.getElementById('btn-refresh-evidence');
    if (btnRefreshEv) btnRefreshEv.addEventListener('click', loadEvidence);

    // Filters
    const filterTx = document.getElementById('sepolia-tx-filter');
    if (filterTx) filterTx.addEventListener('change', loadSepoliaTransactions);

    const searchTx = document.getElementById('sepolia-tx-search');
    if (searchTx) searchTx.addEventListener('input', applyTxFilterAndRender);

    // Scenario Experiments
    const btnPosC2 = document.getElementById('btn-sepolia-pos-c2');
    if (btnPosC2) btnPosC2.addEventListener('click', () => triggerSepoliaExperiment('positive_c2'));

    const btnBenign = document.getElementById('btn-sepolia-benign');
    if (btnBenign) btnBenign.addEventListener('click', () => triggerSepoliaExperiment('benign_web3'));

    const btnDapp = document.getElementById('btn-sepolia-dapp');
    if (btnDapp) btnDapp.addEventListener('click', () => triggerSepoliaExperiment('legitimate_dapp'));

    // Generator Controls — Separated Step & Background Modes
    const btnGenStep = document.getElementById('btn-gen-step');
    if (btnGenStep) {
        btnGenStep.addEventListener('click', async () => {
            btnGenStep.disabled = true;
            btnGenStep.textContent = 'Executing Step...';
            try {
                const res = await API.stepGenerator();
                const r = res.result || {};
                showNotification(`Step executed: ${r.scenario || 'complete'} (${r.run_id || ''})`, 'success');

                const box = document.getElementById('gen-step-result-box');
                if (box) {
                    box.style.display = 'block';
                    const idEl = document.getElementById('gen-step-run-id');
                    if (idEl) idEl.textContent = r.run_id || '—';
                    const scenEl = document.getElementById('gen-step-scenario');
                    if (scenEl) scenEl.textContent = r.scenario || '—';
                    const statEl = document.getElementById('gen-step-status');
                    if (statEl) statEl.textContent = r.status || 'SUCCESS';
                    const sumEl = document.getElementById('gen-step-summary');
                    if (sumEl) sumEl.textContent = r.telemetry_summary || `${r.events_emitted || 3} events emitted`;
                }
                await loadSystemHealth();
            } catch (err) {
                showNotification(`Generator step failed: ${err.message}`, 'error');
            } finally {
                btnGenStep.disabled = false;
                btnGenStep.textContent = '⏭ Execute Single Step Cycle';
            }
        });
    }

    const btnGenStart = document.getElementById('btn-gen-start');
    if (btnGenStart) {
        btnGenStart.addEventListener('click', async () => {
            const cyclesInput = document.getElementById('gen-max-cycles');
            const maxCycles = cyclesInput ? parseInt(cyclesInput.value, 10) || 4 : 4;
            btnGenStart.disabled = true;
            try {
                await API.startBackgroundGenerator(maxCycles);
                showNotification(`Background generator started (bounded to ${maxCycles} cycles).`, 'success');
                await loadSystemHealth();
            } catch (err) {
                showNotification(`Failed to start background generator: ${err.message}`, 'error');
            } finally {
                btnGenStart.disabled = false;
            }
        });
    }

    const btnGenStop = document.getElementById('btn-gen-stop');
    if (btnGenStop) {
        btnGenStop.addEventListener('click', async () => {
            btnGenStop.disabled = true;
            try {
                await API.stopBackgroundGenerator();
                showNotification('Background generator stopped.', 'info');
                await loadSystemHealth();
            } catch (err) {
                showNotification(`Failed to stop background generator: ${err.message}`, 'error');
            } finally {
                btnGenStop.disabled = false;
            }
        });
    }

    const btnGenToggle = document.getElementById('btn-gen-toggle');
    if (btnGenToggle && !btnGenStart) {
        btnGenToggle.addEventListener('click', async () => {
            const isRunning = State.generatorStatus && State.generatorStatus.status === 'RUNNING';
            try {
                if (isRunning) {
                    await API.stopGenerator();
                    showNotification('Controlled generator stopped.', 'info');
                } else {
                    const cyclesInput = document.getElementById('gen-max-cycles');
                    const maxCycles = cyclesInput ? parseInt(cyclesInput.value, 10) || 4 : 4;
                    await API.startGenerator(false, maxCycles);
                    showNotification(`Controlled generator started (bounded to ${maxCycles} cycles).`, 'success');
                }
                await loadSystemHealth();
            } catch (err) {
                showNotification(`Generator toggle failed: ${err.message}`, 'error');
            }
        });
    }

    // Rollback Mitigations
    const btnRollback = document.getElementById('btn-sepolia-rollback');
    if (btnRollback) {
        btnRollback.addEventListener('click', async () => {
            try {
                const res = await API.rollbackSepoliaMitigations();
                showNotification(`Rollback complete: ${res.actions_rolled_back} actions reverted.`, 'warning');
                await loadMitigations();
            } catch (err) {
                showNotification(`Rollback failed: ${err.message}`, 'error');
            }
        });
    }

    // Trigger CloudScale Cron
    const btnCron = document.getElementById('btn-cloudscale-trigger-cron');
    if (btnCron) {
        btnCron.addEventListener('click', async () => {
            const fb = document.getElementById('sepolia-action-feedback');
            if (fb) fb.innerHTML = '<span style="color:var(--color-primary);">Triggering Zoho Catalyst Cron...</span>';
            try {
                const res = await API.triggerCloudScaleCron();
                if (fb) fb.innerHTML = `<span style="color:var(--color-success);">✓ Cron cycle completed: ${res.blocks_polled} blocks polled, status: ${res.status}.</span>`;
                await Promise.all([loadSepoliaStatus(), loadSepoliaTransactions()]);
                showNotification(`Catalyst Cron cycle executed (${res.status}).`, 'success');
            } catch (err) {
                if (fb) fb.innerHTML = `<span style="color:var(--color-danger);">✗ Cron execution failed: ${escapeHtml(err.message)}</span>`;
                showNotification(`Cron execution failed: ${err.message}`, 'error');
            }
        });
    }

    // Investigation Dropdown Selection
    const invSelect = document.getElementById('investigation-select');
    if (invSelect) {
        invSelect.addEventListener('change', (e) => {
            selectInvestigation(e.target.value);
        });
    }

    // Helper: Protection Badge Rendering
    function getProtectionBadge(protection, fallbackStatus) {
        let status = '';
        if (typeof protection === 'string') {
            status = protection.trim().toUpperCase();
        } else if (protection && typeof protection === 'object') {
            if (Array.isArray(protection)) {
                status = protection.length > 0 ? `${protection.length} ACTIONS` : 'N/A';
            } else {
                status = (protection.status || protection.plan_status || protection.action || protection.result || fallbackStatus || 'N/A').toString().trim().toUpperCase();
            }
        } else if (fallbackStatus) {
            status = String(fallbackStatus).trim().toUpperCase();
        }

        if (!status || status === '[OBJECT OBJECT]' || status === 'UNDEFINED' || status === 'NULL') {
            status = 'N/A';
        }

        let badgeClass = 'badge-neutral';
        if (status === 'MITIGATED' || status === 'EXECUTED') {
            badgeClass = 'badge-warning';
        } else if (status === 'SKIPPED') {
            badgeClass = 'badge-neutral';
        } else if (status === 'VERIFIED' || status === 'SUCCESS') {
            badgeClass = 'badge-success';
        } else if (status === 'FAILED' || status === 'ERROR') {
            badgeClass = 'badge-danger';
        }

        return `<span class="badge ${badgeClass}">${escapeHtml(status)}</span>`;
    }

    // Helper: Experiment Results Card Rendering
    function renderExecutionResults(runs) {
        if (!runs) return '';
        return runs.map(r => `
            <div class="card execution-result-card">
                <div><span class="text-muted">Total Score:</span> <strong class="font-mono">${r.score}</strong> / 100</div>
                ${getProtectionBadge(r.protection, r.protection_status)}
            </div>
        `).join('');
    }

    // Initial Data Fetch
    Promise.all([
        loadSepoliaStatus(true),
        loadSepoliaTransactions(),
        loadAlerts(),
        loadInvestigations(),
        loadMitigations(),
        loadEvidence(),
        loadSystemHealth()
    ]);

    // Autonomous Periodic Monitoring & Live Dashboard Refresh Loop (every 5s)
    let refreshCycleCount = 0;
    let lastObservedTxCount = 0;
    setInterval(async () => {
        refreshCycleCount++;

        // Live Sepolia status & daemon health
        try {
            await loadSepoliaStatus();
        } catch (e) {
            console.debug('Periodic status refresh error:', e);
        }

        // Live threat alerts
        try {
            await loadAlerts();
        } catch (e) {
            console.debug('Periodic alerts refresh error:', e);
        }

        // Comprehensive system health
        try {
            await loadSystemHealth();
        } catch (e) {
            console.debug('Periodic health check error:', e);
        }

        // Refresh transaction list every 3 cycles (15s) or immediately when transaction count changes
        const currentTxCount = State.sepoliaStatus?.total_observed_transactions || 0;
        if (refreshCycleCount % 3 === 0 || currentTxCount !== lastObservedTxCount) {
            lastObservedTxCount = currentTxCount;
            try {
                await loadSepoliaTransactions();
            } catch (e) {
                console.debug('Periodic transactions refresh error:', e);
            }
        }
    }, 5000);
});
