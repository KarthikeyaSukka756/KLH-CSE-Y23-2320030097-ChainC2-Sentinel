/**
 * ChainC2 Sentinel — Frontend API Client
 * Clean REST abstraction communicating with dashboard Flask backend.
 */

const APPSAIL_BACKEND_ORIGIN = 'https://chainc2-sentinel-service-50046833542.development.catalystappsail.in';

function getApiBaseUrl() {
  if (typeof window !== 'undefined' && window.location) {
    const host = window.location.hostname || '';
    // Route to AppSail service when accessed from Catalyst Web Client domain
    if (host.includes('catalystserverless.in')) {
      return APPSAIL_BACKEND_ORIGIN;
    }
  }
  return '';
}

const API = {
  async getHealth() {
    return this._fetchJson('/api/health');
  },

  async getOverview() {
    return this._fetchJson('/api/overview');
  },

  async getDetectionEvaluation() {
    return this._fetchJson('/api/evaluation/detection');
  },

  async getProtectionEvaluation() {
    return this._fetchJson('/api/evaluation/protection');
  },

  async getHistory(params = {}) {
    const qs = new URLSearchParams();
    if (params.scenario) qs.append('scenario', params.scenario);
    if (params.detection) qs.append('detection', params.detection);
    if (params.classification) qs.append('classification', params.classification);
    if (params.limit) qs.append('limit', params.limit);
    const url = `/api/experiments/history${qs.toString() ? '?' + qs.toString() : ''}`;
    return this._fetchJson(url);
  },

  // Alias called by main.js
  async getExperimentHistory(params = {}) {
    return this.getHistory(params);
  },

  async getRunDetails(runId) {
    return this._fetchJson(`/api/experiments/run/${encodeURIComponent(runId)}`);
  },

  // Alias called by main.js
  async getExperimentRun(runId) {
    return this.getRunDetails(runId);
  },

  async executeExperiment(scenarioOrPayload, repetitions = 1) {
    let body;
    if (typeof scenarioOrPayload === 'object' && scenarioOrPayload !== null) {
      body = scenarioOrPayload;
    } else {
      body = { scenario: scenarioOrPayload, repetitions };
    }
    return this._fetchJson('/api/experiments/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify(body)
    });
  },

  async getLiveTelemetry(params = {}) {
    const p = typeof params === 'string' ? { runId: params } : (params || {});
    const qs = new URLSearchParams();
    const runId = p.runId || p.run_id;
    if (runId) qs.append('run_id', runId);
    if (p.source) qs.append('source', p.source);
    if (p.limit) qs.append('limit', p.limit);
    const url = `/api/telemetry/live${qs.toString() ? '?' + qs.toString() : ''}`;
    return this._fetchJson(url);
  },

  async getEvidenceList() {
    return this._fetchJson('/api/evidence');
  },

  async getEvidenceBundle(bundleId) {
    return this._fetchJson(`/api/evidence/${encodeURIComponent(bundleId)}`);
  },

  async verifyEvidenceChecksum(bundleId) {
    return this._fetchJson(`/api/evidence/${encodeURIComponent(bundleId)}/verify`, {
      method: 'POST'
    });
  },

  // Alias called by main.js
  async verifyEvidence(bundleId) {
    return this.verifyEvidenceChecksum(bundleId);
  },

  async getResearchSummary() {
    return this._fetchJson('/api/research/summary');
  },

  async getResearchReport(reportName) {
    return this._fetchJson(`/api/research/report/${encodeURIComponent(reportName)}`);
  },

  // Alias called by main.js
  async getReport(reportName) {
    return this.getResearchReport(reportName);
  },

  async getDownloadList() {
    return this._fetchJson('/api/downloads');
  },

  // Alias called by main.js
  async getDownloadsList() {
    return this.getDownloadList();
  },

  getDownloadUrl(fileType) {
    return `${getApiBaseUrl()}/api/download/${encodeURIComponent(fileType)}`;
  },

  // -------------------------------------------------------------------------
  // Dedicated Alerts, Investigations & Operational Endpoints
  // -------------------------------------------------------------------------
  async getAlerts(params = {}) {
    const qs = new URLSearchParams();
    if (params.severity) qs.append('severity', params.severity);
    if (params.limit) qs.append('limit', params.limit);
    return this._fetchJson(`/api/alerts${qs.toString() ? '?' + qs.toString() : ''}`);
  },

  async getAlert(alertId) {
    return this._fetchJson(`/api/alerts/${encodeURIComponent(alertId)}`);
  },

  async getInvestigations(limit = 100) {
    return this._fetchJson(`/api/investigations?limit=${limit}`);
  },

  async getInvestigation(invId) {
    return this._fetchJson(`/api/investigations/${encodeURIComponent(invId)}`);
  },

  async getMitigations(limit = 100) {
    return this._fetchJson(`/api/mitigations?limit=${limit}`);
  },

  async getSystemHealth() {
    return this._fetchJson('/api/system/health');
  },

  async getGeneratorStatus() {
    return this._fetchJson('/api/generator/status');
  },

  async stepGenerator() {
    return this._fetchJson('/api/generator/step', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
  },

  async startBackgroundGenerator(maxCycles = 4) {
    return this._fetchJson('/api/generator/start', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ max_cycles: maxCycles })
    });
  },

  async stopBackgroundGenerator() {
    return this._fetchJson('/api/generator/stop', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
  },

  async startGenerator(singleStep = false, maxCycles = 4) {
    if (singleStep) {
      return this.stepGenerator();
    }
    return this.startBackgroundGenerator(maxCycles);
  },

  async stopGenerator() {
    return this.stopBackgroundGenerator();
  },

  async verifySepoliaTx(txHash, expectedContract = '') {
    const qs = expectedContract ? `?expected_contract=${encodeURIComponent(expectedContract)}` : '';
    return this._fetchJson(`/api/sepolia/verify-tx/${encodeURIComponent(txHash)}${qs}`);
  },

  async getPostRunEvaluation() {
    return this._fetchJson('/api/evaluation/post-run');
  },

  // -------------------------------------------------------------------------
  // Sepolia Testnet & Experiment Endpoints
  // -------------------------------------------------------------------------
  async getSepoliaStatus() {
    return this._fetchJson('/api/sepolia/status');
  },

  async getSepoliaTransactions(filter = '', limit = 100) {
    return this._fetchJson(`/api/sepolia/transactions?filter=${encodeURIComponent(filter)}&limit=${limit}`);
  },

  async pollSepoliaBlocks() {
    return this._fetchJson('/api/sepolia/poll', { method: 'POST' });
  },

  async getSepoliaAlerts() {
    return this._fetchJson('/api/sepolia/alerts');
  },

  async getSepoliaExperiments() {
    return this._fetchJson('/api/sepolia/experiments');
  },

  async getSepoliaMitigations() {
    return this._fetchJson('/api/sepolia/mitigations');
  },

  async executeSepoliaExperiment(experimentType = 'positive_c2') {
    return this._fetchJson('/api/sepolia/execute', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ experiment_type: experimentType })
    });
  },

  async rollbackSepoliaMitigations() {
    return this._fetchJson('/api/sepolia/rollback', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
  },

  // -------------------------------------------------------------------------
  // Zoho Catalyst CloudScale & Budget Endpoints
  // -------------------------------------------------------------------------
  async getCloudScaleBudget() {
    return this._fetchJson('/api/cloudscale/budget');
  },

  async getCloudScaleStatus() {
    return this._fetchJson('/api/cloudscale/status');
  },

  async triggerCloudScaleCron() {
    return this._fetchJson('/api/cloudscale/cron/trigger', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({})
    });
  },

  async _fetchJson(url, options = {}) {
    const fullUrl = url.startsWith('http') ? url : (getApiBaseUrl() + url);
    try {
      const response = await fetch(fullUrl, options);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || data.message || `HTTP ${response.status}: ${response.statusText}`);
      }
      return data;
    } catch (err) {
      console.error(`API Request failed for ${fullUrl}:`, err);
      throw err;
    }
  }
};

window.API = API;
