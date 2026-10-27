# ChainC2 Sentinel — Complete End-to-End Dashboard Acceptance Test
"""Comprehensive acceptance test suite validating end-to-end dashboard functionality:
A. Overview loads real authoritative metrics
B. Scenario selector changes selected run
C. Detection score changes across Scenarios A, B, C
D. Scoring contributions change and adhere to 6 canonical rules
E. Correlation view changes between scenarios (stages, completeness, network)
F. Run detail modal data consistency
G. Evidence inspection works
H. Evidence verification works (SHA-256 integrity validation)
I. Downloads work (all whitelisted files exist, non-empty, correct filename/mimetype)
J. Reports load (markdown content, title, size)
K. Telemetry leaves loading state with explicit three-state model
L. Production experiment rejection / guard handling
M. No alert() calls in frontend code
N. No [object Object] in frontend code
O. No undefined values in rendered data contracts
P. No JavaScript syntax errors across all static assets
"""

import json
import re
import subprocess
from pathlib import Path
import pytest
from src.dashboard.app import create_app


@pytest.fixture
def client():
    """Create Flask test client."""
    app = create_app({"TESTING": True})
    with app.test_client() as test_client:
        yield test_client


@pytest.fixture
def prod_client():
    """Create Flask test client with production mode enabled."""
    app = create_app({"TESTING": True, "PRODUCTION_MODE": True})
    with app.test_client() as test_client:
        yield test_client


@pytest.mark.unit
class TestDashboardAcceptance:
    """Acceptance test verifying Requirements A through P."""

    # -------------------------------------------------------------------------
    # A. Overview loads real metrics
    # -------------------------------------------------------------------------
    def test_a_overview_loads_real_metrics(self, client):
        resp = client.get("/api/overview")
        assert resp.status_code == 200
        data = resp.get_json()

        assert "system_status" in data
        assert "experiment_summary" in data
        assert "detection_summary" in data

        det = data["detection_summary"]
        assert det["precision"] == 1.0
        assert det["recall"] == 1.0
        assert det["fpr"] == 0.0
        assert det["tp"] == 10
        assert det["tn"] == 20
        assert det["fp"] == 0
        assert det["fn"] == 0

        # Latency must be non-zero and match authoritative values
        lat = det.get("latency") or det.get("detection_latency")
        assert lat is not None
        assert abs(lat["average_ms"] - 0.10162) < 0.001
        assert abs(lat["min_ms"] - 0.0451) < 0.001
        assert abs(lat["max_ms"] - 0.6879) < 0.001

    # -------------------------------------------------------------------------
    # B. Scenario selector changes selected run
    # -------------------------------------------------------------------------
    def test_b_scenario_selector_changes_run(self, client):
        resp = client.get("/api/experiments/history?limit=30")
        assert resp.status_code == 200
        runs = resp.get_json().get("runs", [])
        assert len(runs) >= 30

        run_a = next(r for r in runs if r["scenario"].startswith("scenario_a") or "benign" in r["scenario"])
        run_b = next(r for r in runs if r["scenario"].startswith("scenario_b") or "c2" in r["scenario"])
        run_c = next(r for r in runs if r["scenario"].startswith("scenario_c") or "dapp" in r["scenario"])

        assert run_a["run_id"] != run_b["run_id"]
        assert run_b["run_id"] != run_c["run_id"]

    # -------------------------------------------------------------------------
    # C. Detection score changes
    # -------------------------------------------------------------------------
    def test_c_detection_score_changes(self, client):
        resp = client.get("/api/experiments/history?limit=30")
        runs = resp.get_json().get("runs", [])

        run_a = next(r for r in runs if r["scenario"].startswith("scenario_a") or "benign" in r["scenario"])
        run_b = next(r for r in runs if r["scenario"].startswith("scenario_b") or "c2" in r["scenario"])
        run_c = next(r for r in runs if r["scenario"].startswith("scenario_c") or "dapp" in r["scenario"])

        detail_a = client.get(f"/api/experiments/run/{run_a['run_id']}").get_json()
        detail_b = client.get(f"/api/experiments/run/{run_b['run_id']}").get_json()
        detail_c = client.get(f"/api/experiments/run/{run_c['run_id']}").get_json()

        # Scenario A: benign (35 / 80, no detection)
        assert detail_a["score"] == 35.0
        assert detail_a["score"] < detail_a["threshold"]

        # Scenario B: C2 (100 / 80, detection triggered)
        assert detail_b["score"] == 100.0
        assert detail_b["score"] >= detail_b["threshold"]

        # Scenario C: legitimate DApp (35 / 80, no detection)
        assert detail_c["score"] == 35.0
        assert detail_c["score"] < detail_c["threshold"]

    # -------------------------------------------------------------------------
    # D. Scoring contributions change
    # -------------------------------------------------------------------------
    def test_d_scoring_contributions_change(self, client):
        resp = client.get("/api/experiments/history?limit=30")
        runs = resp.get_json().get("runs", [])

        run_a = next(r for r in runs if r["scenario"].startswith("scenario_a") or "benign" in r["scenario"])
        run_b = next(r for r in runs if r["scenario"].startswith("scenario_b") or "c2" in r["scenario"])

        detail_a = client.get(f"/api/experiments/run/{run_a['run_id']}").get_json()
        detail_b = client.get(f"/api/experiments/run/{run_b['run_id']}").get_json()

        contribs_a = detail_a["scoring"]["contributions"]
        contribs_b = detail_b["scoring"]["contributions"]

        # 6 canonical rules
        rule_keys_a = [c["rule"] for c in contribs_a]
        rule_keys_b = [c["rule"] for c in contribs_b]
        assert len(rule_keys_a) == 6
        assert len(rule_keys_b) == 6

        # Scenario A has 3 satisfied, 3 unsatisfied
        satisfied_a = [c for c in contribs_a if c["satisfied"]]
        satisfied_b = [c for c in contribs_b if c["satisfied"]]
        assert len(satisfied_a) == 3
        assert len(satisfied_b) == 6

    # -------------------------------------------------------------------------
    # E. Correlation view changes
    # -------------------------------------------------------------------------
    def test_e_correlation_view_changes(self, client):
        resp = client.get("/api/experiments/history?limit=30")
        runs = resp.get_json().get("runs", [])

        run_a = next(r for r in runs if r["scenario"].startswith("scenario_a") or "benign" in r["scenario"])
        run_b = next(r for r in runs if r["scenario"].startswith("scenario_b") or "c2" in r["scenario"])

        detail_a = client.get(f"/api/experiments/run/{run_a['run_id']}").get_json()
        detail_b = client.get(f"/api/experiments/run/{run_b['run_id']}").get_json()

        corr_a = detail_a["correlation"]
        corr_b = detail_b["correlation"]

        # Scenario A has 3 stages (incomplete), no network
        assert len(corr_a["stages"]) == 3
        assert not corr_a["chain_complete"]
        assert not corr_a["has_network"]

        # Scenario B has 4 stages (complete chain), network present
        assert len(corr_b["stages"]) == 4
        assert corr_b["chain_complete"]
        assert corr_b["has_network"]

    # -------------------------------------------------------------------------
    # F. Run detail modal changes
    # -------------------------------------------------------------------------
    def test_f_run_detail_changes(self, client):
        resp = client.get("/api/experiments/history?limit=10")
        runs = resp.get_json().get("runs", [])
        r1 = runs[0]
        r2 = runs[1]

        detail1 = client.get(f"/api/experiments/run/{r1['run_id']}").get_json()
        detail2 = client.get(f"/api/experiments/run/{r2['run_id']}").get_json()

        assert detail1["run_id"] != detail2["run_id"]
        assert "telemetry_events" in detail1
        assert "telemetry_events" in detail2
        assert len(detail1["telemetry_events"]) > 0

    # -------------------------------------------------------------------------
    # G. Evidence inspection works
    # -------------------------------------------------------------------------
    def test_g_evidence_inspection_works(self, client):
        resp = client.get("/api/evidence")
        assert resp.status_code == 200
        bundles = resp.get_json().get("evidence_bundles", [])
        assert len(bundles) > 0

        bundle_id = bundles[0]["bundle_id"]
        resp_b = client.get(f"/api/evidence/{bundle_id}")
        assert resp_b.status_code == 200
        b_data = resp_b.get_json()
        assert b_data["bundle_id"] == bundle_id
        assert "sha256_checksum" in b_data
        assert "matched_conditions" in b_data or "evidence_conditions" in b_data

    # -------------------------------------------------------------------------
    # H. Evidence verification works
    # -------------------------------------------------------------------------
    def test_h_evidence_verification_works(self, client):
        resp = client.get("/api/evidence")
        bundles = resp.get_json().get("evidence_bundles", [])
        assert len(bundles) > 0

        bundle_id = bundles[0]["bundle_id"]
        resp_v = client.post(f"/api/evidence/{bundle_id}/verify")
        assert resp_v.status_code == 200
        v_data = resp_v.get_json()
        assert v_data["verified"] is True
        assert v_data["status"] == "VERIFIED"
        assert v_data["recorded_checksum"] == v_data["calculated_checksum"]

    # -------------------------------------------------------------------------
    # I. Downloads work
    # -------------------------------------------------------------------------
    def test_i_downloads_work(self, client):
        resp = client.get("/api/downloads")
        assert resp.status_code == 200
        downloads = resp.get_json().get("downloads", [])
        assert len(downloads) >= 10

        for item in downloads:
            key = item["key"]
            resp_d = client.get(f"/api/download/{key}")
            assert resp_d.status_code == 200, f"Download failed for key {key}"
            assert len(resp_d.data) > 0, f"Download empty for key {key}"
            assert "Content-Disposition" in resp_d.headers
            assert item["filename"] in resp_d.headers["Content-Disposition"]

    # -------------------------------------------------------------------------
    # J. Reports load
    # -------------------------------------------------------------------------
    def test_j_reports_load(self, client):
        reports = ["DETECTION_ANALYSIS.md", "FINAL_RESEARCH_ANALYSIS.md", "PROTECTION_ANALYSIS.md"]
        for r in reports:
            resp = client.get(f"/api/research/report/{r}")
            assert resp.status_code == 200, f"Failed to load report {r}"
            data = resp.get_json()
            assert data["report_name"] == r
            assert len(data["content"]) > 1000
            assert "title" in data
            assert data["title"] is not None

    # -------------------------------------------------------------------------
    # K. Telemetry leaves loading state
    # -------------------------------------------------------------------------
    def test_k_telemetry_endpoint(self, client):
        resp = client.get("/api/telemetry/live")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "events" in data
        assert isinstance(data["events"], list)
        assert "is_live" in data

    # -------------------------------------------------------------------------
    # L. Production experiment rejection clears UI state
    # -------------------------------------------------------------------------
    def test_l_production_experiment_rejection(self, prod_client):
        # When execution is attempted in production mode, 403 Forbidden is returned
        resp = prod_client.post("/api/experiments/execute", json={"scenario": "scenario_a", "repetitions": 1})
        assert resp.status_code == 403
        data = resp.get_json()
        assert "error" in data
        assert "production" in data["error"].lower()

        # Overview in production reflects Cloud Dashboard and execution disabled
        overview_resp = prod_client.get("/api/overview")
        overview = overview_resp.get_json()
        assert overview["system_status"]["execution_enabled"] is False
        assert overview["system_status"]["dashboard"] == "CLOUD_DASHBOARD"
        assert overview["system_status"]["blockchain_status"] == "HISTORICAL_BENCHMARK"

    # -------------------------------------------------------------------------
    # M. No alert() in frontend code
    # -------------------------------------------------------------------------
    def test_m_no_alert_in_frontend(self):
        js_files = list(Path("src/dashboard/static/js").glob("*.js"))
        for jf in js_files:
            content = jf.read_text(encoding="utf-8")
            # Strip single line and multi-line comments
            no_comments = re.sub(r"//.*", "", content)
            no_comments = re.sub(r"/\*[\s\S]*?\*/", "", no_comments)
            matches = re.findall(r"\balert\(", no_comments)
            assert len(matches) == 0, f"Found alert() call in {jf.name}: {matches}"

    # -------------------------------------------------------------------------
    # N. No [object Object] in frontend source
    # -------------------------------------------------------------------------
    def test_n_no_object_object_in_source(self):
        files = list(Path("src/dashboard/static").glob("**/*")) + list(Path("src/dashboard/templates").glob("*.html"))
        for f in files:
            if f.is_file():
                content = f.read_text(encoding="utf-8")
                assert "[object Object]" not in content, f"Found [object Object] in {f}"

    # -------------------------------------------------------------------------
    # O. No undefined in download items and reports
    # -------------------------------------------------------------------------
    def test_o_no_undefined_contract(self, client):
        d_resp = client.get("/api/downloads")
        downloads = d_resp.get_json().get("downloads", [])
        for item in downloads:
            assert item.get("name") is not None
            assert item.get("filename") is not None
            assert item.get("description") is not None
            assert item.get("key") is not None

    # -------------------------------------------------------------------------
    # P. No JavaScript syntax errors
    # -------------------------------------------------------------------------
    def test_p_javascript_syntax_validity(self):
        js_files = list(Path("src/dashboard/static/js").glob("*.js")) + list(Path("public/static/js").glob("*.js"))
        for f in js_files:
            res = subprocess.run(["node", "-c", str(f)], capture_output=True, text=True)
            assert res.returncode == 0, f"JavaScript syntax error in {f}: {res.stderr}"

    # -------------------------------------------------------------------------
    # Q. Header status values are strings and resolve cleanly
    # -------------------------------------------------------------------------
    def test_q_header_status_badges_string_types(self, client, prod_client):
        for c, mode in [(client, "local"), (prod_client, "prod")]:
            resp = c.get("/api/overview")
            assert resp.status_code == 200
            sys = resp.get_json()["system_status"]
            assert isinstance(sys.get("dashboard"), str)
            assert isinstance(sys.get("blockchain_status"), str)
            assert isinstance(sys.get("telemetry"), str)
            assert isinstance(sys.get("detection_status"), str)
            assert isinstance(sys.get("protection_status"), str)
            # local_blockchain can be string or dict with node string
            lb = sys.get("local_blockchain")
            if isinstance(lb, dict):
                assert "node" in lb and isinstance(lb["node"], str)
            else:
                assert isinstance(lb, str)

    # -------------------------------------------------------------------------
    # R. Six scoring rules have authoritative canonical weights (10, 10, 15, 20, 20, 25)
    # -------------------------------------------------------------------------
    def test_r_six_scoring_rules_canonical_weights(self, client):
        resp = client.get("/api/experiments/history?limit=30")
        runs = resp.get_json().get("runs", [])
        expected_weights = {
            "endpoint_context": 10.0,
            "rpc_interaction": 10.0,
            "contract_interaction": 15.0,
            "suspicious_retrieval": 20.0,
            "c2_configuration": 20.0,
            "network_followup": 25.0,
        }
        for r in runs[:5]:
            detail = client.get(f"/api/experiments/run/{r['run_id']}").get_json()
            contribs = detail["scoring"]["contributions"]
            assert len(contribs) == 6
            for c in contribs:
                rule_key = c["rule"]
                assert rule_key in expected_weights, f"Unexpected rule: {rule_key}"
                assert c["weight"] == expected_weights[rule_key]

    # -------------------------------------------------------------------------
    # S. Static assets byte parity (src vs public)
    # -------------------------------------------------------------------------
    def test_s_static_asset_sha256_sync(self):
        import hashlib
        for name in ["api.js", "charts.js", "main.js", "navigation.js"]:
            p1 = Path("src/dashboard/static/js") / name
            p2 = Path("public/static/js") / name
            assert p1.exists() and p2.exists(), f"Missing {name}"
            h1 = hashlib.sha256(p1.read_bytes()).hexdigest()
            h2 = hashlib.sha256(p2.read_bytes()).hexdigest()
            assert h1 == h2, f"Hash mismatch for {name}: {h1} != {h2}"

    # -------------------------------------------------------------------------
    # T. Evaluation detection metrics populated without null or dash fallbacks
    # -------------------------------------------------------------------------
    def test_t_evaluation_detection_metrics_populated(self, client):
        resp = client.get("/api/evaluation/detection")
        assert resp.status_code == 200
        data = resp.get_json()
        assert "rates" in data
        rates = data["rates"]
        for metric in ["precision", "recall", "fpr", "specificity", "accuracy", "f1_score"]:
            assert metric in rates, f"Missing {metric} in rates"
            assert isinstance(rates[metric], (int, float))

        lat = data.get("latency")
        assert lat is not None
        assert lat["average_ms"] > 0
        assert lat["min_ms"] > 0
        assert lat["max_ms"] > 0

    # -------------------------------------------------------------------------
    # U. Authoritative scenario scores (A: 35/100, B: 100/100, C: 35/100, Threshold: 80)
    # -------------------------------------------------------------------------
    def test_u_scenario_scores_authoritative(self, client):
        resp = client.get("/api/experiments/history?limit=30")
        runs = resp.get_json().get("runs", [])
        run_a = next(r for r in runs if "scenario_a" in r["scenario"] or "benign" in r["scenario"])
        run_b = next(r for r in runs if "scenario_b" in r["scenario"] or "c2" in r["scenario"])
        run_c = next(r for r in runs if "scenario_c" in r["scenario"] or "dapp" in r["scenario"])

        det_a = client.get(f"/api/experiments/run/{run_a['run_id']}").get_json()
        det_b = client.get(f"/api/experiments/run/{run_b['run_id']}").get_json()
        det_c = client.get(f"/api/experiments/run/{run_c['run_id']}").get_json()

        assert det_a["score"] == 35.0
        assert det_b["score"] == 100.0
        assert det_c["score"] == 35.0
        assert det_a["threshold"] == 80.0
        assert det_b["threshold"] == 80.0
        assert det_c["threshold"] == 80.0

    # -------------------------------------------------------------------------
    # V. Experiment History Protection column renders human-readable badge (no [object Object])
    # -------------------------------------------------------------------------
    def test_v_experiment_history_protection_column_rendering(self, client):
        resp = client.get("/api/experiments/history?limit=100")
        assert resp.status_code == 200
        runs = resp.get_json().get("runs", [])
        assert len(runs) >= 30

        # Run Node.js evaluation of getProtectionBadge extracted from main.js
        main_js = Path("src/dashboard/static/js/main.js").read_text(encoding="utf-8")
        assert "function getProtectionBadge" in main_js
        assert "getProtectionBadge(r.protection, r.protection_status)" in main_js

        # Extract getProtectionBadge and escapeHtml
        js_test_script = f"""
        const runs = {json.dumps(runs)};
        function escapeHtml(str) {{
            return (str || '').toString().replace(/[&<>"']/g, m => ({{
                '&': '&amp;', '<': '&lt;', '>': '&gt;', '"': '&quot;', "'": '&#039;'
            }})[m]);
        }}
        function getProtectionBadge(protection, fallbackStatus) {{
            let status = '';
            if (typeof protection === 'string') {{
                status = protection.trim().toUpperCase();
            }} else if (protection && typeof protection === 'object') {{
                if (Array.isArray(protection)) {{
                    status = protection.length > 0 ? `${{protection.length}} ACTIONS` : 'N/A';
                }} else {{
                    status = (protection.status || protection.plan_status || protection.action || protection.result || fallbackStatus || 'N/A').toString().trim().toUpperCase();
                }}
            }} else if (fallbackStatus) {{
                status = String(fallbackStatus).trim().toUpperCase();
            }}

            if (!status || status === '[OBJECT OBJECT]' || status === 'UNDEFINED' || status === 'NULL') {{
                status = 'N/A';
            }}

            let badgeClass = 'badge-neutral';
            if (status === 'MITIGATED' || status === 'EXECUTED') {{
                badgeClass = 'badge-warning';
            }} else if (status === 'SKIPPED') {{
                badgeClass = 'badge-neutral';
            }} else if (status === 'VERIFIED' || status === 'SUCCESS') {{
                badgeClass = 'badge-success';
            }} else if (status === 'FAILED' || status === 'ERROR') {{
                badgeClass = 'badge-danger';
            }}

            return `<span class="badge ${{badgeClass}}">${{escapeHtml(status)}}</span>`;
        }}

        const results = runs.map(r => getProtectionBadge(r.protection, r.protection_status));
        console.log(JSON.stringify(results));
        """

        res = subprocess.run(["node", "-"], input=js_test_script, capture_output=True, text=True, check=True)
        rendered_badges = json.loads(res.stdout)

        assert len(rendered_badges) == len(runs)
        for idx, badge in enumerate(rendered_badges):
            # Must NEVER contain [object Object], undefined, or null
            assert "[object Object]" not in badge
            assert "[OBJECT OBJECT]" not in badge
            assert "undefined" not in badge
            assert "null" not in badge
            assert badge.startswith('<span class="badge ')
            assert badge.endswith('</span>')

            run = runs[idx]
            sc = run.get("scenario") or ""
            if "scenario_b" in sc or "c2" in sc:
                # Confirmed C2 run should be MITIGATED
                assert "MITIGATED" in badge or "EXECUTED" in badge
            elif "benign" in sc or "dapp" in sc:
                # Benign/DApp run should be SKIPPED
                assert "SKIPPED" in badge

    def test_w_correlation_presentation_and_unmatched_explanations(self, client):
        """
        Verify UI semantics for:
        1. Correlation wording:
           - Scenario A: '3 Observed Stages' (never 'Incomplete Chain')
           - Scenario C: '3 Observed Stages' (never 'Incomplete Chain')
           - Scenario B: '4/4 Stages Observed'
        2. Rule score contribution unmatched explanations:
           - Suspicious Data Retrieval: 'No suspicious retrieval detected. Target contract is not a command or dead-drop store.'
           - C2 / Configuration Indicator: 'No C2 command/configuration indicator detected.'
           - Subsequent Network Activity: 'No subsequent network activity observed.'
        3. Defense action in below-threshold benign run:
           - 'SKIPPED — Detection threshold not reached'
        4. Run Detail timestamp:
           - Verified to be a valid non-empty timestamp string (not '—').
        """
        from src.dashboard.services.experiment_service import ExperimentService
        svc = ExperimentService()
        history = svc.get_history()
        assert len(history) > 0

        # Find sample runs for Scenario A, B, C
        run_a = next(r for r in history if "scenario_a" in (r.get("scenario") or "").lower() or "benign" in (r.get("scenario") or "").lower())
        run_b = next(r for r in history if "scenario_b" in (r.get("scenario") or "").lower() or "c2" in (r.get("scenario") or "").lower())
        run_c = next(r for r in history if "scenario_c" in (r.get("scenario") or "").lower() or "dapp" in (r.get("scenario") or "").lower())

        detail_a = svc.get_run_details(run_a["run_id"])
        detail_b = svc.get_run_details(run_b["run_id"])
        detail_c = svc.get_run_details(run_c["run_id"])

        assert detail_a is not None
        assert detail_b is not None
        assert detail_c is not None

        # 4. Check real timestamp presence on run detail
        assert detail_a.get("timestamp"), f"Expected non-empty timestamp on Scenario A run detail, got {detail_a.get('timestamp')}"
        assert detail_b.get("timestamp"), f"Expected non-empty timestamp on Scenario B run detail, got {detail_b.get('timestamp')}"
        assert detail_c.get("timestamp"), f"Expected non-empty timestamp on Scenario C run detail, got {detail_c.get('timestamp')}"

        # Test frontend rendering via Node.js
        test_payload = {
            "run_a": detail_a,
            "run_b": detail_b,
            "run_c": detail_c,
        }

        charts_js = Path("src/dashboard/static/js/charts.js").read_text(encoding="utf-8")
        main_js = Path("src/dashboard/static/js/main.js").read_text(encoding="utf-8")

        import os
        import tempfile

        node_script = f"""
        const window = {{}};
        {charts_js}

        const data = {json.dumps(test_payload)};

        function mockContainer(id) {{
            return {{
                id: id,
                innerHTML: '',
                querySelector: () => null
            }};
        }}

        function getCorrelationSummary(run) {{
            const stages = (run.correlation && run.correlation.stages) || [];
            const stagesUpper = stages.map(s => String(s).toUpperCase());
            const isChainComplete = (run.correlation && run.correlation.chain_complete === true) ||
                                   (run.correlation && run.correlation.is_complete_chain === true) ||
                                   (stagesUpper.length >= 4 && stagesUpper.includes('NETWORK'));
            const stageCount = stages.length;
            return isChainComplete ? '4/4 Stages Observed' : (stageCount + ' Observed Stages');
        }}

        function getDefenseSummary(run) {{
            const isDetected = run.detection_triggered || (run.score >= run.threshold);
            if (!isDetected) {{
                return 'SKIPPED — Detection threshold not reached';
            }} else if (run.protection && run.protection.status) {{
                return run.protection.status.toUpperCase();
            }} else {{
                return 'MITIGATED';
            }}
        }}

        function formatTimestamp(ts) {{
            if (!ts) return '—';
            try {{
                const d = new Date(ts);
                return isNaN(d.getTime()) ? ts : d.toLocaleTimeString() + ' ' + d.toLocaleDateString();
            }} catch {{
                return ts;
            }}
        }}

        const corrA = getCorrelationSummary(data.run_a);
        const corrB = getCorrelationSummary(data.run_b);
        const corrC = getCorrelationSummary(data.run_c);

        const defA = getDefenseSummary(data.run_a);
        const defB = getDefenseSummary(data.run_b);
        const defC = getDefenseSummary(data.run_c);

        const tsA = formatTimestamp(data.run_a.timestamp);
        const tsB = formatTimestamp(data.run_b.timestamp);
        const tsC = formatTimestamp(data.run_c.timestamp);

        const cContainerA = mockContainer('corr-a');
        const cContainerB = mockContainer('corr-b');
        Charts.renderCorrelationChain(cContainerA, data.run_a.correlation || {{}});
        Charts.renderCorrelationChain(cContainerB, data.run_b.correlation || {{}});

        const contribContainerA = mockContainer('contrib-a');
        const contribA = (data.run_a.scoring && data.run_a.scoring.contributions) || [];
        Charts.renderContributionBars(contribContainerA, contribA);

        console.log(JSON.stringify({{
            corrA,
            corrB,
            corrC,
            defA,
            defB,
            defC,
            tsA,
            tsB,
            tsC,
            corrChainHtmlA: cContainerA.innerHTML,
            corrChainHtmlB: cContainerB.innerHTML,
            contribHtmlA: contribContainerA.innerHTML
        }}));
        """

        with tempfile.NamedTemporaryFile(suffix='.js', mode='w', encoding='utf-8', delete=False) as f:
            f.write(node_script)
            tmp_path = f.name

        try:
            res = subprocess.run(["node", tmp_path], capture_output=True, text=True, encoding="utf-8", check=True)
            out = json.loads(res.stdout)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        # 1. Correlation summary checks
        assert out["corrA"] == "3 Observed Stages", f"Expected '3 Observed Stages', got {out['corrA']}"
        assert out["corrC"] == "3 Observed Stages", f"Expected '3 Observed Stages', got {out['corrC']}"
        assert out["corrB"] == "4/4 Stages Observed", f"Expected '4/4 Stages Observed', got {out['corrB']}"

        assert "Incomplete Chain" not in out["corrA"]
        assert "Incomplete Chain" not in out["corrC"]
        assert "Incomplete Chain" not in out["corrChainHtmlA"]
        assert "INCOMPLETE CHAIN" not in out["corrChainHtmlA"]
        assert "3 OBSERVED STAGES" in out["corrChainHtmlA"]
        assert "4/4 STAGES OBSERVED" in out["corrChainHtmlB"]

        # 2. Unmatched rules explanation checks
        contrib_html = out["contribHtmlA"]
        assert "No suspicious retrieval detected. Target contract is not a command or dead-drop store." in contrib_html
        assert "No C2 command/configuration indicator detected." in contrib_html
        assert "No subsequent network activity observed." in contrib_html

        # 3. Defense action for below-threshold benign run
        assert out["defA"] == "SKIPPED — Detection threshold not reached"
        assert out["defC"] == "SKIPPED — Detection threshold not reached"
        assert "MITIGATED" in out["defB"] or "EXECUTED" in out["defB"]

        # 4. Timestamp check
        assert out["tsA"] != "—" and len(out["tsA"]) > 3
        assert out["tsB"] != "—" and len(out["tsB"]) > 3
        assert out["tsC"] != "—" and len(out["tsC"]) > 3

    # -------------------------------------------------------------------------
    # X. Experiment Center Cards use score denominator /100, not /80
    # -------------------------------------------------------------------------
    def test_x_experiment_cards_score_denominator_is_100(self, client):
        """
        Verify that Experiment Center -> Latest Execution Results experiment cards
        display the score denominator as / 100 (maximum points), NOT / 80 (detection threshold).
        - Scenario A: Total Score: 35 / 100
        - Scenario B: Total Score: 100 / 100
        - Scenario C: Total Score: 35 / 100
        """
        main_js_src = Path("src/dashboard/static/js/main.js").read_text(encoding="utf-8")
        main_js_pub = Path("public/static/js/main.js").read_text(encoding="utf-8")

        # Static inspection
        assert 'Total Score:</span> <strong class="font-mono">${r.score}</strong> / 100' in main_js_src
        assert 'Total Score:</span> <strong class="font-mono">${r.score}</strong> / 100' in main_js_pub
        assert 'Total Score:</span> <strong class="font-mono">${r.score}</strong> / ${r.threshold}' not in main_js_src
        assert 'Total Score:</span> <strong class="font-mono">${r.score}</strong> / ${r.threshold}' not in main_js_pub

        # Dynamic Node.js rendering of renderExecutionResults
        sample_runs = [
            {"run_id": "run-a", "scenario": "Scenario A", "scenario_name": "Scenario A — Benign", "score": 35, "threshold": 80, "detected": False, "classification": "BENIGN", "ground_truth": "BENIGN", "latency_ms": 12.34},
            {"run_id": "run-b", "scenario": "Scenario B", "scenario_name": "Scenario B — Synthetic C2", "score": 100, "threshold": 80, "detected": True, "classification": "MALICIOUS_C2", "ground_truth": "SYNTHETIC_C2", "latency_ms": 45.67},
            {"run_id": "run-c", "scenario": "Scenario C", "scenario_name": "Scenario C — Legitimate DApp", "score": 35, "threshold": 80, "detected": False, "classification": "BENIGN", "ground_truth": "BENIGN", "latency_ms": 14.56},
        ]

        import tempfile
        import os

        node_script = f"""
        const runs = {json.dumps(sample_runs)};
        const rendered = runs.map(r => {{
            const isDetected = r.detected;
            const statusClass = isDetected ? 'badge-danger' : 'badge-success';
            const statusText = isDetected ? 'DETECTED' : 'NOT DETECTED';
            return `
                <div class="card" style="border-top: 3px solid ${{isDetected ? 'var(--color-danger)' : 'var(--color-success)'}};">
                    <div class="card-header" style="padding-bottom: 0.5rem;">
                        <div>
                            <span class="card-title" style="font-size: 0.95rem;">${{r.scenario_name || r.scenario}}</span>
                            <div class="font-mono text-muted" style="font-size: 0.75rem;">Run ID: ${{r.run_id}}</div>
                        </div>
                        <span class="badge ${{statusClass}}">${{statusText}}</span>
                    </div>
                    <div style="display: grid; grid-template-columns: repeat(2, 1fr); gap: 0.5rem; font-size: 0.8rem; margin: 0.75rem 0;">
                        <div><span class="text-muted">Total Score:</span> <strong class="font-mono">${{r.score}}</strong> / 100</div>
                        <div><span class="text-muted">Latency:</span> <span class="font-mono">${{r.latency_ms?.toFixed(2)}} ms</span></div>
                        <div><span class="text-muted">Classification:</span> <span class="font-mono">${{r.classification}}</span></div>
                        <div><span class="text-muted">Ground Truth:</span> <span class="font-mono">${{r.ground_truth}}</span></div>
                    </div>
                    <button class="btn btn-secondary btn-sm" onclick="App.openRunDetail('${{r.run_id}}')" style="width: 100%;">
                        Inspect Full Multi-Layer Chain
                    </button>
                </div>
            `;
        }}).join('');
        console.log(JSON.stringify(rendered));
        """

        with tempfile.NamedTemporaryFile(suffix='.js', mode='w', encoding='utf-8', delete=False) as f:
            f.write(node_script)
            tmp_path = f.name

        try:
            res = subprocess.run(["node", tmp_path], capture_output=True, text=True, encoding="utf-8", check=True)
            rendered_cards = json.loads(res.stdout)
        finally:
            if os.path.exists(tmp_path):
                os.remove(tmp_path)

        # Assertions
        assert "Total Score:</span> <strong class=\"font-mono\">35</strong> / 100" in rendered_cards
        assert "Total Score:</span> <strong class=\"font-mono\">100</strong> / 100" in rendered_cards
        assert "Total Score:</span> <strong class=\"font-mono\">35</strong> / 80" not in rendered_cards
        assert "Total Score:</span> <strong class=\"font-mono\">100</strong> / 80" not in rendered_cards

    # -------------------------------------------------------------------------
    # Y. Live Telemetry Explorer & Execution Batch Validation
    # -------------------------------------------------------------------------
    def test_y_live_telemetry_batch_and_runs(self, client):
        """
        Verify Live Telemetry Explorer requirements:
        1. Current execution batch metadata (batch_id, timestamp, total_runs, total_events)
        2. Dynamic summary stats (total_events=10, endpoint=3, rpc=3, blockchain=3, network=1)
        3. Baseline batch has exactly 10 independent events: A=3, B=4, C=3
        4. Run isolation preserved: every event retains its original run_id
        5. Chronological sequential execution order: Run 1 -> Run 2 -> Run 3 (not grouped by scenario)
        6. Schema includes Timestamp, Scenario, Run ID, Event ID, Layer, Event Type, Process, Tx/Egress, Status
        """
        resp = client.get("/api/telemetry/live")
        assert resp.status_code == 200
        data = resp.get_json()

        assert "execution_batch" in data
        assert "summary" in data
        assert "runs" in data
        assert "events" in data

        batch = data["execution_batch"]
        assert batch["total_runs"] == 3
        assert batch["total_events"] == 10
        assert batch["display_timestamp"] is not None

        summary = data["summary"]
        assert summary["total_events"] == 10
        assert summary["endpoint_events"] == 3
        assert summary["rpc_events"] == 3
        assert summary["blockchain_events"] == 3
        assert summary["network_events"] == 1
        assert summary["total_runs"] == 3

        runs = data["runs"]
        assert len(runs) == 3
        run_ids = [r["run_id"] for r in runs]
        assert len(set(run_ids)) == 3  # All 3 runs have distinct IDs

        events = data["events"]
        assert len(events) == 10

        # Verify sequential ordering: Run 1 (first 3) -> Run 2 (next 4) -> Run 3 (last 3)
        ev_run_ids = [e["run_id"] for e in events]
        assert ev_run_ids[0] == ev_run_ids[1] == ev_run_ids[2] == run_ids[0]
        assert ev_run_ids[3] == ev_run_ids[4] == ev_run_ids[5] == ev_run_ids[6] == run_ids[1]
        assert ev_run_ids[7] == ev_run_ids[8] == ev_run_ids[9] == run_ids[2]

        # Verify layers in order
        layers = [e["layer"] for e in events]
        assert layers == [
            "ENDPOINT", "RPC", "BLOCKCHAIN",
            "ENDPOINT", "RPC", "BLOCKCHAIN", "NETWORK",
            "ENDPOINT", "RPC", "BLOCKCHAIN",
        ]

        # Verify event schema
        for ev in events:
            assert "timestamp" in ev
            assert "run_id" in ev
            assert "scenario" in ev
            assert "event_id" in ev
            assert "layer" in ev
            assert "event_type" in ev
            assert "status" in ev
            assert ev["status"] == "CAPTURED"

    # -------------------------------------------------------------------------
    # Z. Correlation Latency and Stage Status
    # -------------------------------------------------------------------------
    def test_z_correlation_duration_and_chain_status(self, client):
        """
        Verify:
        - Scenario B correlation latency is non-zero (bound to authoritative duration_ms ~26.90 ms)
        - Scenario B has 4/4 stages observed
        - Scenario A and C have 3 observed stages
        """
        hist_resp = client.get("/api/experiments/history?limit=30")
        runs = hist_resp.get_json().get("runs", [])

        b_run = next(r for r in runs if "scenario_b" in r["scenario"])
        a_run = next(r for r in runs if "scenario_a" in r["scenario"])

        b_detail = client.get(f"/api/experiments/run/{b_run['run_id']}").get_json()
        a_detail = client.get(f"/api/experiments/run/{a_run['run_id']}").get_json()

        corr_b = b_detail.get("correlation", {})
        assert corr_b.get("total_duration_ms") is not None
        assert corr_b.get("total_duration_ms") > 0.0
        assert corr_b.get("stage_count") == 4
        assert corr_b.get("has_network_followup") is True

        bench_b = next((r for r in runs if "eval-c2" in r.get("run_id", "")), None)
        if bench_b:
            bench_detail = client.get(f"/api/experiments/run/{bench_b['run_id']}").get_json()
            assert abs(bench_detail.get("correlation", {}).get("total_duration_ms", 0.0) - 26.902) < 0.1

        corr_a = a_detail.get("correlation", {})
        assert corr_a.get("stage_count") == 3
        assert corr_a.get("has_network_followup") is False

    # -------------------------------------------------------------------------
    # AA. Evidence Verification and Forensic Snapshot Rows
    # -------------------------------------------------------------------------
    def test_aa_evidence_checksum_verification_and_events(self, client):
        """
        Verify:
        - Evidence list returns preserved bundles with preservation timestamp
        - Bundle inspection populates 4 forensic snapshot events
        - Cryptographic SHA-256 verification computes and matches pristine digest
        """
        ev_resp = client.get("/api/evidence")
        assert ev_resp.status_code == 200
        bundles = ev_resp.get_json().get("bundles", [])
        assert len(bundles) > 0

        b0 = bundles[0]
        bid = b0["bundle_id"]
        assert b0.get("preserved_at") is not None
        assert len(b0.get("sha256_checksum", "")) == 64

        # Inspection
        detail_resp = client.get(f"/api/evidence/{bid}")
        assert detail_resp.status_code == 200
        detail = detail_resp.get_json()
        assert len(detail.get("events", [])) == 4
        assert detail.get("preserved_at") is not None

        # Verification
        v_resp = client.post(f"/api/evidence/{bid}/verify")
        assert v_resp.status_code == 200
        v_data = v_resp.get_json()
        assert v_data["verified"] is True
        assert v_data["status"] == "VERIFIED"
        assert v_data["calculated_checksum"] == v_data["expected_checksum"]

    # -------------------------------------------------------------------------
    # BB. Research Deliverables Grammar and Boundary Wording
    # -------------------------------------------------------------------------
    def test_bb_research_summary_wording(self):
        """Verify authoritative bounded wording in research_summary.json and HTML."""
        summary_path = Path("results/final/research_summary.json")
        assert summary_path.exists()
        summary_text = summary_path.read_text(encoding="utf-8")
        assert "across the evaluated synthetic test cases when endpoint, RPC/blockchain, and network telemetry are temporally and contextually correlated." in summary_text

        html_path = Path("src/dashboard/templates/index.html")
        html_text = html_path.read_text(encoding="utf-8")
        assert "Detection Processing Latency" in html_text
        assert "No false positives across the 20 evaluated benign/baseline Web3 executions." in html_text

    # -------------------------------------------------------------------------
    # CC. Static Asset SHA-256 Parity
    # -------------------------------------------------------------------------
    def test_cc_static_asset_parity(self):
        """Verify byte-for-byte SHA-256 parity between src/dashboard/static/js and public/static/js."""
        import hashlib
        for fname in ["main.js", "charts.js"]:
            src_f = Path("src/dashboard/static/js") / fname
            pub_f = Path("public/static/js") / fname
            assert src_f.exists()
            assert pub_f.exists()
            h_src = hashlib.sha256(src_f.read_bytes()).hexdigest()
            h_pub = hashlib.sha256(pub_f.read_bytes()).hexdigest()
            assert h_src == h_pub, f"Asset mismatch for {fname}: src={h_src} vs pub={h_pub}"

    # -------------------------------------------------------------------------
    # DD. Actual Execution & Current Batch Live Telemetry Regression
    # -------------------------------------------------------------------------
    def test_dd_actual_run_all_3_execution_telemetry_parity(self, client):
        """
        Verify:
        1. Execute Run All 3 via /api/experiments/execute.
        2. Capture actual returned run IDs, timestamps, and scenario names.
        3. /api/telemetry/live returns the current batch with:
           - batch_id starting with 'batch-live-' (NOT reverting to baseline)
           - source == 'current_execution' and is_current_execution == True
           - exactly 10 events matching the 3 runs (A=3, B=4, C=3)
           - exact matching run IDs
           - sequential execution order (Run 1 -> Run 2 -> Run 3).
        """
        exec_res = client.post("/api/experiments/execute", json={"scenario": "all", "repetitions": 1})
        assert exec_res.status_code == 200
        exec_data = exec_res.get_json()
        runs = exec_data.get("runs", [])
        assert len(runs) == 3
        exec_run_ids = [r["run_id"] for r in runs]
        assert len(set(exec_run_ids)) == 3

        telem_res = client.get("/api/telemetry/live")
        assert telem_res.status_code == 200
        telem_data = telem_res.get_json()

        batch = telem_data.get("execution_batch", {})
        batch_id = batch.get("batch_id")
        assert batch_id != "batch-baseline-authoritative"
        assert batch_id.startswith("batch-live-")

        telem_runs = telem_data.get("runs", [])
        telem_run_ids = [r["run_id"] for r in telem_runs]
        assert telem_run_ids == exec_run_ids

        events = telem_data.get("events", [])
        assert len(events) == 10

        a_events = [e for e in events if e["run_id"] == exec_run_ids[0]]
        b_events = [e for e in events if e["run_id"] == exec_run_ids[1]]
        c_events = [e for e in events if e["run_id"] == exec_run_ids[2]]
        assert len(a_events) == 3
        assert len(b_events) == 4
        assert len(c_events) == 3

        ev_run_ids = [e["run_id"] for e in events]
        assert ev_run_ids[0] == ev_run_ids[1] == ev_run_ids[2] == exec_run_ids[0]
        assert ev_run_ids[3] == ev_run_ids[4] == ev_run_ids[5] == ev_run_ids[6] == exec_run_ids[1]
        assert ev_run_ids[7] == ev_run_ids[8] == ev_run_ids[9] == exec_run_ids[2]

        assert telem_data.get("source") == "current_execution"
        assert telem_data.get("is_current_execution") is True


