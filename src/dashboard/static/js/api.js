/**
 * ChainC2 Sentinel — Frontend API Client
 * Clean REST abstraction communicating with dashboard Flask backend.
 */

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
    const qs = new URLSearchParams();
    if (params.runId) qs.append('run_id', params.runId);
    if (params.source) qs.append('source', params.source);
    if (params.limit) qs.append('limit', params.limit);
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
    return `/api/download/${encodeURIComponent(fileType)}`;
  },

  async _fetchJson(url, options = {}) {
    try {
      const response = await fetch(url, options);
      const data = await response.json();
      if (!response.ok) {
        throw new Error(data.error || `HTTP ${response.status}: ${response.statusText}`);
      }
      return data;
    } catch (err) {
      console.error(`API Request failed for ${url}:`, err);
      throw err;
    }
  }
};

window.API = API;
