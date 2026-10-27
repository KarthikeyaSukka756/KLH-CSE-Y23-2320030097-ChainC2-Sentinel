/**
 * ChainC2 Sentinel - Native Charts & Visualizations
 * Offline-compatible: Pure SVG / Canvas / Vanilla DOM
 */

const Charts = {
    /**
     * Renders a horizontal score meter with threshold indicator
     * @param {HTMLElement|string} container - Element or selector
     * @param {number} score - Achieved score (0 - 100)
     * @param {number} threshold - Detection threshold (e.g., 80)
     */
    renderScoreMeter(container, score, threshold = 80) {
        const el = typeof container === 'string' ? document.querySelector(container) : container;
        if (!el) return;

        score = Math.max(0, Math.min(100, Number(score) || 0));
        threshold = Math.max(0, Math.min(100, Number(threshold) || 80));

        const isDetected = score >= threshold;
        const barColor = isDetected ? 'var(--color-danger)' : (score > 40 ? 'var(--color-warning)' : 'var(--color-success)');

        el.innerHTML = `
            <div class="score-meter-wrap" style="width: 100%; padding: 0.5rem 0;">
                <div style="display: flex; justify-content: space-between; align-items: baseline; margin-bottom: 0.5rem;">
                    <div>
                        <span style="font-size: 1.75rem; font-weight: 700; color: ${barColor}; font-family: var(--font-mono);">${score}</span>
                        <span style="color: var(--text-muted); font-size: 0.85rem;"> / 100 pts</span>
                    </div>
                    <div style="text-align: right; font-size: 0.75rem;">
                        <span style="color: var(--text-muted);">Threshold: </span>
                        <span style="color: var(--color-warning); font-family: var(--font-mono); font-weight: 600;">${threshold}</span>
                        <span class="badge ${isDetected ? 'badge-danger' : 'badge-success'}" style="margin-left: 0.5rem;">
                            ${isDetected ? 'DETECTION TRIGGERED' : 'BELOW THRESHOLD'}
                        </span>
                    </div>
                </div>
                <div style="position: relative; height: 18px; background: var(--bg-tertiary); border-radius: 999px; overflow: visible; border: 1px solid var(--border-color);">
                    <!-- Fill bar -->
                    <div style="height: 100%; width: ${score}%; background: ${barColor}; border-radius: 999px; transition: width 0.5s ease;"></div>
                    <!-- Threshold marker -->
                    <div style="position: absolute; top: -4px; bottom: -4px; left: ${threshold}%; width: 3px; background: var(--color-warning); box-shadow: 0 0 6px rgba(245,158,11,0.6); z-index: 2;" title="Threshold: ${threshold}"></div>
                </div>
                <div style="display: flex; justify-content: space-between; font-size: 0.7rem; color: var(--text-muted); margin-top: 0.35rem; font-family: var(--font-mono);">
                    <span>0 (Benign)</span>
                    <span style="margin-left: ${threshold - 8}%;">▲ Threshold (${threshold})</span>
                    <span>100 (Synthetic C2)</span>
                </div>
            </div>
        `;
    },

    /**
     * Renders rule contribution breakdown bars
     * @param {HTMLElement|string} container - Element or selector
     * @param {Array|Object} contributions - Array or map of rule scores
     */
    renderContributionBars(container, contributions) {
        const el = typeof container === 'string' ? document.querySelector(container) : container;
        if (!el) return;

        // Authoritative 6-factor explainable scoring model in canonical order
        const canonicalRules = [
            { key: 'endpoint_context', name: 'Endpoint / Process Context', max: 10 },
            { key: 'rpc_interaction', name: 'RPC Gateway Interaction', max: 10 },
            { key: 'contract_interaction', name: 'Contract Interaction', max: 15 },
            { key: 'suspicious_retrieval', name: 'Suspicious Data Retrieval', max: 20 },
            { key: 'c2_configuration', name: 'C2 / Configuration Indicator', max: 20 },
            { key: 'network_followup', name: 'Subsequent Network Activity', max: 25 }
        ];

        const unmatchedExplanations = {
            'suspicious_retrieval': 'No suspicious retrieval detected. Target contract is not a command or dead-drop store.',
            'c2_configuration': 'No C2 command/configuration indicator detected.',
            'network_followup': 'No subsequent network activity observed.',
            'endpoint_context': 'No endpoint process context identified.',
            'rpc_interaction': 'No client JSON-RPC interaction observed.',
            'contract_interaction': 'No smart contract interaction observed on blockchain layer.'
        };

        let items = [];
        if (Array.isArray(contributions) && contributions.length > 0) {
            items = canonicalRules.map(cr => {
                const found = contributions.find(c => {
                    const r = (c.rule || c.rule_id || c.rule_name || c.key || '').toLowerCase();
                    return r === cr.key || r.includes(cr.key) || cr.key.includes(r);
                });
                if (found) {
                    const max = Number(found.weight || found.max_points || found.max || cr.max);
                    const isSatisfied = found.satisfied === true || (found.points !== undefined && Number(found.points) > 0);
                    const points = found.points !== undefined ? Number(found.points) : (isSatisfied ? max : 0);
                    const detail = isSatisfied ? (found.evidence_detail || '') : (unmatchedExplanations[cr.key] || found.evidence_detail || '');
                    return { name: cr.name, points, max, detail, satisfied: isSatisfied };
                }
                return { name: cr.name, points: 0, max: cr.max, detail: unmatchedExplanations[cr.key] || '', satisfied: false };
            });
        } else if (contributions && typeof contributions === 'object' && Object.keys(contributions).length > 0) {
            items = canonicalRules.map(cr => {
                let awarded = 0;
                if (contributions[cr.key] !== undefined) awarded = Number(contributions[cr.key]);
                const isSatisfied = awarded > 0;
                return {
                    name: cr.name,
                    points: awarded,
                    max: cr.max,
                    detail: isSatisfied ? '' : (unmatchedExplanations[cr.key] || ''),
                    satisfied: isSatisfied
                };
            });
        } else {
            // Guarantee canonical rules are always displayed even if empty
            items = canonicalRules.map(cr => ({
                name: cr.name,
                points: 0,
                max: cr.max,
                detail: unmatchedExplanations[cr.key] || '',
                satisfied: false
            }));
        }

        let html = '<div class="contribution-list" style="display: flex; flex-direction: column; gap: 0.75rem;">';
        items.forEach(item => {
            const pct = Math.min(100, Math.round((item.points / item.max) * 100));
            const isAwarded = item.satisfied || item.points > 0;
            const barColor = isAwarded ? 'var(--color-primary)' : 'var(--border-color)';
            const textColor = isAwarded ? 'var(--text-primary)' : 'var(--text-muted)';
            const badgeClass = isAwarded ? 'badge-primary' : 'badge-neutral';

            html += `
                <div class="contrib-item" style="display: flex; flex-direction: column; gap: 0.25rem;">
                    <div style="display: flex; justify-content: space-between; font-size: 0.8rem;">
                        <span style="color: ${textColor}; font-weight: ${isAwarded ? '600' : '400'};">${item.name}</span>
                        <div style="display: flex; align-items: center; gap: 0.5rem;">
                            <span class="badge ${badgeClass}" style="font-size: 0.7rem;">${isAwarded ? 'MATCHED' : 'UNMATCHED'}</span>
                            <span style="font-family: var(--font-mono); font-weight: 600; color: ${textColor}; min-width: 45px; text-align: right;">
                                +${item.points} / ${item.max}
                            </span>
                        </div>
                    </div>
                    <div style="height: 6px; background: var(--bg-tertiary); border-radius: 999px; overflow: hidden;">
                        <div style="height: 100%; width: ${pct}%; background: ${barColor}; border-radius: 999px;"></div>
                    </div>
                    ${item.detail ? `<div class="font-mono text-muted" style="font-size: 0.7rem;">${item.detail}</div>` : ''}
                </div>
            `;
        });
        html += '</div>';

        el.innerHTML = html;
    },

    /**
     * Renders an interactive 2x2 Confusion Matrix
     * @param {HTMLElement|string} container
     * @param {Object} cm - {tp, tn, fp, fn}
     */
    renderConfusionMatrix(container, cm = {}) {
        const el = typeof container === 'string' ? document.querySelector(container) : container;
        if (!el) return;

        const tp = Number(cm.tp ?? cm.true_positives ?? 0);
        const tn = Number(cm.tn ?? cm.true_negatives ?? 0);
        const fp = Number(cm.fp ?? cm.false_positives ?? 0);
        const fn = Number(cm.fn ?? cm.false_negatives ?? 0);
        const total = tp + tn + fp + fn;

        const tpPct = total > 0 ? ((tp / total) * 100).toFixed(1) : '0';
        const tnPct = total > 0 ? ((tn / total) * 100).toFixed(1) : '0';
        const fpPct = total > 0 ? ((fp / total) * 100).toFixed(1) : '0';
        const fnPct = total > 0 ? ((fn / total) * 100).toFixed(1) : '0';

        el.innerHTML = `
            <div class="matrix-grid" style="display: grid; grid-template-columns: 110px 1fr 1fr; gap: 6px; font-size: 0.8rem; text-align: center;">
                <div></div>
                <div style="font-weight: 600; color: var(--text-secondary); padding-bottom: 4px;">Predicted C2</div>
                <div style="font-weight: 600; color: var(--text-secondary); padding-bottom: 4px;">Predicted Benign</div>

                <div style="font-weight: 600; color: var(--text-secondary); display: flex; align-items: center; justify-content: flex-end; padding-right: 8px;">
                    Actual C2
                </div>
                <div class="matrix-cell" style="background: rgba(16, 185, 129, 0.12); border: 1px solid var(--color-success); border-radius: var(--radius-sm); padding: 1rem 0.5rem;">
                    <div style="font-size: 1.35rem; font-weight: 700; color: var(--color-success); font-family: var(--font-mono);">${tp}</div>
                    <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 2px;">True Positive (TP)</div>
                    <div style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono);">${tpPct}%</div>
                </div>
                <div class="matrix-cell" style="background: rgba(244, 63, 94, 0.08); border: 1px solid ${fn > 0 ? 'var(--color-danger)' : 'var(--border-color)'}; border-radius: var(--radius-sm); padding: 1rem 0.5rem;">
                    <div style="font-size: 1.35rem; font-weight: 700; color: ${fn > 0 ? 'var(--color-danger)' : 'var(--text-muted)'}; font-family: var(--font-mono);">${fn}</div>
                    <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 2px;">False Negative (FN)</div>
                    <div style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono);">${fnPct}%</div>
                </div>

                <div style="font-weight: 600; color: var(--text-secondary); display: flex; align-items: center; justify-content: flex-end; padding-right: 8px;">
                    Actual Benign
                </div>
                <div class="matrix-cell" style="background: rgba(244, 63, 94, 0.08); border: 1px solid ${fp > 0 ? 'var(--color-danger)' : 'var(--border-color)'}; border-radius: var(--radius-sm); padding: 1rem 0.5rem;">
                    <div style="font-size: 1.35rem; font-weight: 700; color: ${fp > 0 ? 'var(--color-danger)' : 'var(--text-muted)'}; font-family: var(--font-mono);">${fp}</div>
                    <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 2px;">False Positive (FP)</div>
                    <div style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono);">${fpPct}%</div>
                </div>
                <div class="matrix-cell" style="background: rgba(16, 185, 129, 0.12); border: 1px solid var(--color-success); border-radius: var(--radius-sm); padding: 1rem 0.5rem;">
                    <div style="font-size: 1.35rem; font-weight: 700; color: var(--color-success); font-family: var(--font-mono);">${tn}</div>
                    <div style="font-size: 0.7rem; color: var(--text-muted); margin-top: 2px;">True Negative (TN)</div>
                    <div style="font-size: 0.7rem; color: var(--text-muted); font-family: var(--font-mono);">${tnPct}%</div>
                </div>
            </div>
        `;
    },

    /**
     * Renders scenario distribution breakdown (SVG bar / segment)
     * @param {HTMLElement|string} container
     * @param {Object} counts - {scenario_a, scenario_b, scenario_c, total}
     */
    renderScenarioDistribution(container, counts = {}) {
        const el = typeof container === 'string' ? document.querySelector(container) : container;
        if (!el) return;

        let a = Number(counts.scenario_a_benign || counts.scenario_a || counts.A || 0);
        let b = Number(counts.scenario_b_synthetic_c2 || counts.scenario_b_c2_like || counts.scenario_b || counts.B || 0);
        let c = Number(counts.scenario_c_legitimate_dapp || counts.scenario_c || counts.C || 0);

        if (a === 0 && b === 0 && c === 0 && typeof counts === 'object') {
            for (const [k, v] of Object.entries(counts)) {
                const kl = k.toLowerCase();
                if (kl.includes('scenario_a') || kl === 'a') a += Number(v);
                else if (kl.includes('scenario_b') || kl === 'b') b += Number(v);
                else if (kl.includes('scenario_c') || kl === 'c') c += Number(v);
            }
        }
        const total = a + b + c || 1;

        const aPct = ((a / total) * 100).toFixed(1);
        const bPct = ((b / total) * 100).toFixed(1);
        const cPct = ((c / total) * 100).toFixed(1);

        el.innerHTML = `
            <div style="display: flex; flex-direction: column; gap: 0.75rem;">
                <div style="display: flex; height: 22px; border-radius: var(--radius-sm); overflow: hidden; border: 1px solid var(--border-color);">
                    <div style="width: ${aPct}%; background: var(--color-primary); display: flex; align-items: center; justify-content: center; font-size: 0.7rem; font-weight: 600; color: #fff;" title="Scenario A: ${a} (${aPct}%)">${a > 0 ? a : ''}</div>
                    <div style="width: ${bPct}%; background: var(--color-danger); display: flex; align-items: center; justify-content: center; font-size: 0.7rem; font-weight: 600; color: #fff;" title="Scenario B: ${b} (${bPct}%)">${b > 0 ? b : ''}</div>
                    <div style="width: ${cPct}%; background: var(--color-secondary); display: flex; align-items: center; justify-content: center; font-size: 0.7rem; font-weight: 600; color: #fff;" title="Scenario C: ${c} (${cPct}%)">${c > 0 ? c : ''}</div>
                </div>
                <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 0.5rem; font-size: 0.75rem;">
                    <div style="border-left: 3px solid var(--color-primary); padding-left: 6px;">
                        <div style="color: var(--text-muted); font-size: 0.7rem;">Scenario A (Benign)</div>
                        <div style="font-weight: 600; font-family: var(--font-mono);">${a} runs (${aPct}%)</div>
                    </div>
                    <div style="border-left: 3px solid var(--color-danger); padding-left: 6px;">
                        <div style="color: var(--text-muted); font-size: 0.7rem;">Scenario B (Synth C2)</div>
                        <div style="font-weight: 600; font-family: var(--font-mono);">${b} runs (${bPct}%)</div>
                    </div>
                    <div style="border-left: 3px solid var(--color-secondary); padding-left: 6px;">
                        <div style="color: var(--text-muted); font-size: 0.7rem;">Scenario C (DApp Base)</div>
                        <div style="font-weight: 600; font-family: var(--font-mono);">${c} runs (${cPct}%)</div>
                    </div>
                </div>
            </div>
        `;
    },

    /**
     * Renders detection latency visualizer
     * @param {HTMLElement|string} container
     * @param {Object} latencyData - {avg_latency_ms, min_latency_ms, max_latency_ms}
     */
    renderLatencyChart(container, latencyData = {}) {
        const el = typeof container === 'string' ? document.querySelector(container) : container;
        if (!el) return;

        const formatLat = (val) => {
            const n = Number(val);
            if (isNaN(n) || n === 0) return '0.000000';
            return n.toFixed(6);
        };

        const avg = formatLat(
            latencyData.average_ms ??
            latencyData.avg_ms ??
            latencyData.avg_latency_ms ??
            latencyData.average_latency_ms ??
            latencyData.containment_latency_avg_ms ??
            0
        );
        const min = formatLat(
            latencyData.min_ms ??
            latencyData.min_latency_ms ??
            latencyData.containment_latency_min_ms ??
            0
        );
        const max = formatLat(
            latencyData.max_ms ??
            latencyData.max_latency_ms ??
            latencyData.containment_latency_max_ms ??
            0
        );

        el.innerHTML = `
            <div style="display: grid; grid-template-columns: repeat(3, 1fr); gap: 1rem; text-align: center;">
                <div class="stat-card" style="padding: 0.75rem;">
                    <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Min Latency</div>
                    <div style="font-size: 1.25rem; font-weight: 700; font-family: var(--font-mono); color: var(--color-success);">${min} ms</div>
                </div>
                <div class="stat-card" style="padding: 0.75rem; border-color: var(--color-primary);">
                    <div style="font-size: 0.7rem; color: var(--color-primary); text-transform: uppercase; font-weight: 600;">Mean Latency</div>
                    <div style="font-size: 1.5rem; font-weight: 700; font-family: var(--font-mono); color: var(--text-primary);">${avg} ms</div>
                </div>
                <div class="stat-card" style="padding: 0.75rem;">
                    <div style="font-size: 0.7rem; color: var(--text-muted); text-transform: uppercase;">Max Latency</div>
                    <div style="font-size: 1.25rem; font-weight: 700; font-family: var(--font-mono); color: var(--color-warning);">${max} ms</div>
                </div>
            </div>
        `;
    },

    /**
     * Renders cross-layer correlation visual chain (Endpoint -> RPC -> Blockchain -> Network)
     * @param {HTMLElement|string} container
     * @param {Object} correlation - correlation details with stages & transitions
     */
    renderCorrelationChain(container, correlation = {}) {
        const el = typeof container === 'string' ? document.querySelector(container) : container;
        if (!el) return;

        const stages = Array.isArray(correlation.stages) ? correlation.stages : [];
        const transitions = Array.isArray(correlation.transitions) ? correlation.transitions : [];
        const stagesUpper = stages.map(s => String(s).toUpperCase());
        const isComplete = correlation.chain_complete === true ||
                           correlation.is_complete_chain === true ||
                           (stagesUpper.length >= 4 && stagesUpper.includes('NETWORK'));

        let html = `
            <div class="correlation-graph" style="display: flex; flex-direction: column; gap: 1rem; padding: 1rem 0;">
                <div style="display: flex; align-items: center; justify-content: space-between; margin-bottom: 0.5rem;">
                    <div style="font-size: 0.85rem; font-weight: 600; color: var(--text-primary);">
                        Cross-Layer Telemetry Sequence
                    </div>
                    <div>
                        <span class="badge ${isComplete ? 'badge-danger' : 'badge-neutral'}">
                            ${isComplete ? '4/4 STAGES OBSERVED' : `${stages.length} OBSERVED STAGES`}
                        </span>
                    </div>
                </div>
                <div style="display: flex; align-items: center; justify-content: space-between; position: relative; gap: 0.5rem; flex-wrap: wrap;">
        `;

        const layerMeta = [
            { id: 'ENDPOINT', name: 'Endpoint Process', desc: 'Process execution & parentage', icon: '💻' },
            { id: 'RPC', name: 'JSON-RPC Interaction', desc: 'RPC payload & method call', icon: '🔌' },
            { id: 'BLOCKCHAIN', name: 'Smart Contract', desc: 'Contract call & state fetch', icon: '⛓️' },
            { id: 'NETWORK', name: 'Network Egress', desc: 'Egress beacon & target packet', icon: '🌐' }
        ];

        layerMeta.forEach((layer, idx) => {
            const observed = stagesUpper.includes(layer.id);
            const borderColor = observed ? 'var(--color-primary)' : 'var(--border-color)';
            const bgColor = observed ? 'rgba(59, 130, 246, 0.08)' : 'var(--bg-tertiary)';
            const opacity = observed ? '1' : '0.5';

            html += `
                <div style="flex: 1; min-width: 140px; background: ${bgColor}; border: 1px solid ${borderColor}; border-radius: var(--radius-md); padding: 0.75rem; opacity: ${opacity}; text-align: center;">
                    <div style="font-size: 1.25rem; margin-bottom: 0.25rem;">${layer.icon}</div>
                    <div style="font-size: 0.75rem; font-weight: 700; color: var(--text-primary);">${layer.name}</div>
                    <div style="font-size: 0.65rem; color: var(--text-muted); margin-top: 2px;">${layer.desc}</div>
                    <div style="margin-top: 0.5rem;">
                        <span class="badge ${observed ? 'badge-primary' : 'badge-neutral'}" style="font-size: 0.65rem;">
                            ${observed ? 'OBSERVED' : 'NOT PRESENT'}
                        </span>
                    </div>
                </div>
            `;

            if (idx < layerMeta.length - 1) {
                const trans = transitions[idx] || {};
                const deltaMs = trans.delta_ms !== undefined ? `${trans.delta_ms.toFixed(1)} ms` : 'Δt';
                html += `
                    <div style="display: flex; flex-direction: column; align-items: center; justify-content: center; padding: 0 4px;">
                        <span style="font-size: 0.7rem; font-family: var(--font-mono); color: var(--color-secondary); font-weight: 600;">${deltaMs}</span>
                        <span style="color: var(--text-muted); font-size: 1rem;">➔</span>
                    </div>
                `;
            }
        });

        html += `
                </div>
            </div>
        `;

        el.innerHTML = html;
    }
};

window.Charts = Charts;
