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
