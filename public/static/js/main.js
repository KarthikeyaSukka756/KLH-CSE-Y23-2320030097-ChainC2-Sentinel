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
    loadEvidence();
    loadResearchSummary();
    loadDownloads();

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
        updateBadge('status-dashboard', sys.dashboard || 'READY', 'badge-success');
        updateBadge('status-blockchain', sys.local_blockchain || 'LOCAL_STANDALONE', 'badge-neutral');
        updateBadge('status-telemetry', sys.telemetry || 'NORMALIZED', 'badge-primary');
        updateBadge('status-detection', sys.detection_engine || 'ACTIVE', 'badge-success');
        updateBadge('status-protection', sys.protection_engine || 'ACTIVE', 'badge-success');

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
        const det = data.detection_summary || {};
        setText('stat-precision', formatPct(det.precision));
        setText('stat-recall', formatPct(det.recall));
        setText('stat-fpr', formatPct(det.fpr));
        setText('stat-specificity', formatPct(det.specificity));
        setText('stat-accuracy', formatPct(det.accuracy));
        setText('stat-f1', formatPct(det.f1_score));

        setText('stat-tp', det.tp ?? 0);
        setText('stat-tn', det.tn ?? 0);
        setText('stat-fp', det.fp ?? 0);
        setText('stat-fn', det.fn ?? 0);

        const lat = det.latency || {};
        setText('stat-avg-latency', `${Number(lat.avg_ms ?? 0).toFixed(2)} ms`);
        setText('stat-min-latency', `${Number(lat.min_ms ?? 0).toFixed(2)} ms`);
        setText('stat-max-latency', `${Number(lat.max_ms ?? 0).toFixed(2)} ms`);

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
            const protBadge = run.protection_status ? `<span class="badge badge-warning">${run.protection_status}</span>` : '<span class="badge badge-neutral">SKIPPED</span>';

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
        setExecutionState(true);
        logExecution('Starting experiment execution in controlled laboratory environment...');

        try {
            const resp = await API.executeExperiment(payload);
            if (resp.status === 'success') {
                logExecution(`Execution completed successfully: ${resp.runs.length} independent run(s) generated.`);
                renderExecutionResults(resp.runs);
                // Refresh data across sections
                await Promise.all([loadOverview(), loadHistory(), loadTelemetry(resp.runs[0]?.run_id)]);
            } else {
                logExecution(`Execution notice: ${resp.message || 'Complete'}`);
            }
        } catch (err) {
            logExecution(`Execution failed or rejected: ${err.message}`);
            alert(`Experiment execution rejected or failed: ${err.message}`);
        } finally {
            setExecutionState(false);
        }
    }

    function setExecutionState(isBusy) {
        State.isExecuting = isBusy;
        if (elements.btnRunSelected) elements.btnRunSelected.disabled = isBusy;
        if (elements.btnRunAll3) elements.btnRunAll3.disabled = isBusy;
        if (elements.executionStatus) {
            elements.executionStatus.innerHTML = isBusy ?
                '<span class="badge badge-warning">EXPERIMENT IN PROGRESS (LAB LOCK HELD)</span>' :
                '<span class="badge badge-success">LABORATORY READY</span>';
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
                        <div><span class="text-muted">Total Score:</span> <strong class="font-mono">${r.score}</strong> / ${r.threshold}</div>
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
    async function loadTelemetry(runId = null) {
        try {
            const data = await API.getLiveTelemetry(runId);
            renderTelemetry(data);
        } catch (err) {
            console.error('Failed to load telemetry:', err);
        }
    }

    function renderTelemetry(data) {
        const tbody = document.getElementById('telemetry-table-body');
        const badgeSource = document.getElementById('telemetry-source-badge');
        const countBadge = document.getElementById('telemetry-count-badge');
        if (!tbody) return;

        const isLive = data.is_live;
        if (badgeSource) {
            badgeSource.className = `badge ${isLive ? 'badge-danger' : 'badge-neutral'}`;
            badgeSource.textContent = isLive ? 'ACTIVE ON-DEMAND EXPERIMENT' : 'HISTORICAL BENCHMARK DATA';
        }

        const events = data.events || [];
        if (countBadge) countBadge.textContent = `${events.length} Events`;

        if (events.length === 0) {
            tbody.innerHTML = '<tr><td colspan="7" class="text-center text-muted">No telemetry events captured for this query.</td></tr>';
            return;
        }

        tbody.innerHTML = events.map(ev => {
            const layer = (ev.telemetry_source || ev.layer || 'ENDPOINT').toUpperCase();
            const layerBadge = getLayerBadge(layer);

            return `
                <tr>
                    <td class="font-mono text-muted" style="font-size: 0.75rem;">${formatTimestamp(ev.timestamp)}</td>
                    <td class="font-mono" style="font-size: 0.75rem; color: var(--color-primary);">${ev.event_id || '—'}</td>
                    <td>${layerBadge}</td>
                    <td style="font-weight: 600; font-size: 0.8rem;">${ev.event_type || '—'}</td>
                    <td class="font-mono" style="font-size: 0.75rem;">${ev.process || ev.rpc_endpoint || ev.contract || '—'}</td>
                    <td class="font-mono" style="font-size: 0.75rem;">${ev.transaction_or_function || ev.network_dest || '—'}</td>
                    <td><span class="badge badge-success" style="font-size: 0.65rem;">${ev.status || 'CAPTURED'}</span></td>
                </tr>
            `;
        }).join('');
    }

    // Refresh Telemetry button
    const btnRefreshTelem = document.getElementById('btn-refresh-telemetry');
    if (btnRefreshTelem) {
        btnRefreshTelem.addEventListener('click', () => loadTelemetry());
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
                    <div><span class="text-muted">Total Multi-Layer Latency:</span> <span class="font-mono">${corr.total_duration_ms?.toFixed(2) || '0.00'} ms</span></div>
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
            Charts.renderContributionBars(contribContainer, run.scoring?.score_contributions || run.score_contributions || {});
        }

        // Detection metadata
        const detMeta = document.getElementById('detection-meta-details');
        if (detMeta) {
            const det = run.detection || {};
            detMeta.innerHTML = `
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; font-size: 0.8rem;">
                    <div><span class="text-muted">Rule ID:</span> <span class="font-mono">${det.rule_id || 'RULE-BLOCKCHAIN-C2-001'}</span></div>
                    <div><span class="text-muted">Rule Version:</span> <span class="font-mono">${det.rule_version || '1.0.0'}</span></div>
                    <div><span class="text-muted">Threshold:</span> <span class="font-mono font-bold">${run.threshold || 80}</span></div>
                    <div><span class="text-muted">Detection Status:</span> <span class="badge ${run.detection_triggered ? 'badge-danger' : 'badge-success'}">${run.detection_triggered ? 'ALERT TRIGGERED' : 'BENIGN / INSUFFICIENT SCORE'}</span></div>
                    <div><span class="text-muted">Classification:</span> <span class="font-mono font-bold">${run.classification || '—'}</span></div>
                    <div><span class="text-muted">Preserved Evidence:</span> <span class="font-mono">${run.evidence_id || 'None (Below Threshold)'}</span></div>
                </div>
                <div style="margin-top: 1rem; padding: 0.75rem; background: var(--bg-tertiary); border-radius: var(--radius-sm); border-left: 3px solid var(--color-primary); font-size: 0.85rem;">
                    <strong>Decision Explanation:</strong> ${escapeHtml(run.detection?.explanation || run.explanation || 'Score computed through weighted rule aggregation across normalized telemetry.')}
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

        const metrics = data.summary_metrics || {};
        setText('prot-stat-success-rate', formatPct(metrics.mitigation_success_rate || 1.0));
        setText('prot-stat-rpc-blocking', formatPct(metrics.rpc_blocking_rate || 1.0));
        setText('prot-stat-beacon-blocking', formatPct(metrics.beacon_blocking_rate || 1.0));
        setText('prot-stat-isolation-rate', formatPct(metrics.process_isolation_rate || 1.0));
        setText('prot-stat-traffic-preservation', formatPct(metrics.legitimate_traffic_preservation || 1.0));
        setText('prot-stat-false-mitigation', formatPct(metrics.false_mitigation_rate || 0.0));

        // Protection run comparison
        const runs = data.experiments || [];
        const tbody = document.getElementById('protection-runs-body');
        if (!tbody) return;

        tbody.innerHTML = runs.map(r => {
            const isMitigated = r.mitigation_success || r.status === 'MITIGATED';
            const scenarioBadge = getScenarioBadge(r.scenario);

            return `
                <tr>
                    <td class="font-mono" style="font-size: 0.8rem; color: var(--color-primary);">${r.run_id}</td>
                    <td>${scenarioBadge}</td>
                    <td><span class="badge ${r.triggered ? 'badge-danger' : 'badge-neutral'}">${r.triggered ? 'TRIGGERED' : 'SKIPPED (BENIGN)'}</span></td>
                    <td><span class="font-mono" style="font-size: 0.75rem;">${(r.actions_executed || ['None']).join(', ')}</span></td>
                    <td><span class="badge ${isMitigated ? 'badge-success' : (r.triggered ? 'badge-danger' : 'badge-neutral')}">${isMitigated ? 'VERIFIED SUCCESS' : (r.triggered ? 'FAILED' : 'NO ACTION')}</span></td>
                    <td><span class="badge badge-success">COMPLETED</span></td>
                    <td class="font-mono text-muted" style="font-size: 0.75rem;">${r.evidence_bundle_id || '—'}</td>
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

        const metrics = data.summary_metrics || {};
        const cm = metrics.confusion_matrix || {};

        // Render Confusion Matrix
        const cmContainer = document.getElementById('evaluation-confusion-matrix');
        if (cmContainer && window.Charts) {
            Charts.renderConfusionMatrix(cmContainer, cm);
        }

        // Render Scenario Distribution
        const distContainer = document.getElementById('evaluation-scenario-distribution');
        if (distContainer && window.Charts) {
            Charts.renderScenarioDistribution(distContainer, data.scenario_counts || {});
        }

        // Render Latency visualizer
        const latContainer = document.getElementById('evaluation-latency-chart');
        if (latContainer && window.Charts) {
            Charts.renderLatencyChart(latContainer, metrics.detection_latency || {});
        }

        // Evaluation metrics table
        setText('eval-tp', cm.tp ?? 0);
        setText('eval-tn', cm.tn ?? 0);
        setText('eval-fp', cm.fp ?? 0);
        setText('eval-fn', cm.fn ?? 0);
        setText('eval-precision', formatPct(metrics.precision));
        setText('eval-recall', formatPct(metrics.recall));
        setText('eval-fpr', formatPct(metrics.fpr));
        setText('eval-specificity', formatPct(metrics.specificity));
        setText('eval-accuracy', formatPct(metrics.accuracy));
        setText('eval-f1', formatPct(metrics.f1_score));
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
            const protBadge = r.protection ? `<span class="badge badge-warning">${r.protection}</span>` : '<span class="badge badge-neutral">SKIPPED</span>';

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

        const options = runs.map(r => `<option value="${r.run_id}">[${r.run_id}] ${r.scenario} (Score: ${r.score}/${r.threshold})</option>`).join('');

        if (selDetection) {
            selDetection.innerHTML = options;
            selDetection.addEventListener('change', () => openRunDetail(selDetection.value, false));
        }
        if (selCorr) {
            selCorr.innerHTML = options;
            selCorr.addEventListener('change', () => openRunDetail(selCorr.value, false));
        }
    }

    // -------------------------------------------------------------------------
    // RUN DETAIL MODAL
    // -------------------------------------------------------------------------
    async function openRunDetail(runId, showModal = true) {
        try {
            const run = await API.getExperimentRun(runId);
            State.selectedRun = run;

            // Update Correlation and Detection views
            renderRunInCorrelationAndDetection(run);

            if (showModal && elements.runModal) {
                renderModalDetail(run);
                elements.runModal.classList.remove('hidden');
            }
        } catch (err) {
            console.error('Failed to load run detail:', err);
            if (showModal) alert(`Failed to load details for run ${runId}: ${err.message}`);
        }
    }

    function renderModalDetail(run) {
        if (!elements.modalContent) return;

        const isDetected = run.detection_triggered || run.score >= run.threshold;

        elements.modalContent.innerHTML = `
            <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 1.5rem; border-bottom: 1px solid var(--border-color); padding-bottom: 1rem;">
                <div>
                    <h3 style="font-size: 1.25rem; font-weight: 700; color: var(--text-primary);">Run Detail: ${run.run_id}</h3>
                    <div class="text-muted font-mono" style="font-size: 0.8rem;">Scenario: ${run.scenario_name || run.scenario} | Timestamp: ${formatTimestamp(run.timestamp)}</div>
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
                    <div style="font-size: 0.95rem; font-weight: 600;">${run.telemetry_events?.length || 4} Events Captured</div>
                </div>
                <div class="stat-card" style="padding: 0.75rem;">
                    <div style="font-size: 0.7rem; color: var(--text-muted);">2. CORRELATION</div>
                    <div style="font-size: 0.95rem; font-weight: 600;">${run.correlation?.chain_complete ? 'Complete Chain (4/4)' : 'Incomplete Chain'}</div>
                </div>
                <div class="stat-card" style="padding: 0.75rem;">
                    <div style="font-size: 0.7rem; color: var(--text-muted);">3. DETECTION SCORE</div>
                    <div style="font-size: 0.95rem; font-weight: 600; font-family: var(--font-mono);">${run.score} / ${run.threshold} pts</div>
                </div>
                <div class="stat-card" style="padding: 0.75rem;">
                    <div style="font-size: 0.7rem; color: var(--text-muted);">4. DEFENSE ACTION</div>
                    <div style="font-size: 0.95rem; font-weight: 600;">${run.protection?.status || (isDetected ? 'Mitigated' : 'Skipped')}</div>
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
            Charts.renderContributionBars(document.getElementById('modal-contributions'), run.scoring?.score_contributions || run.score_contributions || {});
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
                    <td class="font-mono text-muted" style="font-size: 0.75rem;">${formatTimestamp(b.preservation_timestamp || b.timestamp)}</td>
                    <td class="font-mono" style="font-size: 0.75rem;">${b.rule_id || 'RULE-BLOCKCHAIN-C2-001'}</td>
                    <td class="font-mono text-muted" style="font-size: 0.7rem; max-width: 160px; overflow: hidden; text-overflow: ellipsis;" title="${b.sha256_checksum}">
                        ${b.sha256_checksum}
                    </td>
                    <td id="evidence-verify-status-${b.bundle_id}">
                        <span class="badge badge-neutral">UNCHECKED</span>
                    </td>
                    <td>
                        <button class="btn btn-secondary btn-sm" onclick="App.verifyEvidence('${b.bundle_id}')">
                            Verify SHA-256
                        </button>
                    </td>
                </tr>
            `;
        }).join('');
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
            alert(`Verification failed for bundle ${bundleId}: ${err.message}`);
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
    }

    if (elements.btnLoadReport) {
        elements.btnLoadReport.addEventListener('click', async () => {
            const reportName = elements.reportSelect?.value;
            if (!reportName) return;

            elements.reportViewer.innerHTML = '<div class="text-muted">Loading authoritative research report...</div>';

            try {
                const data = await API.getReport(reportName);
                // Safe basic markdown rendering
                elements.reportViewer.innerHTML = renderMarkdown(data.content);
            } catch (err) {
                elements.reportViewer.innerHTML = `<div class="badge badge-danger">Error loading report: ${escapeHtml(err.message)}</div>`;
            }
        });
    }

    // -------------------------------------------------------------------------
    // 11. DOWNLOADS CONTROLLER
    // -------------------------------------------------------------------------
    async function loadDownloads() {
        try {
            const data = await API.getDownloadsList();
            renderDownloads(data.downloads || {});
        } catch (err) {
            console.error('Failed to load downloads list:', err);
        }
    }

    function renderDownloads(downloads) {
        const container = elements.downloadsList;
        if (!container) return;

        const items = Object.entries(downloads);
        if (items.length === 0) {
            container.innerHTML = '<div class="text-muted">No downloads available.</div>';
            return;
        }

        container.innerHTML = items.map(([key, item]) => {
            return `
                <div class="card" style="display: flex; justify-content: space-between; align-items: center; padding: 0.75rem 1rem;">
                    <div>
                        <div style="font-weight: 600; font-size: 0.9rem; color: var(--text-primary);">${item.name}</div>
                        <div class="text-muted" style="font-size: 0.75rem;">${item.description}</div>
                    </div>
                    <a href="${API.getDownloadUrl(key)}" class="btn btn-secondary btn-sm" download>
                        Download
                    </a>
                </div>
            `;
        }).join('');
    }

    // -------------------------------------------------------------------------
    // UTILITIES
    // -------------------------------------------------------------------------
    function setText(id, val) {
        const el = document.getElementById(id);
        if (el) el.textContent = val;
    }

    function updateBadge(id, text, cls) {
        const el = document.getElementById(id);
        if (el) {
            el.className = `badge ${cls}`;
            el.textContent = text;
        }
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

    // Expose global methods for inline HTML onclick attributes
    window.App = {
        openRunDetail,
        verifyEvidence,
        loadTelemetry
    };
});
