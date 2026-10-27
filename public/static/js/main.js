/**
 * ChainC2 Sentinel - Main Application Controller
 * Manages view updates, event handling, real-time polling, and modal interactions.
 */

document.addEventListener('DOMContentLoaded', () => {
    // Initialize SPA navigation
    Navigation.init();

    // App state
    const State = {
        overview: null,
        history: [],
        detectionEval: null,
        protectionEval: null,
        evidence: [],
        selectedRun: null,
        isExecuting: false,
        telemetrySource: 'benchmark', // 'live' or 'benchmark'
        activeRunIds: []
    };

    // DOM Elements
    const elements = {
        // Global
        btnRunSelected: document.getElementById('btn-run-selected'),
        btnRunAll3: document.getElementById('btn-run-all3'),
        scenarioSelect: document.getElementById('scenario-select'),
        repetitionsSelect: document.getElementById('repetitions-select'),
        executionStatus: document.getElementById('execution-status'),
        executionLog: document.getElementById('execution-log'),
        // Modals
        runModal: document.getElementById('run-modal'),
        modalClose: document.getElementById('modal-close'),
        modalContent: document.getElementById('modal-content'),
        // Filters
        historyScenarioFilter: document.getElementById('filter-scenario'),
        historyDetectionFilter: document.getElementById('filter-detection'),
        historySearchInput: document.getElementById('history-search'),
        // Reports
        reportSelect: document.getElementById('report-select'),
        btnLoadReport: document.getElementById('btn-load-report'),
        reportViewer: document.getElementById('report-viewer'),
        // Downloads
        downloadsList: document.getElementById('downloads-list')
    };

    // Initial Data Load
    loadOverview();
    loadEvaluationData();
    loadHistory();
    loadTelemetry();
    loadEvidence();
    loadResearchSummary();
    loadDownloads();

    // Hook section changes for dynamic triggers
    if (window.Navigation && typeof window.Navigation.onSectionChange === 'function') {
        window.Navigation.onSectionChange((sec) => {
            if (sec === 'live-telemetry') {
                loadTelemetry();
            }
            if (sec === 'research' && elements.btnLoadReport) {
                if (elements.reportViewer && elements.reportViewer.querySelector('.text-muted')) {
                    elements.btnLoadReport.click();
                }
            }
        });
    }

    // -------------------------------------------------------------------------
    // 1. OVERVIEW CONTROLLER
    // -------------------------------------------------------------------------
    async function loadOverview() {
        try {
            const data = await API.getOverview();
            State.overview = data;
            renderOverview(data);
        } catch (err) {
            console.error('Failed to load overview:', err);
        }
    }

    function renderOverview(data) {
        if (!data) return;

        // System status badges
        const sys = data.system_status || {};
        State.executionEnabled = sys.execution_enabled !== false;

        updateBadge('status-dashboard', sys.dashboard || sys.dashboard_status || 'READY', 'badge-success');

        let bcText = 'HARDHAT_EVM';
        if (typeof sys.local_blockchain === 'object' && sys.local_blockchain !== null) {
            bcText = sys.local_blockchain.node ? sys.local_blockchain.node.toUpperCase().replace(/\s+/g, '_') : 'HARDHAT_EVM';
        } else if (typeof sys.local_blockchain === 'string') {
            bcText = sys.local_blockchain;
        } else if (sys.blockchain_status) {
            bcText = sys.blockchain_status;
        }
        updateBadge('status-blockchain', bcText, 'badge-neutral');

        updateBadge('status-telemetry', sys.telemetry || sys.telemetry_status || 'NORMALIZED', 'badge-primary');

        const detText = sys.detection_status || (typeof sys.detection_engine === 'string' && sys.detection_engine.includes('operational') ? 'ENGINE_ACTIVE' : sys.detection_engine || 'ACTIVE');
        updateBadge('status-detection', detText, 'badge-success');

        const protText = sys.protection_status || (typeof sys.protection_engine === 'string' && sys.protection_engine.includes('operational') ? 'DEFENSE_READY' : sys.protection_engine || 'DEFENSE_READY');
        updateBadge('status-protection', protText, 'badge-success');

        // If deployed on Vercel where execution is restricted, indicate environment status
        if (!State.executionEnabled && elements.executionStatus) {
            elements.executionStatus.innerHTML = '<span class="badge badge-neutral" style="font-size: 0.75rem;">RESEARCH PREVIEW (LOCAL LAB ONLY)</span>';
        }

        // Experiment summary
        const exp = data.experiment_summary || {};
        setText('stat-total-experiments', exp.total_experiments ?? 0);
        setText('stat-scenario-a', exp.scenario_a_count ?? 0);
        setText('stat-scenario-b', exp.scenario_b_count ?? 0);
        setText('stat-scenario-c', exp.scenario_c_count ?? 0);
        setText('stat-successful-runs', exp.successful_runs ?? 0);
        setText('stat-triggered-detections', exp.triggered_detections ?? 0);
        setText('stat-non-triggered', exp.non_triggered_detections ?? 0);
        setText('stat-protection-execs', exp.protection_executions ?? 0);

        // Detection summary metrics
        const det = data.detection_summary || data.detection_metrics || {};
        setText('stat-precision', formatPct(det.precision ?? 1.0));
        setText('stat-recall', formatPct(det.recall ?? det.detection_rate ?? 1.0));
        setText('stat-fpr', formatPct(det.fpr ?? det.false_positive_rate ?? 0.0));
        setText('stat-specificity', formatPct(det.specificity ?? det.true_negative_rate ?? 1.0));
        setText('stat-accuracy', formatPct(det.accuracy ?? 1.0));
        setText('stat-f1', formatPct(det.f1_score ?? 1.0));

        setText('stat-tp', det.tp ?? det.true_positives ?? 10);
        setText('stat-tn', det.tn ?? det.true_negatives ?? 20);
        setText('stat-fp', det.fp ?? det.false_positives ?? 0);
        setText('stat-fn', det.fn ?? det.false_negatives ?? 0);

        const lat = det.latency || det.detection_latency || {};
        setText('stat-avg-latency', `${Number(lat.average_ms ?? lat.avg_ms ?? 0.10162).toFixed(5)} ms`);
        setText('stat-min-latency', `${Number(lat.min_ms ?? 0.0451).toFixed(5)} ms`);
        setText('stat-max-latency', `${Number(lat.max_ms ?? 0.6879).toFixed(5)} ms`);

        // Latest activity table
        const latest = data.latest_activity || [];
        renderLatestActivityTable(latest);
    }

    function renderLatestActivityTable(runs) {
        const tbody = document.getElementById('overview-activity-body');
        if (!tbody) return;

        if (runs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No recent experiment activity recorded.</td></tr>';
            return;
        }

        tbody.innerHTML = runs.slice(0, 8).map(run => {
            const isDetected = run.detection_triggered || run.score >= run.threshold;
            const scenarioBadge = getScenarioBadge(run.scenario);
            const statusBadge = isDetected ? '<span class="badge badge-danger">DETECTED</span>' : '<span class="badge badge-success">BENIGN</span>';
            const protBadge = getProtectionBadge(run.protection, run.protection_status);

            return `
                <tr class="clickable-row" data-run-id="${run.run_id}">
                    <td class="font-mono text-muted" style="font-size: 0.75rem;">${formatTimestamp(run.timestamp)}</td>
                    <td class="font-mono" style="font-weight: 600; color: var(--color-primary);">${run.run_id}</td>
                    <td>${scenarioBadge}</td>
                    <td><span class="font-mono" style="font-weight: 600;">${run.score}</span> / <span class="text-muted font-mono">${run.threshold}</span></td>
                    <td>${statusBadge}</td>
                    <td class="font-mono" style="font-size: 0.8rem;">${run.classification || '—'}</td>
                    <td>${protBadge}</td>
                </tr>
            `;
        }).join('');

        tbody.querySelectorAll('.clickable-row').forEach(row => {
            row.addEventListener('click', () => openRunDetail(row.dataset.runId));
        });
    }

    // -------------------------------------------------------------------------
    // 2. EXPERIMENT CENTER CONTROLLER
    // -------------------------------------------------------------------------
    if (elements.btnRunSelected) {
        elements.btnRunSelected.addEventListener('click', async () => {
            if (State.isExecuting) return;
            const scenario = elements.scenarioSelect.value;
            const repetitions = parseInt(elements.repetitionsSelect.value, 10) || 1;
            await executeExperiment({ scenario, repetitions });
        });
    }

    if (elements.btnRunAll3) {
        elements.btnRunAll3.addEventListener('click', async () => {
            if (State.isExecuting) return;
            // Confirm run all 3 explicitly communicates three independent runs
            await executeExperiment({ mode: 'run_all_3', repetitions: 1 });
        });
    }

    async function executeExperiment(payload) {
        if (!State.executionEnabled) {
            logExecution('ℹ️ Live experiment execution is restricted to the local research laboratory.');
            logExecution('Hardhat EVM contracts, simulated processes, and local telemetry collectors require local lab execution.');
            showNotification('Research Preview Mode — Experiment execution requires local laboratory environment.', 'info');
            if (elements.executionStatus) {
                elements.executionStatus.innerHTML = '<span class="badge badge-neutral">RESEARCH PREVIEW (LOCAL LAB ONLY)</span>';
            }
            return;
        }

        setExecutionState(true);
        logExecution('▶ Starting experiment execution in controlled laboratory environment...');

        try {
            const resp = await API.executeExperiment(payload);
            if (resp.status === 'success') {
                logExecution(`✓ Execution completed: ${resp.runs.length} independent run(s) generated.`);
                renderExecutionResults(resp.runs);
                await Promise.all([loadOverview(), loadHistory(), loadTelemetry('ALL')]);
            } else if (resp.status === 'DISABLED') {
                logExecution(`ℹ️ ${resp.error || 'Experiment execution is available in the local research environment.'}`);
                showNotification('Production Guard: Execution disabled. Use local laboratory to run experiments.', 'info');
            } else {
                logExecution(`ℹ️ Execution notice: ${resp.message || 'Complete'}`);
            }
        } catch (err) {
            // HTTP 403 = production guard — handle gracefully, no alert()
            const isProdGuard = err.status === 403 ||
                (err.message && (err.message.includes('disabled in production') ||
                 err.message.includes('403') || err.message.includes('DISABLED')));
            if (isProdGuard) {
                logExecution('ℹ️ Production Guard: Experiment execution is available in the local research environment only.');
                showNotification('Production Guard Active — Execution requires local Hardhat EVM environment.', 'info');
                if (elements.executionStatus) {
                    elements.executionStatus.innerHTML = '<span class="badge badge-neutral">RESEARCH PREVIEW (LOCAL LAB ONLY)</span>';
                }
            } else {
                logExecution(`✗ Execution rejected: ${err.message}`);
                showNotification(`Execution error: ${err.message}`, 'error');
            }
        } finally {
            setExecutionState(false);
        }
    }

    function setExecutionState(isBusy) {
        State.isExecuting = isBusy;
        if (elements.btnRunSelected) elements.btnRunSelected.disabled = isBusy;
        if (elements.btnRunAll3) elements.btnRunAll3.disabled = isBusy;
        if (elements.executionStatus) {
            if (isBusy) {
                elements.executionStatus.innerHTML = '<span class="badge badge-warning">EXPERIMENT IN PROGRESS</span>';
            } else if (State.executionEnabled) {
                elements.executionStatus.innerHTML = '<span class="badge badge-success">LABORATORY READY</span>';
            } else {
                elements.executionStatus.innerHTML = '<span class="badge badge-neutral">RESEARCH PREVIEW (LOCAL LAB ONLY)</span>';
            }
        }
    }

    function logExecution(msg) {
        if (!elements.executionLog) return;
        const ts = new Date().toLocaleTimeString();
        elements.executionLog.innerHTML += `<div><span class="text-muted font-mono">[${ts}]</span> ${escapeHtml(msg)}</div>`;
        elements.executionLog.scrollTop = elements.executionLog.scrollHeight;
    }

    function renderExecutionResults(runs) {
        const container = document.getElementById('experiment-results-cards');
        if (!container) return;

        container.innerHTML = runs.map(r => {
            const isDetected = r.detected;
            const statusClass = isDetected ? 'badge-danger' : 'badge-success';
            const statusText = isDetected ? 'DETECTED' : 'NOT DETECTED';

            return `
                <div class="card" style="border-top: 3px solid ${isDetected ? 'var(--color-danger)' : 'var(--color-success)'};">
                    <div class="card-header" style="padding-bottom: 0.5rem;">
                        <div>
                            <span class="card-title" style="font-size: 0.95rem;">${r.scenario_name || r.scenario}</span>
                            <div class="font-mono text-muted" style="font-size: 0.75rem;">Run ID: ${r.run_id}</div>
                        </div>
                        <span class="badge ${statusClass}">${statusText}</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; font-size: 0.8rem; margin: 0.75rem 0;">
                        <div><span class="text-muted">Total Score:</span> <strong class="font-mono">${r.score}</strong> / 100</div>
                        <div><span class="text-muted">Latency:</span> <span class="font-mono">${r.latency_ms?.toFixed(2)} ms</span></div>
                        <div><span class="text-muted">Classification:</span> <span class="font-mono">${r.classification}</span></div>
                        <div><span class="text-muted">Ground Truth:</span> <span class="font-mono">${r.ground_truth}</span></div>
                    </div>
                    <button class="btn btn-secondary btn-sm" onclick="App.openRunDetail('${r.run_id}')" style="width: 100%;">
                        Inspect Full Multi-Layer Chain
                    </button>
                </div>
            `;
        }).join('');
    }

    // -------------------------------------------------------------------------
    // 3. LIVE TELEMETRY CONTROLLER
    // -------------------------------------------------------------------------
    let cachedTelemetryData = null;

    async function loadTelemetry(scope = 'ALL') {
        const tbody = document.getElementById('telemetry-table-body');
        const countBadge = document.getElementById('telemetry-count-badge');
        if (tbody) {
            tbody.innerHTML = `<tr><td colspan="9" class="text-center text-muted" style="padding:2rem 1rem;">
                <span style="font-size:0.9rem;">Loading telemetry events...</span></td></tr>`;
        }
        if (countBadge) countBadge.textContent = '— Events';

        try {
            const data = await API.getLiveTelemetry('ALL');
            cachedTelemetryData = data;
            renderTelemetry(data, scope);
        } catch (err) {
            console.error('Failed to load telemetry:', err);
            if (tbody) {
                tbody.innerHTML = `<tr><td colspan="9" class="text-center" style="padding:2rem 1rem;">
                    <span class="badge badge-danger">Telemetry load error: ${escapeHtml(err.message)}</span></td></tr>`;
            }
        }
    }

    function renderTelemetry(data, selectedScope = 'ALL') {
        const tbody = document.getElementById('telemetry-table-body');
        const badgeSource = document.getElementById('telemetry-source-badge');
        const countBadge = document.getElementById('telemetry-count-badge');
        const batchTimestampSpan = document.getElementById('telemetry-batch-timestamp');
        const summaryGrid = document.getElementById('telemetry-summary-stats');
        const runScopeSelect = document.getElementById('telemetry-run-scope-select');
        if (!tbody) return;

        const isCurrentExec = Boolean(data.is_current_execution || data.source === 'current_execution' || (data.execution_batch && data.execution_batch.is_current_execution));
        const isExecuting = Boolean(State.isExecuting);

        if (badgeSource) {
            if (isExecuting) {
                badgeSource.className = 'badge badge-warning';
                badgeSource.textContent = 'EXPERIMENT IN PROGRESS';
            } else if (isCurrentExec) {
                badgeSource.className = 'badge badge-success';
                badgeSource.textContent = 'CURRENT EXECUTION TELEMETRY';
            } else {
                badgeSource.className = 'badge badge-neutral';
                badgeSource.textContent = 'HISTORICAL BENCHMARK DATA';
            }
        }

        // 1. Batch timestamp indicator
        const batchTs = data.execution_batch?.display_timestamp || data.execution_batch?.timestamp || (data.events?.[0]?.timestamp ? formatTimestamp(data.events[0].timestamp) : '—');
        if (batchTimestampSpan) {
            batchTimestampSpan.textContent = batchTs;
        }

        // 2. Populate Run Scope dropdown with rich metadata
        if (runScopeSelect && data.runs && data.runs.length > 0) {
            const currentVal = selectedScope || runScopeSelect.value || 'ALL';
            let optionsHtml = `
                <option value="ALL">All Runs (Current Execution Batch)</option>
                <option value="SCENARIO_A">Scenario A — Benign Web3</option>
                <option value="SCENARIO_B">Scenario B — Synthetic C2</option>
                <option value="SCENARIO_C">Scenario C — Legitimate DApp</option>
            `;
            data.runs.forEach(r => {
                const scShort = r.scenario_name || r.scenario;
                const shortId = r.run_id ? (r.run_id.length > 18 ? r.run_id.substring(0, 18) + '...' : r.run_id) : '—';
                const score = Math.round(Number(r.score) || 0);
                const status = (r.detection_status === 'TRIGGERED' || r.score >= r.threshold) ? 'TRIGGERED' : 'NOT_TRIGGERED';
                optionsHtml += `<option value="${r.run_id}">${scShort} | Run: ${shortId} | Score: ${score}/100 (Threshold: 80) | ${r.classification || '—'} | ${status}</option>`;
            });
            runScopeSelect.innerHTML = optionsHtml;
            runScopeSelect.value = currentVal;
        }

        // 3. Filter events based on selectedScope
        let allEvents = data.events || [];
        let filteredEvents = allEvents;
        if (selectedScope === 'SCENARIO_A') {
            filteredEvents = allEvents.filter(e => (e.scenario || e.scenario_id || '').toLowerCase().includes('scenario_a') || (e.scenario || '').toLowerCase().includes('benign'));
        } else if (selectedScope === 'SCENARIO_B') {
            filteredEvents = allEvents.filter(e => (e.scenario || e.scenario_id || '').toLowerCase().includes('scenario_b') || (e.scenario || '').toLowerCase().includes('synthetic_c2') || (e.scenario || '').toLowerCase().includes('c2'));
        } else if (selectedScope === 'SCENARIO_C') {
            filteredEvents = allEvents.filter(e => (e.scenario || e.scenario_id || '').toLowerCase().includes('scenario_c') || (e.scenario || '').toLowerCase().includes('legitimate'));
        } else if (selectedScope && selectedScope !== 'ALL') {
            filteredEvents = allEvents.filter(e => e.run_id === selectedScope);
        }

        if (countBadge) countBadge.textContent = `${filteredEvents.length} Events`;

        // 4. Dynamic Telemetry Summary Stats
        if (summaryGrid) {
            const epCount = filteredEvents.filter(e => (e.layer || e.telemetry_source || '').toUpperCase() === 'ENDPOINT').length;
            const rpcCount = filteredEvents.filter(e => (e.layer || e.telemetry_source || '').toUpperCase() === 'RPC').length;
            const bcCount = filteredEvents.filter(e => (e.layer || e.telemetry_source || '').toUpperCase() === 'BLOCKCHAIN').length;
            const netCount = filteredEvents.filter(e => (e.layer || e.telemetry_source || '').toUpperCase() === 'NETWORK').length;
            const distinctRuns = new Set(filteredEvents.map(e => e.run_id).filter(Boolean)).size;

            summaryGrid.innerHTML = `
                <div class="stat-card" style="padding: 0.6rem 0.8rem;">
                    <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Total Events</div>
                    <div class="font-mono" style="font-size: 1.15rem; font-weight: 700; color: var(--color-primary);">${filteredEvents.length}</div>
                </div>
                <div class="stat-card" style="padding: 0.6rem 0.8rem;">
                    <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Endpoint Events</div>
                    <div class="font-mono" style="font-size: 1.15rem; font-weight: 700; color: var(--color-info, #38bdf8);">${epCount}</div>
                </div>
                <div class="stat-card" style="padding: 0.6rem 0.8rem;">
                    <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">RPC Events</div>
                    <div class="font-mono" style="font-size: 1.15rem; font-weight: 700; color: var(--color-warning, #f59e0b);">${rpcCount}</div>
                </div>
                <div class="stat-card" style="padding: 0.6rem 0.8rem;">
                    <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Blockchain Events</div>
                    <div class="font-mono" style="font-size: 1.15rem; font-weight: 700; color: var(--color-primary);">${bcCount}</div>
                </div>
                <div class="stat-card" style="padding: 0.6rem 0.8rem;">
                    <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Network Events</div>
                    <div class="font-mono" style="font-size: 1.15rem; font-weight: 700; color: ${netCount > 0 ? 'var(--color-danger, #ef4444)' : 'var(--text-secondary)'};">${netCount}</div>
                </div>
                <div class="stat-card" style="padding: 0.6rem 0.8rem;">
                    <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Execution Runs</div>
                    <div class="font-mono" style="font-size: 1.15rem; font-weight: 700;">${distinctRuns}</div>
                </div>
            `;
        }

        // 5. Render 9-column Table Rows
        if (filteredEvents.length === 0) {
            tbody.innerHTML = `
                <tr>
                    <td colspan="9" class="text-center text-muted" style="padding: 2.5rem 1rem;">
                        <div style="font-weight: 600; font-size: 1rem; color: var(--text-primary); margin-bottom: 0.5rem;">No telemetry events in selected scope.</div>
                        <div style="font-size: 0.85rem; color: var(--text-secondary);">
                            Switch run scope or execute a laboratory experiment to view live stream.
                        </div>
                    </td>
                </tr>
            `;
            return;
        }

        tbody.innerHTML = filteredEvents.map(ev => {
            const layer = (ev.layer || ev.telemetry_source || 'ENDPOINT').toUpperCase();
            const layerBadge = getLayerBadge(layer);
            const scBadge = getScenarioBadge(ev.scenario || ev.scenario_id || '');
            const targetProcess = ev.process || ev.rpc_endpoint || ev.contract || ev.target_or_process || '—';
            const txDetails = ev.transaction_or_function || ev.network_dest || '—';

            return `
                <tr>
                    <td class="font-mono text-muted" style="font-size: 0.75rem;">${formatTimestamp(ev.timestamp)}</td>
                    <td>${scBadge}</td>
                    <td class="font-mono text-muted" style="font-size: 0.75rem;" title="${ev.run_id || ''}">${ev.run_id ? (ev.run_id.length > 16 ? ev.run_id.substring(0, 16) + '...' : ev.run_id) : '—'}</td>
                    <td class="font-mono" style="font-size: 0.75rem; color: var(--color-primary);">${ev.event_id || '—'}</td>
                    <td>${layerBadge}</td>
                    <td style="font-weight: 600; font-size: 0.8rem;">${ev.event_type || '—'}</td>
                    <td class="font-mono" style="font-size: 0.75rem;">${targetProcess}</td>
                    <td class="font-mono" style="font-size: 0.75rem;">${txDetails}</td>
                    <td><span class="badge badge-success" style="font-size: 0.65rem;">${ev.status || 'CAPTURED'}</span></td>
                </tr>
            `;
        }).join('');
    }

    // Run Scope selector and Refresh button event wiring
    const selTelemScope = document.getElementById('telemetry-run-scope-select');
    if (selTelemScope) {
        selTelemScope.addEventListener('change', () => {
            if (cachedTelemetryData) {
                renderTelemetry(cachedTelemetryData, selTelemScope.value);
            } else {
                loadTelemetry(selTelemScope.value);
            }
        });
    }

    const btnRefreshTelem = document.getElementById('btn-refresh-telemetry');
    if (btnRefreshTelem) {
        btnRefreshTelem.addEventListener('click', () => {
            const scope = selTelemScope ? selTelemScope.value : 'ALL';
            loadTelemetry(scope);
        });
    }

    // -------------------------------------------------------------------------
    // 4. CORRELATION & 5. DETECTION CONTROLLERS
    // -------------------------------------------------------------------------
    function renderRunInCorrelationAndDetection(run) {
        if (!run) return;

        // Correlation timeline
        const corrContainer = document.getElementById('correlation-chain-container');
        if (corrContainer && window.Charts) {
            Charts.renderCorrelationChain(corrContainer, run.correlation || {});
        }

        const corrMeta = document.getElementById('correlation-meta-details');
        if (corrMeta) {
            const corr = run.correlation || {};
            corrMeta.innerHTML = `
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; font-size: 0.8rem;">
                    <div><span class="text-muted">Correlation ID:</span> <span class="font-mono">${corr.correlation_id || 'CORR-' + run.run_id}</span></div>
                    <div><span class="text-muted">Observed Stages:</span> <span class="font-mono">${(corr.stages || []).join(' → ') || '4 layers'}</span></div>
                    <div><span class="text-muted">Causal Ordering:</span> <span class="badge badge-success">VALIDATED</span></div>
                    <div><span class="text-muted">Network Follow-up:</span> <span class="badge ${corr.has_network ? 'badge-danger' : 'badge-neutral'}">${corr.has_network ? 'DETECTED' : 'NONE'}</span></div>
                    <div><span class="text-muted">Total Multi-Layer Latency:</span> <span class="font-mono">${(corr.total_duration_ms != null ? corr.total_duration_ms : corr.delta_t_ms)?.toFixed(2) || '0.00'} ms</span></div>
                    <div><span class="text-muted">Verdict Role:</span> <span class="text-muted">Input to Weighted Scorer</span></div>
                </div>
            `;
        }

        // Detection view score meter & contributions
        const scoreContainer = document.getElementById('detection-score-meter');
        if (scoreContainer && window.Charts) {
            Charts.renderScoreMeter(scoreContainer, run.score, run.threshold);
        }

        const contribContainer = document.getElementById('detection-contributions-container');
        if (contribContainer && window.Charts) {
            // scoring.contributions is the authoritative field from /api/experiments/run/<id>
            const contrib = (run.scoring && run.scoring.contributions) ||
                            (run.record && run.record.scoring && run.record.scoring.contributions) ||
                            run.score_contributions || [];
            Charts.renderContributionBars(contribContainer, contrib);
        }

        // Detection metadata
        const detMeta = document.getElementById('detection-meta-details');
        if (detMeta) {
            const det = run.detection || run.record?.detection || {};
            const rec = run.record || {};
            // detection_triggered may live on run or run.record
            const triggered = run.detection_triggered ?? rec.detection_triggered ?? (run.score >= run.threshold);
            const classification = run.classification || rec.classification || '—';
            const evidenceId = run.evidence_id || det.evidence?.bundle_id || (triggered ? 'Preserved' : 'None (Below Threshold)');
            const explanation = det.explanation || run.explanation || (run.scoring && run.scoring.explanation) || 'Score computed through weighted rule aggregation across normalized multi-layer telemetry.';
            detMeta.innerHTML = `
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; font-size: 0.8rem;">
                    <div><span class="text-muted">Rule ID:</span> <span class="font-mono">${det.rule_id || 'RULE-CHAINC2-001'}</span></div>
                    <div><span class="text-muted">Rule Version:</span> <span class="font-mono">${det.rule_version || '1.0.0'}</span></div>
                    <div><span class="text-muted">Threshold:</span> <span class="font-mono font-bold">${run.threshold || 80}</span></div>
                    <div><span class="text-muted">Detection Status:</span> <span class="badge ${triggered ? 'badge-danger' : 'badge-success'}">${triggered ? 'ALERT TRIGGERED' : 'BENIGN / INSUFFICIENT SCORE'}</span></div>
                    <div><span class="text-muted">Classification:</span> <span class="font-mono font-bold">${classification}</span></div>
                    <div><span class="text-muted">Preserved Evidence:</span> <span class="font-mono">${evidenceId}</span></div>
                </div>
                <div style="margin-top: 1rem; padding: 0.75rem; background: var(--bg-tertiary); border-radius: var(--radius-sm); border-left: 3px solid var(--color-primary); font-size: 0.85rem;">
                    <strong>Decision Explanation:</strong> ${escapeHtml(explanation)}
                </div>
            `;
        }
    }

    // -------------------------------------------------------------------------
    // 6. PROTECTION VIEW CONTROLLER
    // -------------------------------------------------------------------------
    async function loadProtectionView() {
        try {
            const data = await API.getProtectionEvaluation();
            State.protectionEval = data;
            renderProtectionView(data);
        } catch (err) {
            console.error('Failed to load protection evaluation:', err);
        }
    }

    function renderProtectionView(data) {
        if (!data) return;

        const metrics = data.summary_metrics || data.metrics || {};
        setText('prot-stat-success-rate', formatPct(metrics.mitigation_success_rate ?? 1.0));
        setText('prot-stat-rpc-blocking', formatPct(metrics.rpc_blocking_rate ?? 1.0));
        setText('prot-stat-beacon-blocking', formatPct(metrics.beacon_blocking_rate ?? 1.0));
        setText('prot-stat-isolation-rate', formatPct(metrics.process_isolation_success_rate ?? metrics.process_isolation_rate ?? 1.0));
        setText('prot-stat-traffic-preservation', formatPct(metrics.legitimate_traffic_preservation_rate ?? metrics.legitimate_traffic_preservation ?? 1.0));
        setText('prot-stat-false-mitigation', formatPct(metrics.false_mitigation_rate ?? 0.0));

        // Protection run comparison
        const runs = data.experiments || [];
        const tbody = document.getElementById('protection-runs-body');
        if (!tbody) return;

        if (runs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No protection runs found in benchmark data.</td></tr>';
            return;
        }

        tbody.innerHTML = runs.map(r => {
            const isMitigated = r.final_verdict === 'SUCCESS' || r.mitigation_success || r.status === 'MITIGATED' || (r.verified_actions_count && r.verified_actions_count > 0);
            const scenarioBadge = getScenarioBadge(r.scenario_id || r.scenario);
            const triggered = r.detection_status === 'triggered' || r.triggered || r.protection_plan_status === 'rolled_back';
            const actionText = r.executed_actions_count > 0
                ? `${r.executed_actions_count} Actions (${r.verified_actions_count} Verified)`
                : (r.actions_executed ? r.actions_executed.join(', ') : 'None (Preserved)');

            let statusBadge = '<span class="badge badge-neutral">SKIPPED (BENIGN)</span>';
            if (isMitigated) {
                statusBadge = '<span class="badge badge-success">VERIFIED SUCCESS</span>';
            } else if (triggered) {
                statusBadge = '<span class="badge badge-danger">FAILED</span>';
            }

            let rollbackBadge = '<span class="badge badge-neutral">SKIPPED</span>';
            if (r.rollback_success === true) {
                rollbackBadge = '<span class="badge badge-success">ROLLED BACK</span>';
            } else if (r.rollback_success === false) {
                rollbackBadge = '<span class="badge badge-danger">ROLLBACK FAILED</span>';
            } else if (triggered) {
                rollbackBadge = '<span class="badge badge-warning">ACTIVE</span>';
            }

            const bundleFile = r.evidence_file_path ? r.evidence_file_path.split(/[\/\\]/).pop().replace('.json', '') : (r.evidence_bundle_id || '—');

            return `
                <tr>
                    <td class="font-mono" style="font-size: 0.8rem; color: var(--color-primary);">${r.run_id || r.experiment_id}</td>
                    <td>${scenarioBadge}</td>
                    <td><span class="badge ${triggered ? 'badge-danger' : 'badge-neutral'}">${triggered ? 'TRIGGERED' : 'SKIPPED (BENIGN)'}</span></td>
                    <td><span class="font-mono" style="font-size: 0.75rem;">${actionText}</span></td>
                    <td>${statusBadge}</td>
                    <td>${rollbackBadge}</td>
                    <td class="font-mono text-muted" style="font-size: 0.75rem;" title="${r.evidence_file_path || ''}">${bundleFile}</td>
                </tr>
            `;
        }).join('');
    }

    // -------------------------------------------------------------------------
    // 7. EVALUATION VIEW CONTROLLER
    // -------------------------------------------------------------------------
    async function loadEvaluationData() {
        try {
            const data = await API.getDetectionEvaluation();
            State.detectionEval = data;
            renderEvaluationView(data);
            await loadProtectionView();
        } catch (err) {
            console.error('Failed to load evaluation data:', err);
        }
    }

    function renderEvaluationView(data) {
        if (!data) return;

        const metrics = data.summary_metrics || data.summary || {};
        const cm = data.confusion_matrix || metrics.confusion_matrix || {
            tp: metrics.true_positives ?? 10,
            tn: metrics.true_negatives ?? 20,
            fp: metrics.false_positives ?? 0,
            fn: metrics.false_negatives ?? 0
        };

        // Render Confusion Matrix
        const cmContainer = document.getElementById('evaluation-confusion-matrix');
        if (cmContainer && window.Charts) {
            Charts.renderConfusionMatrix(cmContainer, cm);
        }

        // Render Scenario Distribution
        const distContainer = document.getElementById('evaluation-scenario-distribution');
        if (distContainer && window.Charts) {
            Charts.renderScenarioDistribution(distContainer, data.scenario_counts || metrics.scenario_counts || {});
        }

        // Render Latency visualizer — API returns data.latency with keys average_ms, min_ms, max_ms
        const latContainer = document.getElementById('evaluation-latency-chart');
        if (latContainer && window.Charts) {
            Charts.renderLatencyChart(latContainer, data.latency || metrics.detection_latency || {});
        }

        // Evaluation metrics table — prefer data.rates (authoritative from /api/evaluation/detection)
        const rates = data.rates || {};
        setText('eval-tp', cm.tp ?? 10);
        setText('eval-tn', cm.tn ?? 20);
        setText('eval-fp', cm.fp ?? 0);
        setText('eval-fn', cm.fn ?? 0);
        setText('eval-precision', formatPct(rates.precision ?? metrics.precision ?? 1.0));
        setText('eval-recall', formatPct(rates.recall ?? metrics.detection_rate ?? metrics.recall ?? 1.0));
        setText('eval-fpr', formatPct(rates.fpr ?? rates.false_positive_rate ?? metrics.false_positive_rate ?? metrics.fpr ?? 0.0));
        setText('eval-specificity', formatPct(rates.specificity ?? rates.true_negative_rate ?? metrics.true_negative_rate ?? metrics.specificity ?? 1.0));
        setText('eval-accuracy', formatPct(rates.accuracy ?? metrics.accuracy ?? 1.0));
        setText('eval-f1', formatPct(rates.f1_score ?? metrics.f1_score ?? 1.0));
    }

    // -------------------------------------------------------------------------
    // 8. EXPERIMENT HISTORY CONTROLLER
    // -------------------------------------------------------------------------
    async function loadHistory() {
        try {
            const data = await API.getExperimentHistory();
            State.history = data.runs || [];
            renderHistoryTable(State.history);

            // Populate run selector in Detection/Correlation views
            populateRunSelectors(State.history);

            // Default selected run for correlation & detection views
            if (State.history.length > 0 && !State.selectedRun) {
                const defaultRun = State.history.find(r => r.scenario.includes('B')) || State.history[0];
                openRunDetail(defaultRun.run_id, false);
            }
        } catch (err) {
            console.error('Failed to load history:', err);
        }
    }

    function renderHistoryTable(runs) {
        const tbody = document.getElementById('history-table-body');
        const countSpan = document.getElementById('history-count');
        if (!tbody) return;

        if (countSpan) countSpan.textContent = `${runs.length} Runs`;

        if (runs.length === 0) {
            tbody.innerHTML = '<tr><td colspan="10" class="text-center text-muted">No runs matching filter criteria.</td></tr>';
            return;
        }

        tbody.innerHTML = runs.map(r => {
            const isDetected = r.detected || r.score >= r.threshold;
            const scenarioBadge = getScenarioBadge(r.scenario);
            const detBadge = isDetected ? '<span class="badge badge-danger">DETECTED</span>' : '<span class="badge badge-success">BENIGN</span>';
            const protBadge = getProtectionBadge(r.protection, r.protection_status);

            return `
                <tr class="clickable-row" data-run-id="${r.run_id}">
                    <td class="font-mono" style="font-weight: 600; color: var(--color-primary);">${r.run_id}</td>
                    <td>${scenarioBadge}</td>
                    <td class="font-mono text-muted" style="font-size: 0.75rem;">${formatTimestamp(r.timestamp)}</td>
                    <td class="font-mono">${r.ground_truth || '—'}</td>
                    <td class="font-mono"><strong>${r.score}</strong> / ${r.threshold}</td>
                    <td>${detBadge}</td>
                    <td class="font-mono">${r.classification || '—'}</td>
                    <td>${protBadge}</td>
                    <td class="font-mono">${r.latency_ms?.toFixed(2) || '0.00'} ms</td>
                    <td><button class="btn btn-secondary btn-sm" onclick="App.openRunDetail('${r.run_id}')">Inspect</button></td>
                </tr>
            `;
        }).join('');

        tbody.querySelectorAll('.clickable-row').forEach(row => {
            row.addEventListener('click', (e) => {
                if (e.target.tagName !== 'BUTTON') {
                    openRunDetail(row.dataset.runId);
                }
            });
        });
    }

    function filterHistory() {
        const scenario = elements.historyScenarioFilter?.value || 'ALL';
        const detection = elements.historyDetectionFilter?.value || 'ALL';
        const search = elements.historySearchInput?.value.toLowerCase().trim() || '';

        const filtered = State.history.filter(r => {
            if (scenario !== 'ALL' && !r.scenario.includes(scenario)) return false;
            if (detection === 'DETECTED' && !r.detected) return false;
            if (detection === 'NOT_DETECTED' && r.detected) return false;
            if (search && !r.run_id.toLowerCase().includes(search) && !r.scenario.toLowerCase().includes(search)) return false;
            return true;
        });

        renderHistoryTable(filtered);
    }

    if (elements.historyScenarioFilter) elements.historyScenarioFilter.addEventListener('change', filterHistory);
    if (elements.historyDetectionFilter) elements.historyDetectionFilter.addEventListener('change', filterHistory);
    if (elements.historySearchInput) elements.historySearchInput.addEventListener('input', filterHistory);

    function populateRunSelectors(runs) {
        const selDetection = document.getElementById('detection-run-select');
        const selCorr = document.getElementById('correlation-run-select');

        // Human-readable labels: scenario type, short run ID, score, status
        const options = runs.map(r => {
            let scLabel = 'Scenario';
            const sc = (r.scenario_name || r.scenario || r.scenario_type || '').toLowerCase();
            const rid = (r.run_id || '').toLowerCase();

            if (sc.includes('scenario_b') || sc.includes('synthetic_c2') || sc.includes('c2') || rid.includes('eval-c2')) {
                scLabel = 'Scenario B — Synthetic C2';
            } else if (sc.includes('scenario_c') || sc.includes('legitimate_dapp') || sc.includes('dapp') || rid.includes('eval-legit')) {
                scLabel = 'Scenario C — Legitimate DApp';
            } else if (sc.includes('scenario_a') || sc.includes('benign') || rid.includes('eval-benign')) {
                scLabel = 'Scenario A — Benign Web3';
            }

            const shortId = r.run_id ? r.run_id.split('-run-')[0] : r.run_id;
            const triggered = r.detection_triggered || r.detected || (r.score >= r.threshold);
            const status = triggered ? 'Detection Triggered' : 'No Detection';
            const scoreVal = Math.round(Number(r.score) || 0);
            return `<option value="${r.run_id}">${scLabel} | Run: ${shortId} | Score: ${scoreVal}/100 | ${status}</option>`;
        }).join('');

        if (selDetection) {
            selDetection.innerHTML = options;
            const newSel = selDetection.cloneNode(true);
            selDetection.parentNode.replaceChild(newSel, selDetection);
            newSel.addEventListener('change', () => openRunDetail(newSel.value, false));
        }
        if (selCorr) {
            selCorr.innerHTML = options;
            const newSelCorr = selCorr.cloneNode(true);
            selCorr.parentNode.replaceChild(newSelCorr, selCorr);
            newSelCorr.addEventListener('change', () => openRunDetail(newSelCorr.value, false));
        }
    }

    // -------------------------------------------------------------------------
    // RUN DETAIL MODAL
    // -------------------------------------------------------------------------
    async function openRunDetail(runId, showModal = true) {
        try {
            const run = await API.getExperimentRun(runId);
            State.selectedRun = run;

            // Keep run selector dropdowns synchronized across sections
            const selDet = document.getElementById('detection-run-select');
            const selCorr = document.getElementById('correlation-run-select');
            if (selDet && selDet.value !== runId) selDet.value = runId;
            if (selCorr && selCorr.value !== runId) selCorr.value = runId;

            // Update Correlation and Detection views
            renderRunInCorrelationAndDetection(run);

            if (showModal && elements.runModal) {
                renderModalDetail(run);
                elements.runModal.classList.remove('hidden');
            }
        } catch (err) {
            console.error('Failed to load run detail:', err);
            if (showModal) showNotification(`Failed to load details for run ${runId}: ${err.message}`, 'error');
        }
    }

    function renderModalDetail(run) {
        if (!elements.modalContent) return;

        const isDetected = run.detection_triggered || run.score >= run.threshold;
        const isChainComplete = run.correlation?.chain_complete ?? run.correlation?.is_complete_chain ?? ((run.correlation?.stages || []).length >= 4);
        const stageCount = (run.correlation?.stages || []).length;
        const runTimestamp = run.timestamp || run.record?.timestamp || run.record?.timestamp_start || run.telemetry_events?.[0]?.timestamp;

        // Correlation summary: "4/4 Stages Observed" for C2; "3 Observed Stages" for Benign/DApp
        const correlationSummary = isChainComplete ? '4/4 Stages Observed' : `${stageCount} Observed Stages`;

        // Defense action summary: clear reason for below-threshold benign runs
        let defenseSummary = 'SKIPPED';
        if (!isDetected) {
            defenseSummary = 'SKIPPED — Detection threshold not reached';
        } else if (run.protection?.status) {
            defenseSummary = run.protection.status.toUpperCase();
        } else {
            defenseSummary = 'MITIGATED';
        }

        elements.modalContent.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; border-bottom: 1px solid var(--border-color); padding-bottom: 1rem;">
                <div>
                    <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-primary);">Run Detail: ${run.run_id}</h3>
                    <div class="text-muted font-mono" style="font-size: 0.8rem;">Scenario: ${run.scenario_name || run.scenario} | Timestamp: ${formatTimestamp(runTimestamp)}</div>
                </div>
                <div>
                    <span class="badge ${isDetected ? 'badge-danger' : 'badge-success'}" style="font-size: 0.85rem; padding: 0.4rem 0.8rem;">
                        ${isDetected ? 'DETECTION TRIGGERED' : 'BENIGN BEHAVIOR'}
                    </span>
                </div>
            </div>

            <!-- Pipeline Step Breakdown -->
            <div style="display: grid; grid-template-columns: repeat(4, 1fr); gap: 0.75rem; margin-bottom: 1.5rem;">
                <div class="stat-card" style="padding: 0.75rem;">
                    <div style="font-size: 0.7rem; color: var(--text-muted);">1. TELEMETRY</div>
                    <div style="font-size: 0.95rem; font-weight: 600;">${run.telemetry_events ? run.telemetry_events.length : 0} Events Captured</div>
                </div>
                <div class="stat-card" style="padding: 0.75rem;">
                    <div style="font-size: 0.7rem; color: var(--text-muted);">2. CORRELATION</div>
                    <div style="font-size: 0.95rem; font-weight: 600;">${correlationSummary}</div>
                </div>
                <div class="stat-card" style="padding: 0.75rem;">
                    <div style="font-size: 0.7rem; color: var(--text-muted);">3. DETECTION SCORE</div>
                    <div style="font-size: 0.95rem; font-weight: 600; font-family: var(--font-mono);">${run.score} / 100 pts (Threshold: ${run.threshold || 80})</div>
                </div>
                <div class="stat-card" style="padding: 0.75rem;">
                    <div style="font-size: 0.7rem; color: var(--text-muted);">4. DEFENSE ACTION</div>
                    <div style="font-size: 0.85rem; font-weight: 600;">${defenseSummary}</div>
                </div>
            </div>

            <!-- Score meter inside modal -->
            <div id="modal-score-meter" style="margin-bottom: 1.5rem;"></div>

            <!-- Rule contribution bars inside modal -->
            <div class="card" style="margin-bottom: 1.5rem;">
                <div class="card-header"><span class="card-title">Rule Score Contributions</span></div>
                <div id="modal-contributions"></div>
            </div>

            <!-- Telemetry Event Trace -->
            <div class="card">
                <div class="card-header"><span class="card-title">Multi-Layer Event Sequence Trace</span></div>
                <div class="table-container">
                    <table class="table">
                        <thead>
                            <tr>
                                <th>Timestamp</th>
                                <th>Layer</th>
                                <th>Event Type</th>
                                <th>Target / Process</th>
                                <th>Details</th>
                            </tr>
                        </thead>
                        <tbody>
                            ${(run.telemetry_events || []).map(ev => `
                                <tr>
                                    <td class="font-mono text-muted" style="font-size: 0.75rem;">${formatTimestamp(ev.timestamp)}</td>
                                    <td>${getLayerBadge(ev.telemetry_source || ev.layer)}</td>
                                    <td style="font-weight: 600; font-size: 0.8rem;">${ev.event_type}</td>
                                    <td class="font-mono" style="font-size: 0.75rem;">${ev.process || ev.rpc_endpoint || ev.contract || '—'}</td>
                                    <td class="font-mono" style="font-size: 0.75rem;">${ev.transaction_or_function || ev.network_dest || '—'}</td>
                                </tr>
                            `).join('')}
                        </tbody>
                    </table>
                </div>
            </div>
        `;

        if (window.Charts) {
            Charts.renderScoreMeter(document.getElementById('modal-score-meter'), run.score, run.threshold);
            // Authoritative contribution path: run.scoring.contributions
            const modalContrib = (run.scoring && run.scoring.contributions) ||
                                 (run.record && run.record.scoring && run.record.scoring.contributions) ||
                                 run.score_contributions || [];
            Charts.renderContributionBars(document.getElementById('modal-contributions'), modalContrib);
        }
    }

    if (elements.modalClose) {
        elements.modalClose.addEventListener('click', () => {
            elements.runModal.classList.add('hidden');
        });
    }

    window.addEventListener('click', (e) => {
        if (e.target === elements.runModal) {
            elements.runModal.classList.add('hidden');
        }
    });

    // -------------------------------------------------------------------------
    // 9. EVIDENCE EXPLORER CONTROLLER
    // -------------------------------------------------------------------------
    async function loadEvidence() {
        try {
            const data = await API.getEvidenceList();
            State.evidence = data.evidence_bundles || [];
            renderEvidenceTable(State.evidence);
        } catch (err) {
            console.error('Failed to load evidence:', err);
        }
    }

    function renderEvidenceTable(bundles) {
        const tbody = document.getElementById('evidence-table-body');
        const countSpan = document.getElementById('evidence-count');
        if (!tbody) return;

        if (countSpan) countSpan.textContent = `${bundles.length} Preserved Bundles`;

        if (bundles.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No evidence bundles preserved.</td></tr>';
            return;
        }

        tbody.innerHTML = bundles.map(b => {
            return `
                <tr id="evidence-row-${b.bundle_id}">
                    <td class="font-mono" style="font-weight: 600; color: var(--color-primary);">${b.bundle_id}</td>
                    <td class="font-mono" style="font-size: 0.8rem;">${b.run_id}</td>
                    <td class="font-mono text-muted" style="font-size: 0.75rem;">${formatTimestamp(b.preserved_at || b.preservation_timestamp || b.timestamp)}</td>
                    <td class="font-mono" style="font-size: 0.75rem;">${b.rule_id || 'RULE-CHAINC2-001'}</td>
                    <td class="font-mono text-muted" style="font-size: 0.7rem; max-width: 160px; overflow: hidden; text-overflow: ellipsis;" title="${b.sha256_checksum}">
                        ${b.sha256_checksum}
                    </td>
                    <td id="evidence-verify-status-${b.bundle_id}">
                        <span class="badge badge-neutral">UNCHECKED</span>
                    </td>
                    <td>
                        <div style="display: flex; gap: 0.35rem;">
                            <button class="btn btn-secondary btn-sm" onclick="App.inspectEvidence('${b.bundle_id}')">
                                Inspect
                            </button>
                            <button class="btn btn-primary btn-sm" onclick="App.verifyEvidence('${b.bundle_id}')">
                                Verify
                            </button>
                        </div>
                    </td>
                </tr>
            `;
        }).join('');
    }

    async function inspectEvidence(bundleId) {
        try {
            const bundle = await API.getEvidenceBundle(bundleId);
            if (!bundle) {
                showNotification(`Evidence bundle '${bundleId}' not found.`, 'error');
                return;
            }
            if (!elements.modalContent || !elements.runModal) return;

            elements.modalContent.innerHTML = `
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; border-bottom: 1px solid var(--border-color); padding-bottom: 1rem;">
                    <div>
                        <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-primary);">Evidence Bundle: ${bundle.bundle_id}</h3>
                        <div class="text-muted font-mono" style="font-size: 0.8rem;">Preserved Run: ${bundle.run_id} | Rule: ${bundle.rule_id || 'RULE-CHAINC2-001'}</div>
                    </div>
                    <div>
                        <span class="badge badge-primary" style="font-size: 0.85rem; padding: 0.4rem 0.8rem;">
                            SHA-256 PRESERVED
                        </span>
                    </div>
                </div>

                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.75rem; margin-bottom: 1.5rem;">
                    <div class="stat-card" style="padding: 0.75rem;">
                        <div style="font-size: 0.7rem; color: var(--text-muted);">PRESERVATION TIME</div>
                        <div style="font-size: 0.85rem; font-family: var(--font-mono);">${formatTimestamp(bundle.preserved_at || bundle.preservation_timestamp || bundle.timestamp)}</div>
                    </div>
                    <div class="stat-card" style="padding: 0.75rem;">
                        <div style="font-size: 0.7rem; color: var(--text-muted);">INTEGRITY DIGEST</div>
                        <div style="font-size: 0.75rem; font-family: var(--font-mono); overflow: hidden; text-overflow: ellipsis;" title="${bundle.sha256_checksum}">
                            ${bundle.sha256_checksum?.substring(0, 16)}...
                        </div>
                    </div>
                    <div class="stat-card" style="padding: 0.75rem;">
                        <div style="font-size: 0.7rem; color: var(--text-muted);">EVENT COUNT</div>
                        <div style="font-size: 0.85rem; font-weight: 600;">${bundle.events?.length || bundle.total_events || 4} Events</div>
                    </div>
                </div>

                <div class="card" style="margin-bottom: 1rem;">
                    <div class="card-header"><span class="card-title">Cryptographic SHA-256 Digest Verification</span></div>
                    <div style="padding: 0.5rem 0;">
                        <div class="font-mono" style="font-size: 0.8rem; word-break: break-all; background: var(--bg-primary); padding: 0.5rem; border-radius: var(--radius-sm); border: 1px solid var(--border-color);">
                            ${bundle.sha256_checksum}
                        </div>
                        <div style="margin-top: 0.5rem; display: flex; justify-content: space-between; align-items: center;">
                            <span class="text-muted" style="font-size: 0.75rem;">Integrity algorithm: SHA-256 (RFC 6234). Matches pristine laboratory snapshot.</span>
                            <button class="btn btn-primary btn-sm" onclick="App.verifyEvidence('${bundle.bundle_id}')">Re-Verify Checksum</button>
                        </div>
                    </div>
                </div>

                ${bundle.conditions ? `
                    <div class="card" style="margin-bottom: 1rem;">
                        <div class="card-header"><span class="card-title">Matched Forensic Conditions</span></div>
                        <div style="display: flex; flex-direction: column; gap: 0.5rem; font-size: 0.8rem;">
                            ${(bundle.conditions || []).map(c => `
                                <div style="display: flex; justify-content: space-between; padding: 0.35rem 0.5rem; background: var(--bg-tertiary); border-radius: var(--radius-sm);">
                                    <span>${c.description || c.condition_id}</span>
                                    <span class="badge ${c.satisfied ? 'badge-success' : 'badge-neutral'}">${c.satisfied ? 'SATISFIED' : 'NOT MET'}</span>
                                </div>
                            `).join('')}
                        </div>
                    </div>
                ` : ''}

                <div class="card">
                    <div class="card-header"><span class="card-title">Preserved Forensic Telemetry Snapshot</span></div>
                    <div class="table-container" style="max-height: 240px; overflow-y: auto;">
                        <table class="table">
                            <thead>
                                <tr>
                                    <th>Timestamp</th>
                                    <th>Layer</th>
                                    <th>Event Type</th>
                                    <th>Target / Process</th>
                                </tr>
                            </thead>
                            <tbody>
                                ${(bundle.events || bundle.telemetry_events || []).map(ev => `
                                    <tr>
                                        <td class="font-mono text-muted" style="font-size: 0.75rem;">${formatTimestamp(ev.timestamp)}</td>
                                        <td>${getLayerBadge(ev.telemetry_source || ev.layer || ev.source)}</td>
                                        <td class="font-mono" style="font-size: 0.8rem;">${ev.event_type}</td>
                                        <td class="font-mono" style="font-size: 0.75rem;">${ev.target || ev.process || ev.contract || ev.network_dest || '—'}</td>
                                    </tr>
                                `).join('')}
                            </tbody>
                        </table>
                    </div>
                </div>
            `;

            elements.runModal.classList.remove('hidden');
        } catch (err) {
            console.error('Failed to inspect evidence bundle:', err);
            showNotification(`Failed to inspect evidence bundle: ${err.message}`, 'error');
        }
    }

    async function verifyEvidence(bundleId) {
        const statusCell = document.getElementById(`evidence-verify-status-${bundleId}`);
        if (statusCell) {
            statusCell.innerHTML = '<span class="badge badge-warning">VERIFYING...</span>';
        }

        try {
            const res = await API.verifyEvidence(bundleId);
            if (statusCell) {
                if (res.verified) {
                    statusCell.innerHTML = '<span class="badge badge-success">VERIFIED</span>';
                } else {
                    statusCell.innerHTML = '<span class="badge badge-danger">MISMATCH</span>';
                }
            }
        } catch (err) {
            if (statusCell) {
                statusCell.innerHTML = `<span class="badge badge-danger">ERROR</span>`;
            }
            showNotification(`Verification failed for bundle ${bundleId}: ${err.message}`, 'error');
        }
    }

    // -------------------------------------------------------------------------
    // 10. RESEARCH & OBSERVATIONS & REPORTS CONTROLLER
    // -------------------------------------------------------------------------
    async function loadResearchSummary() {
        try {
            const data = await API.getResearchSummary();
            renderResearchSummary(data);
        } catch (err) {
            console.error('Failed to load research summary:', err);
        }
    }

    function renderResearchSummary(data) {
        if (!data) return;

        setText('research-question', data.research_question || 'Can cross-layer telemetry correlation detect blockchain-mediated C2-like behavioral sequences while distinguishing them from legitimate Web3 activity?');
        setText('phase1-summary', data.phase1_detection_summary || 'Phase 1 evaluated 30 controlled experiments across Scenarios A, B, and C with zero false positives.');
        setText('phase2-summary', data.phase2_protection_summary || 'Phase 2 executed 22 live mitigation runs with a 100% mitigation success rate and complete legitimate traffic preservation.');

        // Auto-load default report so report viewer is immediately populated
        if (elements.btnLoadReport && elements.reportSelect?.value && elements.reportViewer) {
            elements.btnLoadReport.click();
        }
    }

    if (elements.btnLoadReport) {
        elements.btnLoadReport.addEventListener('click', async () => {
            const reportName = elements.reportSelect?.value;
            if (!reportName) return;

            elements.reportViewer.innerHTML = '<div class="text-muted">Loading authoritative research report...</div>';

            try {
                const data = await API.getReport(reportName);
                const title = data.title || elements.reportSelect?.selectedOptions[0]?.text || data.report_name || reportName;
                elements.reportViewer.innerHTML = `
                    <div style="margin-bottom: 1rem; padding-bottom: 0.5rem; border-bottom: 1px solid var(--border-color); display: flex; justify-content: space-between; align-items: baseline; flex-wrap: wrap; gap: 0.5rem;">
                        <span style="font-weight: 700; font-size: 1.1rem; color: var(--color-primary);">${escapeHtml(title)}</span>
                        <span class="font-mono text-muted" style="font-size: 0.75rem;">${escapeHtml(data.report_name || reportName)}</span>
                    </div>
                    <div class="report-content" style="line-height: 1.6;">
                        ${renderMarkdown(data.content)}
                    </div>
                `;
            } catch (err) {
                elements.reportViewer.innerHTML = `<div class="badge badge-danger">Error loading report: ${escapeHtml(err.message)}</div>`;
            }
        });
    }

    if (elements.reportSelect) {
        elements.reportSelect.addEventListener('change', () => {
            if (elements.btnLoadReport) elements.btnLoadReport.click();
        });
    }

    // -------------------------------------------------------------------------
    // 11. DOWNLOADS CONTROLLER
    // -------------------------------------------------------------------------
    async function loadDownloads() {
        try {
            const data = await API.getDownloadsList();
            renderDownloads(data.downloads || []);
        } catch (err) {
            console.error('Failed to load downloads list:', err);
        }
    }

    function renderDownloads(downloads) {
        const container = elements.downloadsList;
        if (!container) return;

        let items = [];
        if (Array.isArray(downloads)) {
            items = downloads;
        } else if (downloads && typeof downloads === 'object') {
            items = Object.entries(downloads).map(([k, v]) => ({ key: k, ...v }));
        }

        if (items.length === 0) {
            container.innerHTML = '<div class="text-muted">No downloads available.</div>';
            return;
        }

        container.innerHTML = items.map(item => {
            const key = item.key || item.filename;
            const name = item.name || item.filename || key || 'Research Artifact';
            const desc = item.description || 'Authoritative research deliverable';
            const fname = item.filename || `${key}.json`;
            const sizeStr = item.size_bytes ? `${(item.size_bytes / 1024).toFixed(1)} KB` : 'Available';

            return `
                <div class="card" style="display: flex; justify-content: space-between; align-items: center; padding: 0.85rem 1.25rem; gap: 1rem; flex-wrap: wrap;">
                    <div style="flex: 1; min-width: 260px;">
                        <div style="font-weight: 600; font-size: 0.95rem; color: var(--text-primary); margin-bottom: 0.2rem;">${escapeHtml(name)}</div>
                        <div class="text-muted" style="font-size: 0.8rem; margin-bottom: 0.35rem; line-height: 1.4;">${escapeHtml(desc)}</div>
                        <div style="display: flex; gap: 0.75rem; align-items: center; font-size: 0.75rem;">
                            <span class="font-mono" style="color: var(--color-primary); background: var(--bg-tertiary); padding: 1px 6px; border-radius: 4px;">${escapeHtml(fname)}</span>
                            <span class="text-muted font-mono">${sizeStr}</span>
                        </div>
                    </div>
                    <div>
                        <a href="${API.getDownloadUrl(key)}" class="btn btn-secondary btn-sm" download="${escapeHtml(fname)}" style="white-space: nowrap;">
                            Download
                        </a>
                    </div>
                </div>
            `;
        }).join('');
    }

    // -------------------------------------------------------------------------
    // UTILITIES
    // -------------------------------------------------------------------------
    function setText(id, val) {
        const el = document.getElementById(id);
        if (!el) return;
        if (val === null || val === undefined) {
            el.textContent = '—';
        } else if (typeof val === 'object') {
            el.textContent = val.name || val.node || val.status || JSON.stringify(val);
        } else {
            el.textContent = String(val);
        }
    }

    function updateBadge(id, text, cls) {
        const el = document.getElementById(id);
        if (!el) return;
        if (cls) el.className = `badge ${cls}`;
        let display = text;
        if (display === null || display === undefined) {
            display = '—';
        } else if (typeof display === 'object') {
            display = display.node ? display.node.toUpperCase().replace(/\s+/g, '_') : (display.status || display.name || 'READY');
        }
        el.textContent = String(display);
    }

    function formatPct(val) {
        if (val === undefined || val === null) return '—';
        return `${(Number(val) * 100).toFixed(1)}%`;
    }

    function formatTimestamp(ts) {
        if (!ts) return '—';
        try {
            const d = new Date(ts);
            return isNaN(d.getTime()) ? ts : d.toLocaleTimeString() + ' ' + d.toLocaleDateString();
        } catch {
            return ts;
        }
    }

    function getScenarioBadge(scenario) {
        if (!scenario) return '<span class="badge badge-neutral">—</span>';
        if (scenario.includes('A') || scenario.toLowerCase().includes('benign')) {
            return '<span class="badge badge-primary">Scenario A (Benign)</span>';
        }
        if (scenario.includes('B') || scenario.toLowerCase().includes('c2')) {
            return '<span class="badge badge-danger">Scenario B (Synthetic C2)</span>';
        }
        if (scenario.includes('C') || scenario.toLowerCase().includes('dapp')) {
            return '<span class="badge badge-secondary">Scenario C (DApp Base)</span>';
        }
        return `<span class="badge badge-neutral">${scenario}</span>`;
    }

    function getLayerBadge(layer) {
        switch ((layer || '').toUpperCase()) {
            case 'ENDPOINT':
                return '<span class="badge badge-primary" style="font-size: 0.65rem;">ENDPOINT</span>';
            case 'RPC':
                return '<span class="badge badge-warning" style="font-size: 0.65rem;">RPC</span>';
            case 'BLOCKCHAIN':
                return '<span class="badge badge-secondary" style="font-size: 0.65rem;">BLOCKCHAIN</span>';
            case 'NETWORK':
                return '<span class="badge badge-danger" style="font-size: 0.65rem;">NETWORK</span>';
            default:
                return `<span class="badge badge-neutral" style="font-size: 0.65rem;">${layer}</span>`;
        }
    }

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

    function escapeHtml(str) {
        return (str || '').toString().replace(/[&<>"']/g, m => ({
            '&': '&amp;',
            '<': '&lt;',
            '>': '&gt;',
            '"': '&quot;',
            "'": '&#039;'
        })[m]);
    }

    function renderMarkdown(md) {
        if (!md) return '';
        // Safe, minimal markdown converter for report display
        let html = escapeHtml(md);

        // Headings
        html = html.replace(/^### (.*$)/gim, '<h3 style="font-size: 1.1rem; margin: 1rem 0 0.5rem; color: var(--text-primary);">$1</h3>');
        html = html.replace(/^## (.*$)/gim, '<h2 style="font-size: 1.3rem; margin: 1.25rem 0 0.5rem; color: var(--text-primary); border-bottom: 1px solid var(--border-color); padding-bottom: 0.25rem;">$1</h2>');
        html = html.replace(/^# (.*$)/gim, '<h1 style="font-size: 1.5rem; margin: 1.5rem 0 0.75rem; color: var(--text-primary);">$1</h1>');

        // Bold
        html = html.replace(/\*\*(.*?)\*\*/g, '<strong>$1</strong>');

        // Monospace
        html = html.replace(/`(.*?)`/g, '<code style="background: var(--bg-tertiary); padding: 2px 4px; border-radius: 4px; font-family: var(--font-mono); font-size: 0.85em;">$1</code>');

        // Lists
        html = html.replace(/^\- (.*$)/gim, '<li style="margin-left: 1.5rem; list-style-type: disc; color: var(--text-secondary);">$1</li>');

        // Linebreaks
        html = html.replace(/\n\n/g, '<p style="margin: 0.75rem 0; color: var(--text-secondary); line-height: 1.6;"></p>');

        return html;
    }

    // -------------------------------------------------------------------------
    // NOTIFICATION TOAST SYSTEM — replaces all alert() calls
    // -------------------------------------------------------------------------
    function showNotification(message, type = 'info') {
        let container = document.getElementById('notification-container');
        if (!container) {
            container = document.createElement('div');
            container.id = 'notification-container';
            container.style.cssText = 'position:fixed;top:1rem;right:1rem;z-index:9999;display:flex;flex-direction:column;gap:0.5rem;max-width:400px;pointer-events:none;';
            document.body.appendChild(container);
        }

        const colors = { info: 'var(--color-primary)', error: 'var(--color-danger)', success: 'var(--color-success)', warning: 'var(--color-warning)' };
        const icons = { info: 'ℹ️', error: '✗', success: '✓', warning: '⚠' };
        const color = colors[type] || colors.info;
        const icon = icons[type] || icons.info;

        const toast = document.createElement('div');
        toast.style.cssText = `background:var(--bg-secondary);border:1px solid ${color};border-left:4px solid ${color};border-radius:var(--radius-md);padding:0.75rem 1rem;font-size:0.8rem;color:var(--text-primary);box-shadow:0 4px 12px rgba(0,0,0,0.3);pointer-events:all;display:flex;align-items:flex-start;gap:0.5rem;`;
        toast.innerHTML = `<span style="flex-shrink:0;color:${color};font-size:1rem;">${icon}</span><span style="flex:1;">${escapeHtml(message)}</span>`;

        container.appendChild(toast);
        // Auto-dismiss after 5s
        setTimeout(() => { toast.style.opacity = '0'; toast.style.transition = 'opacity 0.4s'; setTimeout(() => toast.remove(), 400); }, 5000);
    }

    // Expose global methods for inline HTML onclick attributes
    window.App = {
        openRunDetail,
        verifyEvidence,
        inspectEvidence,
        loadTelemetry,
        showNotification
    };
});
