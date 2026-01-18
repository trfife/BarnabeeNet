/**
 * BarnabeeNet Dashboard - JavaScript Application
 */

// Configuration
const API_BASE = window.location.origin;
const WS_URL = `ws://${window.location.host}/api/v1/ws/activity`;

// State
let ws = null;
let autoScroll = true;
let activityFilter = '';
let activeTraces = new Map(); // trace_id -> signals

// =============================================================================
// Initialization
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initClock();
    initActivityControls();
    initConfigNav();
    initTestButtons();
    initTraceModal();

    // Load initial data
    loadSystemStatus();
    loadStats();
    loadTraces();

    // Connect WebSocket
    connectWebSocket();

    // Refresh data periodically
    setInterval(loadSystemStatus, 30000);
    setInterval(loadStats, 60000);
    setInterval(loadTraces, 10000);
});

// =============================================================================
// Navigation
// =============================================================================

function initNavigation() {
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', (e) => {
            e.preventDefault();
            const page = link.dataset.page;
            showPage(page);
        });
    });
}

function showPage(pageId) {
    // Update nav links
    document.querySelectorAll('.nav-link').forEach(link => {
        link.classList.toggle('active', link.dataset.page === pageId);
    });

    // Show page
    document.querySelectorAll('.page').forEach(page => {
        page.classList.toggle('active', page.id === `page-${pageId}`);
    });
}

// =============================================================================
// Clock
// =============================================================================

function initClock() {
    updateClock();
    setInterval(updateClock, 1000);
}

function updateClock() {
    const now = new Date();
    document.getElementById('current-time').textContent =
        now.toLocaleString('en-US', {
            month: 'short',
            day: 'numeric',
            year: 'numeric',
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });
}

// =============================================================================
// WebSocket Connection
// =============================================================================

function connectWebSocket() {
    const statusEl = document.getElementById('ws-status');

    try {
        ws = new WebSocket(WS_URL);

        ws.onopen = () => {
            statusEl.className = 'status-indicator connected';
            addActivityItem({
                type: 'system',
                message: 'Connected to activity stream',
                timestamp: new Date().toISOString()
            });
        };

        ws.onclose = () => {
            statusEl.className = 'status-indicator disconnected';
            addActivityItem({
                type: 'error',
                message: 'Disconnected from activity stream. Reconnecting...',
                timestamp: new Date().toISOString()
            });
            // Reconnect after 5 seconds
            setTimeout(connectWebSocket, 5000);
        };

        ws.onerror = (error) => {
            console.error('WebSocket error:', error);
            statusEl.className = 'status-indicator disconnected';
        };

        ws.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                handleActivityMessage(data);
            } catch (e) {
                console.error('Error parsing WebSocket message:', e);
            }
        };
    } catch (e) {
        console.error('WebSocket connection failed:', e);
        statusEl.className = 'status-indicator disconnected';
        setTimeout(connectWebSocket, 5000);
    }
}

function handleActivityMessage(data) {
    if (data.type === 'signal') {
        addActivityItem({
            type: data.signal_type || 'system',
            message: formatSignalMessage(data),
            timestamp: data.timestamp,
            latency: data.latency_ms
        });

        // Track active trace for real-time updates
        if (data.trace_id) {
            if (!activeTraces.has(data.trace_id)) {
                activeTraces.set(data.trace_id, {
                    trace_id: data.trace_id,
                    signals: [],
                    started_at: data.timestamp
                });
            }
            activeTraces.get(data.trace_id).signals.push(data);
        }

        // Refresh traces list for new/completed traces
        if (data.signal_type === 'request_start' || data.signal_type === 'request_complete') {
            loadTraces();
        }
    } else if (data.type === 'heartbeat') {
        // Heartbeat - ignore
    }
}

function formatSignalMessage(data) {
    const type = data.signal_type || 'unknown';

    switch (type) {
        case 'llm_call':
            return `LLM: ${data.model || 'unknown'} - "${truncate(data.prompt || data.message || '', 100)}"`;
        case 'stt':
            return `STT: "${data.transcript || data.message || ''}"`;
        case 'tts':
            return `TTS: "${truncate(data.text || data.message || '', 80)}"`;
        case 'ha_action':
            return `HA: ${data.service || ''} → ${data.entity_id || data.message || ''}`;
        case 'memory':
            return `Memory: ${data.operation || ''} - ${data.message || ''}`;
        default:
            return data.message || JSON.stringify(data);
    }
}

function truncate(str, len) {
    return str.length > len ? str.substring(0, len) + '...' : str;
}

// =============================================================================
// Activity Feed
// =============================================================================

function initActivityControls() {
    document.getElementById('activity-filter').addEventListener('change', (e) => {
        activityFilter = e.target.value;
        filterActivityFeed();
    });

    document.getElementById('clear-activity').addEventListener('click', () => {
        document.getElementById('activity-feed').innerHTML = '';
    });

    document.getElementById('auto-scroll').addEventListener('change', (e) => {
        autoScroll = e.target.checked;
    });
}

function addActivityItem(data) {
    const feed = document.getElementById('activity-feed');
    const item = document.createElement('div');
    item.className = 'activity-item';
    item.dataset.type = data.type;

    const time = new Date(data.timestamp).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });

    item.innerHTML = `
        <span class="activity-time">${time}</span>
        <span class="activity-badge ${data.type}">${data.type}</span>
        <span class="activity-message">${escapeHtml(data.message)}</span>
        ${data.latency ? `<span class="activity-latency">${data.latency.toFixed(0)}ms</span>` : ''}
    `;

    // Apply filter
    if (activityFilter && data.type !== activityFilter) {
        item.style.display = 'none';
    }

    feed.appendChild(item);

    // Limit items
    while (feed.children.length > 200) {
        feed.removeChild(feed.firstChild);
    }

    // Auto scroll
    if (autoScroll) {
        feed.scrollTop = feed.scrollHeight;
    }
}

function filterActivityFeed() {
    document.querySelectorAll('.activity-item').forEach(item => {
        if (!activityFilter || item.dataset.type === activityFilter) {
            item.style.display = '';
        } else {
            item.style.display = 'none';
        }
    });
}

// =============================================================================
// System Status
// =============================================================================

async function loadSystemStatus() {
    try {
        const response = await fetch(`${API_BASE}/health`);
        const data = await response.json();

        updateSystemStatus(data);
        updateServicesHealth(data.services || []);
    } catch (e) {
        console.error('Failed to load system status:', e);
    }
}

function updateSystemStatus(data) {
    const container = document.getElementById('system-status');

    const statusClass = data.status === 'healthy' ? 'status-healthy' :
        data.status === 'degraded' ? 'status-degraded' : 'status-unhealthy';

    container.innerHTML = `
        <div class="status-row">
            <span class="status-label">Status:</span>
            <span class="status-value ${statusClass}">${data.status}</span>
        </div>
        <div class="status-row">
            <span class="status-label">Version:</span>
            <span class="status-value">${data.version || '0.1.0'}</span>
        </div>
        <div class="status-row">
            <span class="status-label">Environment:</span>
            <span class="status-value">Production</span>
        </div>
    `;
}

function updateServicesHealth(services) {
    const container = document.getElementById('services-health');

    if (!services.length) {
        container.innerHTML = '<p class="text-muted">No services data</p>';
        return;
    }

    container.innerHTML = services.map(service => {
        const statusClass = service.status === 'healthy' ? 'status-healthy' :
            service.status === 'degraded' ? 'status-degraded' : 'status-unhealthy';
        const latency = service.latency_ms ? ` (${service.latency_ms.toFixed(1)}ms)` : '';

        return `
            <div class="status-row">
                <span class="status-label">${service.name}:</span>
                <span class="status-value ${statusClass}">${service.status}${latency}</span>
            </div>
        `;
    }).join('');
}

// =============================================================================
// Statistics
// =============================================================================

async function loadStats() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/dashboard/stats`);
        const data = await response.json();

        document.getElementById('stat-requests').textContent = data.total_requests || '0';
        document.getElementById('stat-signals').textContent = data.total_signals || '0';
        document.getElementById('stat-memories').textContent = data.total_memories || '0';
        document.getElementById('stat-actions').textContent = data.total_actions || '0';
    } catch (e) {
        console.error('Failed to load stats:', e);
    }
}

// =============================================================================
// Configuration Navigation
// =============================================================================

function initConfigNav() {
    document.querySelectorAll('.config-nav li').forEach(item => {
        item.addEventListener('click', () => {
            const configId = item.dataset.config;

            // Update nav
            document.querySelectorAll('.config-nav li').forEach(i => {
                i.classList.toggle('active', i.dataset.config === configId);
            });

            // Show section
            document.querySelectorAll('.config-section').forEach(section => {
                section.classList.toggle('active', section.id === `config-${configId}`);
            });
        });
    });
}

// =============================================================================
// Test Buttons
// =============================================================================

function initTestButtons() {
    document.getElementById('test-tts').addEventListener('click', testTTS);
    document.getElementById('test-llm').addEventListener('click', testLLM);
    document.getElementById('test-stt').addEventListener('click', testSTT);
    document.getElementById('test-pipeline').addEventListener('click', testPipeline);

    // E2E Test buttons
    document.getElementById('e2e-quick-test').addEventListener('click', runQuickE2ETest);
    document.getElementById('e2e-run-suite').addEventListener('click', runE2ETestSuite);
}

async function testTTS() {
    const result = document.getElementById('tts-result');
    const text = document.getElementById('tts-test-text').value;

    result.className = 'test-result loading';
    result.textContent = 'Testing TTS...';

    try {
        const response = await fetch(`${API_BASE}/api/v1/voice/tts`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text })
        });

        if (response.ok) {
            const data = await response.json();
            result.className = 'test-result success';
            result.textContent = `✓ TTS Success! Latency: ${data.latency_ms?.toFixed(0) || 'N/A'}ms`;
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
    } catch (e) {
        result.className = 'test-result error';
        result.textContent = `✗ TTS Failed: ${e.message}`;
    }
}

async function testLLM() {
    const result = document.getElementById('llm-result');
    const prompt = document.getElementById('llm-test-prompt').value;

    result.className = 'test-result loading';
    result.textContent = 'Testing LLM...';

    try {
        // Use the voice process endpoint which goes through the orchestrator
        const response = await fetch(`${API_BASE}/api/v1/voice/process`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: prompt,
                speaker: 'dashboard_test',
                room: 'web'
            })
        });

        if (response.ok) {
            const data = await response.json();
            result.className = 'test-result success';
            result.innerHTML = `✓ Response: "${truncate(data.response || data.text || 'OK', 100)}"`;
        } else {
            throw new Error(`HTTP ${response.status}`);
        }
    } catch (e) {
        result.className = 'test-result error';
        result.textContent = `✗ LLM Failed: ${e.message}`;
    }
}

async function testSTT() {
    const result = document.getElementById('stt-result');

    result.className = 'test-result loading';
    result.textContent = 'STT test requires audio input. Check GPU worker status below.';

    try {
        const gpuUrl = document.getElementById('stt-gpu-url').value;
        const response = await fetch(`${gpuUrl}/health`);

        if (response.ok) {
            const data = await response.json();
            document.getElementById('gpu-worker-status').textContent = 'Online';
            document.getElementById('gpu-worker-status').className = 'status-value status-healthy';
            result.className = 'test-result success';
            result.textContent = `✓ GPU Worker Online - Model: ${data.model || 'Parakeet TDT'}`;
        } else {
            throw new Error('GPU worker not responding');
        }
    } catch (e) {
        document.getElementById('gpu-worker-status').textContent = 'Offline';
        document.getElementById('gpu-worker-status').className = 'status-value status-unhealthy';
        result.className = 'test-result error';
        result.textContent = `✗ GPU Worker Offline - Using CPU fallback`;
    }
}

async function testPipeline() {
    const result = document.getElementById('pipeline-result');
    const input = document.getElementById('pipeline-input').value;

    result.className = 'test-result loading';
    result.textContent = 'Processing through full pipeline...';

    try {
        const response = await fetch(`${API_BASE}/api/v1/voice/process`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                text: input,
                speaker: 'dashboard_test',
                room: 'web'
            })
        });

        if (response.ok) {
            const data = await response.json();
            result.className = 'test-result success';
            result.innerHTML = `
                <strong>✓ Pipeline Complete</strong><br>
                <strong>Intent:</strong> ${data.intent || 'N/A'}<br>
                <strong>Agent:</strong> ${data.agent_used || 'N/A'}<br>
                <strong>Response:</strong> "${data.response || data.text || 'OK'}"<br>
                <strong>Total Time:</strong> ${data.total_latency_ms?.toFixed(0) || 'N/A'}ms
            `;
        } else {
            const errData = await response.json().catch(() => ({}));
            throw new Error(errData.detail || `HTTP ${response.status}`);
        }
    } catch (e) {
        result.className = 'test-result error';
        result.textContent = `✗ Pipeline Failed: ${e.message}`;
    }
}

// =============================================================================
// Utilities
// =============================================================================

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// =============================================================================
// Request Traces
// =============================================================================

function initTraceModal() {
    document.getElementById('close-modal').addEventListener('click', () => {
        document.getElementById('trace-modal').style.display = 'none';
    });

    document.getElementById('trace-modal').addEventListener('click', (e) => {
        if (e.target.id === 'trace-modal') {
            document.getElementById('trace-modal').style.display = 'none';
        }
    });

    document.getElementById('refresh-traces').addEventListener('click', loadTraces);
}

async function loadTraces() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/dashboard/traces?limit=50`);
        const data = await response.json();

        renderTraces(data.traces);
    } catch (e) {
        console.error('Failed to load traces:', e);
    }
}

function renderTraces(traces) {
    const container = document.getElementById('traces-list');

    if (!traces || traces.length === 0) {
        container.innerHTML = '<p class="text-muted">No request traces yet. Process a voice command to see the data flow.</p>';
        return;
    }

    container.innerHTML = traces.map(trace => {
        const time = new Date(trace.timestamp).toLocaleTimeString('en-US', {
            hour: '2-digit',
            minute: '2-digit',
            second: '2-digit'
        });

        const agentClass = (trace.agent_used || 'unknown').toLowerCase();

        return `
            <div class="trace-item" onclick="showTraceDetail('${trace.trace_id}')">
                <span class="trace-time">${time}</span>
                <div class="trace-flow">
                    <span class="trace-input">"${escapeHtml(trace.input_preview || '')}"</span>
                    <span class="trace-arrow">→</span>
                    <span class="trace-agent ${agentClass}">${trace.agent_used || 'N/A'}</span>
                    <span class="trace-arrow">→</span>
                    <span class="trace-response">"${escapeHtml(trace.response_preview || '')}"</span>
                </div>
                <div class="trace-meta">
                    <span class="trace-latency">${trace.total_latency_ms?.toFixed(0) || '-'}ms</span>
                    <span class="trace-signals">${trace.signal_count} signals</span>
                    <span class="trace-status ${trace.success ? 'success' : 'error'}"></span>
                </div>
            </div>
        `;
    }).join('');
}

async function showTraceDetail(traceId) {
    const modal = document.getElementById('trace-modal');
    const detail = document.getElementById('trace-detail');

    detail.innerHTML = '<p class="text-muted">Loading trace...</p>';
    modal.style.display = 'flex';

    try {
        const response = await fetch(`${API_BASE}/api/v1/dashboard/traces/${traceId}`);
        const trace = await response.json();

        detail.innerHTML = renderTraceDetail(trace);
    } catch (e) {
        detail.innerHTML = `<p class="text-muted">Failed to load trace: ${e.message}</p>`;
    }
}

function renderTraceDetail(trace) {
    const startTime = new Date(trace.started_at).toLocaleString();
    const endTime = trace.completed_at ? new Date(trace.completed_at).toLocaleString() : 'In progress';

    return `
        <div class="trace-header">
            <div class="trace-header-section">
                <h4>📥 Input</h4>
                <div class="trace-field">
                    <span class="trace-field-label">Text:</span>
                    <span class="trace-field-value">"${escapeHtml(trace.input_text)}"</span>
                </div>
                <div class="trace-field">
                    <span class="trace-field-label">Type:</span>
                    <span class="trace-field-value">${trace.input_type}</span>
                </div>
                <div class="trace-field">
                    <span class="trace-field-label">Speaker:</span>
                    <span class="trace-field-value">${trace.speaker || 'Unknown'}</span>
                </div>
                <div class="trace-field">
                    <span class="trace-field-label">Room:</span>
                    <span class="trace-field-value">${trace.room || 'Unknown'}</span>
                </div>
            </div>

            <div class="trace-header-section">
                <h4>🧠 Classification</h4>
                <div class="trace-field">
                    <span class="trace-field-label">Intent:</span>
                    <span class="trace-field-value">${trace.intent || 'N/A'}</span>
                </div>
                <div class="trace-field">
                    <span class="trace-field-label">Confidence:</span>
                    <span class="trace-field-value">${trace.intent_confidence ? (trace.intent_confidence * 100).toFixed(0) + '%' : 'N/A'}</span>
                </div>
                <div class="trace-field">
                    <span class="trace-field-label">Context:</span>
                    <span class="trace-field-value">${trace.context_type || 'N/A'}</span>
                </div>
                <div class="trace-field">
                    <span class="trace-field-label">Agent:</span>
                    <span class="trace-field-value">${trace.agent_used || 'N/A'}</span>
                </div>
            </div>
        </div>

        <div class="trace-header">
            <div class="trace-header-section">
                <h4>📤 Response</h4>
                <div class="trace-field">
                    <span class="trace-field-label">Text:</span>
                    <span class="trace-field-value">"${escapeHtml(trace.response_text)}"</span>
                </div>
                <div class="trace-field">
                    <span class="trace-field-label">Type:</span>
                    <span class="trace-field-value">${trace.response_type}</span>
                </div>
                <div class="trace-field">
                    <span class="trace-field-label">Success:</span>
                    <span class="trace-field-value" style="color: ${trace.success ? 'var(--accent-primary)' : 'var(--accent-error)'}">${trace.success ? '✓ Yes' : '✗ No'}</span>
                </div>
                ${trace.error ? `<div class="trace-field"><span class="trace-field-label">Error:</span><span class="trace-field-value" style="color: var(--accent-error)">${escapeHtml(trace.error)}</span></div>` : ''}
            </div>

            <div class="trace-header-section">
                <h4>📊 Metrics</h4>
                <div class="trace-field">
                    <span class="trace-field-label">Total Time:</span>
                    <span class="trace-field-value">${trace.total_latency_ms?.toFixed(0) || '-'}ms</span>
                </div>
                <div class="trace-field">
                    <span class="trace-field-label">Tokens:</span>
                    <span class="trace-field-value">${trace.total_tokens || 0}</span>
                </div>
                <div class="trace-field">
                    <span class="trace-field-label">Cost:</span>
                    <span class="trace-field-value">$${trace.total_cost_usd?.toFixed(5) || '0.00000'}</span>
                </div>
                <div class="trace-field">
                    <span class="trace-field-label">Started:</span>
                    <span class="trace-field-value">${startTime}</span>
                </div>
            </div>
        </div>

        <div class="pipeline-flow">
            <h4>🔄 Pipeline Flow (${trace.signals.length} signals)</h4>
            <div class="pipeline-stages">
                ${trace.signals.map(sig => renderPipelineSignal(sig)).join('')}
            </div>
        </div>

        ${trace.ha_actions && trace.ha_actions.length > 0 ? `
            <div class="data-section">
                <h4>🏠 Home Assistant Actions</h4>
                <div class="data-block">${JSON.stringify(trace.ha_actions, null, 2)}</div>
            </div>
        ` : ''}

        ${trace.memories_retrieved && trace.memories_retrieved.length > 0 ? `
            <div class="data-section">
                <h4>💾 Memories Retrieved</h4>
                <div class="data-block">${trace.memories_retrieved.map(m => '• ' + m).join('\n')}</div>
            </div>
        ` : ''}
    `;
}

function renderPipelineSignal(sig) {
    const time = new Date(sig.timestamp).toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit',
        fractionalSecondDigits: 3
    });

    const signalClass = sig.signal_type.replace(/[^a-z_]/gi, '_');

    let details = '';
    if (sig.model_used) {
        details += `Model: ${sig.model_used}`;
    }
    if (sig.tokens_in || sig.tokens_out) {
        details += ` | Tokens: ${sig.tokens_in || 0}→${sig.tokens_out || 0}`;
    }
    if (sig.cost_usd) {
        details += ` | Cost: $${sig.cost_usd.toFixed(5)}`;
    }

    return `
        <div class="pipeline-signal ${sig.success ? '' : 'error'}">
            <span class="pipeline-signal-time">${time}</span>
            <div class="pipeline-signal-type">
                <span class="pipeline-signal-badge ${signalClass}">${sig.signal_type}</span>
            </div>
            <div class="pipeline-signal-content">
                <div class="pipeline-signal-summary">${escapeHtml(sig.summary)}</div>
                ${details ? `<div class="pipeline-signal-details">${details}</div>` : ''}
                ${sig.error ? `<div class="pipeline-signal-details" style="color: var(--accent-error)">Error: ${escapeHtml(sig.error)}</div>` : ''}
            </div>
            <span class="pipeline-signal-latency">${sig.latency_ms?.toFixed(0) || '-'}ms</span>
        </div>
    `;
}

// =============================================================================
// E2E Testing
// =============================================================================

async function runQuickE2ETest() {
    const statusEl = document.getElementById('e2e-status');
    const resultsEl = document.getElementById('e2e-results');

    statusEl.style.display = 'block';
    resultsEl.style.display = 'none';
    document.getElementById('e2e-progress-text').textContent = 'Running quick tests...';

    try {
        const response = await fetch(`${API_BASE}/api/v1/e2e/quick`, {
            method: 'POST'
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        displayE2EResults(data);
    } catch (e) {
        console.error('E2E quick test failed:', e);
        document.getElementById('e2e-progress-text').textContent = `Error: ${e.message}`;
    }
}

async function runE2ETestSuite() {
    const statusEl = document.getElementById('e2e-status');
    const resultsEl = document.getElementById('e2e-results');

    // Get selected categories
    const categories = [];
    if (document.getElementById('e2e-cat-instant').checked) categories.push('instant');
    if (document.getElementById('e2e-cat-action').checked) categories.push('action');
    if (document.getElementById('e2e-cat-interaction').checked) categories.push('interaction');

    if (categories.length === 0) {
        alert('Please select at least one test category');
        return;
    }

    statusEl.style.display = 'block';
    resultsEl.style.display = 'none';
    document.getElementById('e2e-progress-text').textContent = 'Starting test suite...';

    try {
        const response = await fetch(`${API_BASE}/api/v1/e2e/run`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                suite_name: 'dashboard_run',
                categories: categories,
                include_llm_tests: categories.includes('interaction'),
                delay_between_tests_ms: 100
            })
        });

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();
        displayE2EResults(data);
    } catch (e) {
        console.error('E2E test suite failed:', e);
        document.getElementById('e2e-progress-text').textContent = `Error: ${e.message}`;
    }
}

function displayE2EResults(data) {
    const statusEl = document.getElementById('e2e-status');
    const resultsEl = document.getElementById('e2e-results');
    const testListEl = document.getElementById('e2e-test-list');

    statusEl.style.display = 'none';
    resultsEl.style.display = 'block';

    // Update summary stats
    document.getElementById('e2e-passed').textContent = data.passed || 0;
    document.getElementById('e2e-failed').textContent = data.failed || 0;
    document.getElementById('e2e-latency').textContent = Math.round(data.total_latency_ms || 0);

    // Render test results
    if (!data.test_results || data.test_results.length === 0) {
        testListEl.innerHTML = '<p class="text-muted">No test results</p>';
        return;
    }

    testListEl.innerHTML = data.test_results.map(test => {
        const resultClass = test.result === 'pass' ? 'passed' :
            test.result === 'fail' ? 'failed' : 'error';
        const resultIcon = test.result === 'pass' ? '✓' :
            test.result === 'fail' ? '✗' : '⚠';

        const assertionsHtml = test.assertions.map(a => {
            const aClass = a.passed ? 'passed' : 'failed';
            const aIcon = a.passed ? '✓' : '✗';
            return `<div class="e2e-assertion ${aClass}">
                <span class="e2e-assertion-icon">${aIcon}</span>
                <span class="e2e-assertion-type">${a.type}</span>
                <span class="e2e-assertion-msg">${escapeHtml(a.message)}</span>
            </div>`;
        }).join('');

        return `
            <div class="e2e-test-item ${resultClass}">
                <div class="e2e-test-header">
                    <span class="e2e-test-icon">${resultIcon}</span>
                    <span class="e2e-test-name">${escapeHtml(test.name)}</span>
                    <span class="e2e-test-category">${test.category}</span>
                    <span class="e2e-test-latency">${test.latency_ms.toFixed(0)}ms</span>
                </div>
                <div class="e2e-test-input">"${escapeHtml(test.input_text)}"</div>
                <div class="e2e-test-response">
                    <strong>${test.agent_used}</strong>: "${escapeHtml(test.response_text || '')}"
                </div>
                <div class="e2e-assertions">${assertionsHtml}</div>
                ${test.error ? `<div class="e2e-test-error">Error: ${escapeHtml(test.error)}</div>` : ''}
            </div>
        `;
    }).join('');

    // Also refresh traces to show new test traces
    loadTraces();
}


// =============================================================================
// LLM Provider Configuration
// =============================================================================

let providersData = [];
let currentProvider = null;

async function loadProviders() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/config/providers`);
        const data = await response.json();

        providersData = data.providers || [];
        document.getElementById('providers-configured').textContent = data.configured_count || 0;
        document.getElementById('providers-enabled').textContent = data.enabled_count || 0;

        renderProvidersList();
    } catch (e) {
        console.error('Failed to load providers:', e);
        document.getElementById('providers-list').innerHTML = `
            <div class="error-message">Failed to load providers: ${e.message}</div>
        `;
    }
}

async function loadProviderStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/config/providers/status`);
        return await response.json();
    } catch (e) {
        console.error('Failed to load provider status:', e);
        return { statuses: [] };
    }
}

function renderProvidersList() {
    const container = document.getElementById('providers-list');

    if (!providersData.length) {
        container.innerHTML = '<p class="text-muted">No providers available</p>';
        return;
    }

    // First load status to show which are configured
    loadProviderStatus().then(statusData => {
        const statusMap = new Map(
            statusData.statuses?.map(s => [s.provider_type, s]) || []
        );

        container.innerHTML = providersData.map(provider => {
            const status = statusMap.get(provider.provider_type) || {};
            const isConfigured = status.configured;
            const isEnabled = status.enabled;

            const statusClass = isEnabled ? 'enabled' : isConfigured ? 'configured' : 'not-configured';
            const statusText = isEnabled ? '✓ Enabled' : isConfigured ? '⏸ Configured' : 'Not configured';
            const statusIcon = getProviderIcon(provider.provider_type);

            return `
                <div class="provider-card ${statusClass}" data-provider="${provider.provider_type}">
                    <div class="provider-icon">${statusIcon}</div>
                    <div class="provider-info">
                        <h4>${provider.display_name}</h4>
                        <p class="provider-desc">${provider.description}</p>
                        <span class="provider-status">${statusText}</span>
                    </div>
                    <div class="provider-actions">
                        <button class="btn btn-small" onclick="openProviderSetup('${provider.provider_type}')">
                            ${isConfigured ? '⚙️ Configure' : '➕ Setup'}
                        </button>
                        ${isConfigured ? `
                            <button class="btn btn-small ${isEnabled ? 'btn-warning' : 'btn-primary'}"
                                    onclick="toggleProvider('${provider.provider_type}', ${!isEnabled})">
                                ${isEnabled ? '⏸ Disable' : '▶️ Enable'}
                            </button>
                        ` : ''}
                    </div>
                </div>
            `;
        }).join('');
    });
}

function getProviderIcon(providerType) {
    const icons = {
        'openrouter': '🔀',
        'openai': '🧠',
        'anthropic': '🤖',
        'azure': '☁️',
        'google': '🌐',
        'xai': '🚀',
        'deepseek': '🔍',
        'huggingface': '🤗',
        'bedrock': '🏔️',
        'together': '🤝',
        'mistral': '🌊',
        'groq': '⚡'
    };
    return icons[providerType] || '🤖';
}

function openProviderSetup(providerType) {
    const provider = providersData.find(p => p.provider_type === providerType);
    if (!provider) return;

    currentProvider = provider;

    // Update modal content
    document.getElementById('provider-modal-title').textContent = `Configure ${provider.display_name}`;
    document.getElementById('provider-type').value = providerType;

    // Setup instructions
    const stepsEl = document.getElementById('provider-setup-steps');
    stepsEl.innerHTML = provider.setup_instructions.map(step => `<li>${step}</li>`).join('');

    // Links
    document.getElementById('provider-docs-link').href = provider.docs_url;
    document.getElementById('provider-key-link').href = provider.api_key_url;

    // Secret fields
    const secretFieldsEl = document.getElementById('provider-secret-fields');
    secretFieldsEl.innerHTML = provider.secret_fields.map(field => `
        <div class="form-group">
            <label>${field.display_name} ${field.required ? '<span class="required">*</span>' : ''}</label>
            <input type="password"
                   class="form-control"
                   id="secret-${field.name}"
                   placeholder="${field.placeholder}"
                   ${field.required ? 'required' : ''}>
            <small class="form-help">${field.description}</small>
        </div>
    `).join('');

    // Config fields
    const configFieldsEl = document.getElementById('provider-config-fields');
    if (provider.config_fields && provider.config_fields.length) {
        configFieldsEl.innerHTML = '<h5 style="margin-top: 16px;">Additional Settings</h5>' +
            provider.config_fields.map(field => {
                if (field.field_type === 'select') {
                    return `
                        <div class="form-group">
                            <label>${field.display_name}</label>
                            <select class="form-control" id="config-${field.name}">
                                ${field.options.map(opt =>
                        `<option value="${opt}" ${opt === field.default ? 'selected' : ''}>${opt}</option>`
                    ).join('')}
                            </select>
                        </div>
                    `;
                }
                return `
                    <div class="form-group">
                        <label>${field.display_name}</label>
                        <input type="${field.field_type === 'number' ? 'number' : 'text'}"
                               class="form-control"
                               id="config-${field.name}"
                               value="${field.default || ''}"
                               placeholder="${field.placeholder || ''}">
                        <small class="form-help">${field.description}</small>
                    </div>
                `;
            }).join('');
    } else {
        configFieldsEl.innerHTML = '';
    }

    // Pricing notes
    document.getElementById('provider-pricing').innerHTML = provider.pricing_notes ?
        `<p class="pricing-note">💰 ${provider.pricing_notes}</p>` : '';

    // Clear test result
    document.getElementById('provider-test-result').style.display = 'none';

    // Show modal
    document.getElementById('provider-modal').style.display = 'flex';
}

async function testProviderConnection() {
    if (!currentProvider) return;

    const resultEl = document.getElementById('provider-test-result');
    resultEl.style.display = 'block';
    resultEl.className = 'test-result testing';
    resultEl.innerHTML = '🔄 Testing connection...';

    // First save the credentials temporarily for the test
    const secrets = {};
    currentProvider.secret_fields.forEach(field => {
        const value = document.getElementById(`secret-${field.name}`)?.value;
        if (value) secrets[field.name] = value;
    });

    if (Object.keys(secrets).length === 0) {
        resultEl.className = 'test-result error';
        resultEl.innerHTML = '❌ Please enter at least one credential to test';
        return;
    }

    // Save first, then test
    try {
        // Save credentials
        const config = {};
        currentProvider.config_fields?.forEach(field => {
            const value = document.getElementById(`config-${field.name}`)?.value;
            if (value) config[field.name] = value;
        });

        await fetch(`${API_BASE}/api/v1/config/providers/setup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider_type: currentProvider.provider_type,
                secrets: secrets,
                config: config
            })
        });

        // Now test
        const testResponse = await fetch(`${API_BASE}/api/v1/config/providers/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider_type: currentProvider.provider_type
            })
        });

        const testResult = await testResponse.json();

        if (testResult.success) {
            resultEl.className = 'test-result success';
            resultEl.innerHTML = `✅ ${testResult.message}` +
                (testResult.latency_ms ? ` (${testResult.latency_ms.toFixed(0)}ms)` : '');
        } else {
            resultEl.className = 'test-result error';
            resultEl.innerHTML = `❌ ${testResult.message}`;
        }
    } catch (e) {
        resultEl.className = 'test-result error';
        resultEl.innerHTML = `❌ Test failed: ${e.message}`;
    }
}

async function saveProvider(e) {
    e.preventDefault();

    if (!currentProvider) return;

    const secrets = {};
    currentProvider.secret_fields.forEach(field => {
        const value = document.getElementById(`secret-${field.name}`)?.value;
        if (value) secrets[field.name] = value;
    });

    const config = {};
    currentProvider.config_fields?.forEach(field => {
        const value = document.getElementById(`config-${field.name}`)?.value;
        if (value) config[field.name] = value;
    });

    try {
        const response = await fetch(`${API_BASE}/api/v1/config/providers/setup`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider_type: currentProvider.provider_type,
                secrets: secrets,
                config: config
            })
        });

        const result = await response.json();

        if (response.ok && result.success) {
            const providerName = currentProvider?.display_name || currentProvider?.provider_type || 'Provider';
            closeProviderModal();
            loadProviders(); // Refresh the list

            // Show success message
            if (typeof addActivityItem === 'function') {
                addActivityItem({
                    type: 'system',
                    message: `Provider ${providerName} configured successfully`,
                    timestamp: new Date().toISOString()
                });
            }
        } else {
            alert(`Failed to save: ${result.detail || result.message || 'Unknown error'}`);
        }
    } catch (e) {
        alert(`Error saving provider: ${e.message}`);
    }
}

async function toggleProvider(providerType, enable) {
    try {
        await fetch(`${API_BASE}/api/v1/config/providers/enable`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                provider_type: providerType,
                enabled: enable
            })
        });
        loadProviders(); // Refresh
    } catch (e) {
        console.error('Failed to toggle provider:', e);
    }
}

function closeProviderModal() {
    document.getElementById('provider-modal').style.display = 'none';
    currentProvider = null;
}

// Initialize provider config UI
function initProviderConfig() {
    document.getElementById('refresh-providers')?.addEventListener('click', loadProviders);
    document.getElementById('close-provider-modal')?.addEventListener('click', closeProviderModal);
    document.getElementById('test-provider-btn')?.addEventListener('click', testProviderConnection);
    document.getElementById('provider-setup-form')?.addEventListener('submit', saveProvider);

    // Close modal on background click
    document.getElementById('provider-modal')?.addEventListener('click', (e) => {
        if (e.target.id === 'provider-modal') {
            closeProviderModal();
        }
    });

    // Load providers when config page is shown
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => {
            if (link.dataset.page === 'config') {
                loadProviders();
            }
        });
    });

    // Also load if we're starting on config page
    if (window.location.hash === '#config') {
        loadProviders();
    }
}


// =============================================================================
// Model Selection Configuration
// =============================================================================

let availableModels = [];
let activitiesData = [];
let showFreeOnly = false;

async function loadModels() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/config/models`);
        const data = await response.json();
        availableModels = data.models || [];

        const countDisplay = document.getElementById('models-count-display');
        if (countDisplay) {
            countDisplay.textContent = `${data.total_count} models available (${data.free_count} free)`;
        }

        return availableModels;
    } catch (e) {
        console.error('Failed to load models:', e);
        return [];
    }
}

async function loadActivities() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/config/activities`);
        const data = await response.json();
        activitiesData = data.activities || [];
        renderActivities(data.groups || {});
    } catch (e) {
        console.error('Failed to load activities:', e);
        document.getElementById('activities-list').innerHTML = `
            <div class="error-message">Failed to load activities: ${e.message}</div>
        `;
    }
}

function renderActivities(groups) {
    const container = document.getElementById('activities-list');
    if (!container) return;

    const agentIcons = {
        'meta': '🎯',
        'action': '🏠',
        'interaction': '💬',
        'memory': '🧠',
        'instant': '⚡'
    };

    const agentDescriptions = {
        'meta': 'Intent Classification (runs on every request)',
        'action': 'Device Control & Home Automation',
        'interaction': 'Conversations & Personality',
        'memory': 'Memory Generation & Retrieval',
        'instant': 'Quick Responses (time, date, etc.)'
    };

    let html = '';

    for (const [agent, activityNames] of Object.entries(groups)) {
        const activities = activityNames
            .map(name => activitiesData.find(a => a.activity === name))
            .filter(Boolean);

        if (activities.length === 0) continue;

        html += `
            <div class="activity-group" data-agent="${agent}">
                <div class="activity-group-header" onclick="toggleActivityGroup('${agent}')">
                    <span class="activity-group-icon">${agentIcons[agent] || '🤖'}</span>
                    <h4>${agent.charAt(0).toUpperCase() + agent.slice(1)}Agent</h4>
                    <span class="activity-group-desc">${agentDescriptions[agent] || ''}</span>
                    <span class="activity-group-toggle">▼</span>
                </div>
                <div class="activity-group-items">
                    ${activities.map(activity => renderActivityItem(activity)).join('')}
                </div>
            </div>
        `;
    }

    container.innerHTML = html || '<p class="no-models-message">No activities configured</p>';

    // Initialize all model dropdowns
    initModelDropdowns();
}

function renderActivityItem(activity) {
    return `
        <div class="activity-item" data-activity="${activity.activity}">
            <div class="activity-info">
                <span class="activity-name">${activity.activity}</span>
                <span class="activity-desc">${activity.description}</span>
            </div>
            <div class="activity-model-select">
                <div class="model-search-container">
                    <input type="text"
                           class="model-search-input"
                           data-activity="${activity.activity}"
                           value="${activity.model}"
                           placeholder="Search models..."
                           autocomplete="off">
                    <span class="model-price-badge" data-activity="${activity.activity}">
                        ${getModelPriceBadge(activity.model)}
                    </span>
                    <div class="model-dropdown" data-activity="${activity.activity}"></div>
                </div>
            </div>
            <span class="activity-priority ${activity.priority}">${activity.priority}</span>
        </div>
    `;
}

function getModelPriceBadge(modelId) {
    const model = availableModels.find(m => m.id === modelId);
    if (!model) return '';
    if (model.is_free) return '<span class="free">FREE</span>';
    const totalPrice = model.pricing_prompt + model.pricing_completion;
    return `$${totalPrice.toFixed(2)}/M`;
}

function initModelDropdowns() {
    document.querySelectorAll('.model-search-input').forEach(input => {
        const activityName = input.dataset.activity;
        const dropdown = document.querySelector(`.model-dropdown[data-activity="${activityName}"]`);

        // Focus - show dropdown
        input.addEventListener('focus', () => {
            renderModelDropdown(dropdown, input.value, activityName);
            dropdown.classList.add('visible');
        });

        // Blur - hide dropdown (with delay for click)
        input.addEventListener('blur', () => {
            setTimeout(() => dropdown.classList.remove('visible'), 200);
        });

        // Input - filter models
        input.addEventListener('input', () => {
            renderModelDropdown(dropdown, input.value, activityName);
        });

        // Keyboard navigation
        input.addEventListener('keydown', (e) => {
            handleDropdownKeyboard(e, dropdown, input, activityName);
        });
    });
}

function renderModelDropdown(dropdown, searchTerm, activityName) {
    let filteredModels = availableModels;

    // Filter by search term
    if (searchTerm) {
        const term = searchTerm.toLowerCase();
        filteredModels = filteredModels.filter(m =>
            m.id.toLowerCase().includes(term) ||
            m.name.toLowerCase().includes(term)
        );
    }

    // Filter by free if checkbox is checked
    if (showFreeOnly) {
        filteredModels = filteredModels.filter(m => m.is_free);
    }

    // Limit to 50 results
    filteredModels = filteredModels.slice(0, 50);

    if (filteredModels.length === 0) {
        dropdown.innerHTML = '<div class="model-option">No models found</div>';
        return;
    }

    dropdown.innerHTML = filteredModels.map((model, index) => `
        <div class="model-option ${index === 0 ? 'highlighted' : ''}"
             data-model-id="${model.id}"
             data-activity="${activityName}"
             onclick="selectModel('${model.id}', '${activityName}')">
            <div class="model-option-name">${model.name}</div>
            <div class="model-option-details">
                <span class="model-option-price ${model.is_free ? 'free' : ''}">
                    ${model.is_free ? 'FREE' : `$${(model.pricing_prompt + model.pricing_completion).toFixed(2)}/M tokens`}
                </span>
                <span class="model-option-context">${(model.context_length / 1000).toFixed(0)}K context</span>
            </div>
        </div>
    `).join('');
}

function handleDropdownKeyboard(e, dropdown, input, activityName) {
    const options = dropdown.querySelectorAll('.model-option[data-model-id]');
    const highlighted = dropdown.querySelector('.model-option.highlighted');
    let currentIndex = Array.from(options).indexOf(highlighted);

    switch (e.key) {
        case 'ArrowDown':
            e.preventDefault();
            if (currentIndex < options.length - 1) {
                options[currentIndex]?.classList.remove('highlighted');
                options[currentIndex + 1]?.classList.add('highlighted');
                options[currentIndex + 1]?.scrollIntoView({ block: 'nearest' });
            }
            break;
        case 'ArrowUp':
            e.preventDefault();
            if (currentIndex > 0) {
                options[currentIndex]?.classList.remove('highlighted');
                options[currentIndex - 1]?.classList.add('highlighted');
                options[currentIndex - 1]?.scrollIntoView({ block: 'nearest' });
            }
            break;
        case 'Enter':
            e.preventDefault();
            if (highlighted) {
                const modelId = highlighted.dataset.modelId;
                selectModel(modelId, activityName);
            }
            break;
        case 'Escape':
            dropdown.classList.remove('visible');
            input.blur();
            break;
    }
}

async function selectModel(modelId, activityName) {
    // Update UI immediately
    const input = document.querySelector(`.model-search-input[data-activity="${activityName}"]`);
    const priceBadge = document.querySelector(`.model-price-badge[data-activity="${activityName}"]`);

    if (input) input.value = modelId;
    if (priceBadge) priceBadge.innerHTML = getModelPriceBadge(modelId);

    // Close dropdown
    const dropdown = document.querySelector(`.model-dropdown[data-activity="${activityName}"]`);
    if (dropdown) dropdown.classList.remove('visible');

    // Save to backend
    try {
        const response = await fetch(`${API_BASE}/api/v1/config/activities/${activityName}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ model: modelId })
        });

        if (!response.ok) {
            throw new Error('Failed to save');
        }

        console.log(`Updated ${activityName} to use ${modelId}`);
    } catch (e) {
        console.error('Failed to update activity:', e);
        alert(`Failed to save model selection: ${e.message}`);
    }
}

function toggleActivityGroup(agent) {
    const group = document.querySelector(`.activity-group[data-agent="${agent}"]`);
    if (group) {
        group.classList.toggle('collapsed');
    }
}

function initModelSelection() {
    // Free models filter
    document.getElementById('show-free-only')?.addEventListener('change', (e) => {
        showFreeOnly = e.target.checked;
        // Re-render all open dropdowns
        document.querySelectorAll('.model-dropdown.visible').forEach(dropdown => {
            const activityName = dropdown.dataset.activity;
            const input = document.querySelector(`.model-search-input[data-activity="${activityName}"]`);
            if (input) {
                renderModelDropdown(dropdown, input.value, activityName);
            }
        });
    });

    // Refresh models button
    document.getElementById('refresh-models')?.addEventListener('click', async () => {
        await fetch(`${API_BASE}/api/v1/config/models/refresh`, { method: 'POST' });
        await loadModels();
        // Reload activities to refresh price badges
        await loadActivities();
    });

    // Load when models config section is shown
    document.querySelectorAll('.config-nav li').forEach(item => {
        item.addEventListener('click', () => {
            if (item.dataset.config === 'models') {
                loadModels().then(() => loadActivities());
            }
        });
    });
}


// Add to initialization
document.addEventListener('DOMContentLoaded', () => {
    initProviderConfig();
    initModelSelection();
});
