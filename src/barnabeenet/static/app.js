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
    // Handle wrapped messages from different WS endpoints
    const messageType = data.type;
    const payload = data.data || data;

    if (messageType === 'signal' || payload.signal_type) {
        // LLM/Pipeline signal from /ws/activity
        const signalData = messageType === 'signal' ? payload : data;
        addActivityItem({
            type: signalData.signal_type || signalData.event_type || 'system',
            message: formatSignalMessage(signalData),
            timestamp: signalData.timestamp,
            latency: signalData.latency_ms,
            signal_id: signalData.signal_id,
            model: signalData.model,
            trace_id: signalData.trace_id,
            agent: signalData.agent_type || signalData.agent,
            tokens_in: signalData.input_tokens,
            tokens_out: signalData.output_tokens,
            cost: signalData.cost_usd
        });

        // Update live stats
        updateLiveStats(signalData);

        // Track active trace for real-time updates
        if (signalData.trace_id) {
            if (!activeTraces.has(signalData.trace_id)) {
                activeTraces.set(signalData.trace_id, {
                    trace_id: signalData.trace_id,
                    signals: [],
                    started_at: signalData.timestamp
                });
            }
            activeTraces.get(signalData.trace_id).signals.push(signalData);
        }

        // Refresh traces list for new/completed traces
        if (signalData.signal_type === 'request_start' || signalData.signal_type === 'request_complete') {
            loadTraces();
        }
    } else if (messageType === 'activity') {
        // Activity log message from /ws/dashboard (including HA state changes)
        addActivityItem({
            type: payload.type || 'system',
            message: payload.title || payload.detail || '',
            timestamp: payload.timestamp,
            source: payload.source,
            trace_id: payload.trace_id,
            duration_ms: payload.duration_ms
        });

        // Update live stats
        updateLiveStats({ signal_type: payload.type });
    } else if (messageType === 'heartbeat' || messageType === 'ping' || messageType === 'pong') {
        // Heartbeat - ignore
    } else if (messageType === 'status') {
        // Connection status - could update UI indicator
        console.log('WebSocket status:', payload);
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

    // Check if this is an LLM signal that can be expanded
    const isLLMSignal = data.signal_id && (data.type === 'llm_request' || data.type === 'llm.request' || data.type === 'llm_call');
    const isHAEvent = data.type && (data.type.startsWith('ha.') || data.type === 'ha_state_change');

    let expandButton = '';
    if (isLLMSignal) {
        expandButton = `<button class="activity-expand-btn" onclick="event.stopPropagation(); showLLMInspector('${data.signal_id}')" title="View LLM details">🔍</button>`;
    }

    // Build token/cost badge for LLM signals
    let tokenBadge = '';
    if (data.tokens_in !== undefined || data.tokens_out !== undefined) {
        const tokensIn = data.tokens_in ?? '?';
        const tokensOut = data.tokens_out ?? '?';
        const cost = data.cost ? `$${data.cost.toFixed(5)}` : '';
        tokenBadge = `<span class="activity-tokens">📥${tokensIn} 📤${tokensOut} ${cost}</span>`;
    }

    // Build agent badge
    let agentBadge = '';
    if (data.agent) {
        agentBadge = `<span class="activity-agent">${data.agent}</span>`;
    }

    item.innerHTML = `
        <span class="activity-time">${time}</span>
        <span class="activity-badge ${data.type}">${formatActivityType(data.type)}</span>
        ${agentBadge}
        <span class="activity-message">${escapeHtml(data.message)}</span>
        ${tokenBadge}
        ${data.latency ? `<span class="activity-latency">${data.latency.toFixed(0)}ms</span>` : ''}
        ${expandButton}
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

function formatActivityType(type) {
    // Clean up activity type for display
    if (!type) return 'unknown';
    return type.replace(/\./g, ' ').replace(/_/g, ' ');
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
// Live Statistics
// =============================================================================

let liveStats = {
    total: 0,
    perSecond: 0,
    llm: 0,
    ha: 0,
    lastMinute: []
};

function updateLiveStats(data) {
    liveStats.total++;
    liveStats.lastMinute.push(Date.now());
    liveStats.lastMinute = liveStats.lastMinute.filter(t => t > Date.now() - 60000);
    liveStats.perSecond = (liveStats.lastMinute.length / 60).toFixed(1);

    const signalType = data.signal_type || data.activity_type || '';
    if (signalType.startsWith('llm')) {
        liveStats.llm++;
    }
    if (signalType.startsWith('ha')) {
        liveStats.ha++;
    }

    // Update UI if elements exist
    const perSecEl = document.getElementById('events-per-sec');
    const totalEl = document.getElementById('events-total');
    const llmEl = document.getElementById('events-llm');
    const haEl = document.getElementById('events-ha');

    if (perSecEl) perSecEl.textContent = liveStats.perSecond;
    if (totalEl) totalEl.textContent = liveStats.total;
    if (llmEl) llmEl.textContent = liveStats.llm;
    if (haEl) haEl.textContent = liveStats.ha;
}

// =============================================================================
// LLM Inspector Modal
// =============================================================================

async function showLLMInspector(signalId) {
    // Show loading state in modal
    const existingModal = document.getElementById('llm-inspector-modal');
    if (existingModal) {
        existingModal.remove();
    }

    const modal = document.createElement('div');
    modal.id = 'llm-inspector-modal';
    modal.className = 'modal llm-inspector-modal';
    modal.style.display = 'flex';
    modal.innerHTML = `
        <div class="modal-content modal-large">
            <div class="modal-header">
                <h3>🧠 LLM Request Inspector</h3>
                <button class="btn btn-small" onclick="document.getElementById('llm-inspector-modal').remove()">✕</button>
            </div>
            <div class="modal-body">
                <p class="text-muted">Loading signal details...</p>
            </div>
        </div>
    `;
    document.body.appendChild(modal);

    // Close on backdrop click
    modal.addEventListener('click', (e) => {
        if (e.target === modal) {
            modal.remove();
        }
    });

    try {
        const response = await fetch(`${API_BASE}/api/v1/dashboard/signals/${signalId}`);
        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }
        const signal = await response.json();
        renderLLMInspector(modal, signal);
    } catch (e) {
        modal.querySelector('.modal-body').innerHTML = `
            <div class="error-message">Failed to load signal: ${e.message}</div>
        `;
    }
}

function renderLLMInspector(modal, signal) {
    const time = new Date(signal.timestamp).toLocaleString();
    const latency = signal.latency_ms ? `${signal.latency_ms.toFixed(0)}ms` : 'N/A';
    const inputTokens = signal.input_tokens ?? 'N/A';
    const outputTokens = signal.output_tokens ?? 'N/A';
    const totalTokens = signal.total_tokens ?? 'N/A';
    const cost = signal.cost_usd ? `$${signal.cost_usd.toFixed(6)}` : 'N/A';

    // Build messages display
    let messagesHtml = '';
    if (signal.messages && signal.messages.length > 0) {
        messagesHtml = signal.messages.map(msg => {
            const role = msg.role || 'unknown';
            const content = msg.content || '';
            const roleClass = role === 'system' ? 'llm-msg-system' :
                role === 'user' ? 'llm-msg-user' : 'llm-msg-assistant';
            const roleIcon = role === 'system' ? '⚙️' :
                role === 'user' ? '👤' : '🤖';
            return `
                <div class="llm-message ${roleClass}">
                    <div class="llm-message-header">
                        <span class="llm-message-icon">${roleIcon}</span>
                        <span class="llm-message-role">${role}</span>
                    </div>
                    <pre class="llm-message-content">${escapeHtml(content)}</pre>
                </div>
            `;
        }).join('');
    }

    // Build system prompt display (if separate)
    let systemPromptHtml = '';
    if (signal.system_prompt) {
        systemPromptHtml = `
            <div class="llm-section">
                <h4>⚙️ System Prompt</h4>
                <pre class="llm-system-prompt">${escapeHtml(signal.system_prompt)}</pre>
            </div>
        `;
    }

    // Build injected context display
    let contextHtml = '';
    if (signal.injected_context && Object.keys(signal.injected_context).length > 0) {
        contextHtml = `
            <div class="llm-section">
                <h4>📋 Injected Context</h4>
                <pre class="llm-context">${escapeHtml(JSON.stringify(signal.injected_context, null, 2))}</pre>
            </div>
        `;
    }

    modal.querySelector('.modal-body').innerHTML = `
        <div class="llm-inspector-content">
            <!-- Header Card -->
            <div class="llm-inspector-header">
                <div class="llm-inspector-title">
                    <span class="llm-agent-badge">${signal.agent_type || 'Unknown'}</span>
                    <span class="llm-model-badge">${signal.model || 'Unknown Model'}</span>
                    <span class="llm-provider-badge">${signal.provider || ''}</span>
                </div>
                <div class="llm-inspector-meta">
                    <span class="llm-latency">${latency}</span>
                    <span class="llm-time">${time}</span>
                </div>
            </div>

            <!-- Metrics Bar -->
            <div class="llm-metrics-bar">
                <div class="llm-metric">
                    <span class="llm-metric-icon">📥</span>
                    <span class="llm-metric-value">${inputTokens}</span>
                    <span class="llm-metric-label">Input Tokens</span>
                </div>
                <div class="llm-metric">
                    <span class="llm-metric-icon">📤</span>
                    <span class="llm-metric-value">${outputTokens}</span>
                    <span class="llm-metric-label">Output Tokens</span>
                </div>
                <div class="llm-metric">
                    <span class="llm-metric-icon">📊</span>
                    <span class="llm-metric-value">${totalTokens}</span>
                    <span class="llm-metric-label">Total Tokens</span>
                </div>
                <div class="llm-metric">
                    <span class="llm-metric-icon">💰</span>
                    <span class="llm-metric-value">${cost}</span>
                    <span class="llm-metric-label">Cost</span>
                </div>
                <div class="llm-metric">
                    <span class="llm-metric-icon">🌡️</span>
                    <span class="llm-metric-value">${signal.temperature ?? 'N/A'}</span>
                    <span class="llm-metric-label">Temperature</span>
                </div>
            </div>

            ${systemPromptHtml}

            <!-- Messages -->
            <div class="llm-section">
                <h4>💬 Conversation</h4>
                <div class="llm-messages-container">
                    ${messagesHtml || '<p class="text-muted">No messages captured</p>'}
                </div>
            </div>

            <!-- Response -->
            <div class="llm-section">
                <h4>📥 LLM Response</h4>
                <pre class="llm-response">${escapeHtml(signal.response_text || 'No response')}</pre>
            </div>

            ${contextHtml}

            <!-- Error (if any) -->
            ${signal.error ? `
                <div class="llm-section llm-error-section">
                    <h4>❌ Error</h4>
                    <div class="llm-error">
                        <strong>${signal.error_type || 'Error'}:</strong> ${escapeHtml(signal.error)}
                    </div>
                </div>
            ` : ''}

            <!-- Context Info -->
            <div class="llm-section llm-context-info">
                <h4>📌 Request Context</h4>
                <div class="llm-context-grid">
                    <div class="llm-context-item">
                        <span class="label">Signal ID:</span>
                        <span class="value">${signal.signal_id}</span>
                    </div>
                    <div class="llm-context-item">
                        <span class="label">Trace ID:</span>
                        <span class="value">${signal.trace_id || 'N/A'}</span>
                    </div>
                    <div class="llm-context-item">
                        <span class="label">Speaker:</span>
                        <span class="value">${signal.speaker || 'Unknown'}</span>
                    </div>
                    <div class="llm-context-item">
                        <span class="label">Room:</span>
                        <span class="value">${signal.room || 'Unknown'}</span>
                    </div>
                    <div class="llm-context-item">
                        <span class="label">User Input:</span>
                        <span class="value">${signal.user_input || 'N/A'}</span>
                    </div>
                </div>
            </div>
        </div>
    `;
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

    // Build waterfall timeline
    const waterfallHtml = renderWaterfallTimeline(trace);

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

        ${waterfallHtml}

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

function renderWaterfallTimeline(trace) {
    if (!trace.signals || trace.signals.length === 0) {
        return '';
    }

    const totalMs = trace.total_latency_ms || 1;

    // Calculate cumulative timing from signals
    // Signals are in order, so we can use their timestamps to calculate positions
    const traceStart = new Date(trace.started_at).getTime();

    const rows = trace.signals.map((signal, index) => {
        const signalTime = new Date(signal.timestamp).getTime();
        const startOffset = signalTime - traceStart;
        const duration = signal.latency_ms || 0;

        const startPercent = Math.max(0, (startOffset / totalMs) * 100);
        const widthPercent = Math.max(1, (duration / totalMs) * 100);

        // Determine bar class based on signal type
        let barClass = 'llm';
        const sigType = (signal.signal_type || '').toLowerCase();
        if (sigType.includes('meta')) barClass = 'meta';
        else if (sigType.includes('instant')) barClass = 'instant';
        else if (sigType.includes('action')) barClass = 'action';
        else if (sigType.includes('interaction')) barClass = 'interaction';
        else if (sigType.includes('memory')) barClass = 'memory';
        else if (sigType.includes('tts')) barClass = 'tts';
        else if (sigType.includes('stt')) barClass = 'stt';

        const label = `${signal.component || signal.signal_type}: ${signal.summary || ''}`.substring(0, 40);

        return `
            <div class="timeline-row">
                <span class="step-label" title="${escapeHtml(signal.summary || signal.signal_type)}">${escapeHtml(label)}</span>
                <div class="timeline-bar-container">
                    <div class="timeline-bar ${barClass}"
                         style="left: ${startPercent.toFixed(1)}%; width: ${Math.min(widthPercent, 100 - startPercent).toFixed(1)}%">
                    </div>
                    <span class="step-duration">${duration?.toFixed(0) || 0}ms</span>
                </div>
            </div>
        `;
    }).join('');

    return `
        <div class="waterfall-timeline">
            <h4>⏱️ Waterfall Timeline (${totalMs.toFixed(0)}ms total)</h4>
            ${rows}
        </div>
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
        const response = await fetch(`${API_BASE}/api/v1/config/models?provider=all`);
        const data = await response.json();
        availableModels = data.models || [];

        const countDisplay = document.getElementById('models-count-display');
        if (countDisplay) {
            const workingText = data.working_count > 0 ? `, ${data.working_count} verified` : '';
            const providersText = data.providers_included?.length > 1
                ? ` from ${data.providers_included.length} providers`
                : '';
            countDisplay.textContent = `${data.total_count} models (${data.free_count} free${workingText})${providersText}`;
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

    // Filter out failed models (they shouldn't appear in the list)
    filteredModels = filteredModels.filter(m => m.health_status !== 'failed');

    // Filter by search term
    if (searchTerm) {
        const term = searchTerm.toLowerCase();
        filteredModels = filteredModels.filter(m =>
            m.id.toLowerCase().includes(term) ||
            m.name.toLowerCase().includes(term) ||
            (m.provider_display || '').toLowerCase().includes(term)
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

    dropdown.innerHTML = filteredModels.map((model, index) => {
        const healthClass = model.health_status === 'working' ? 'health-working' :
            model.health_status === 'failed' ? 'health-failed' : '';
        const healthIcon = model.health_status === 'working' ? '✓' :
            model.health_status === 'failed' ? '✗' : '';
        const providerBadge = model.provider_display || model.provider || 'Unknown';

        return `
            <div class="model-option ${index === 0 ? 'highlighted' : ''} ${healthClass}"
                 data-model-id="${model.id}"
                 data-activity="${activityName}"
                 onclick="selectModel('${model.id}', '${activityName}')">
                <div class="model-option-header">
                    <span class="model-option-name">${model.name}</span>
                    <span class="model-provider-badge">${providerBadge}</span>
                </div>
                <div class="model-option-details">
                    <span class="model-option-price ${model.is_free ? 'free' : ''}">
                        ${model.is_free ? 'FREE' : `$${(model.pricing_prompt + model.pricing_completion).toFixed(2)}/M`}
                    </span>
                    <span class="model-option-context">${(model.context_length / 1000).toFixed(0)}K ctx</span>
                    ${healthIcon ? `<span class="model-health-icon ${healthClass}">${healthIcon}</span>` : ''}
                </div>
            </div>
        `;
    }).join('');
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

// =============================================================================
// Mode Toggle (Testing vs Production)
// =============================================================================

let currentMode = 'testing';

async function loadCurrentMode() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/config/mode`);
        const data = await response.json();
        currentMode = data.mode || 'testing';
        updateModeUI();
    } catch (e) {
        console.error('Failed to load mode:', e);
    }
}

function updateModeUI() {
    // Update buttons
    document.querySelectorAll('.mode-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.mode === currentMode);
    });

    // Update status display
    const modeDisplay = document.getElementById('current-mode-display');
    if (modeDisplay) {
        modeDisplay.textContent = currentMode === 'testing' ? 'Testing' : 'Production';
        modeDisplay.classList.toggle('production', currentMode === 'production');
    }
}

async function switchMode(mode) {
    if (mode === currentMode) return;

    const container = document.querySelector('.activities-list');
    if (container) {
        container.classList.add('mode-switching');
    }

    try {
        const response = await fetch(`${API_BASE}/api/v1/config/mode`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ mode })
        });

        if (!response.ok) {
            throw new Error('Failed to switch mode');
        }

        const data = await response.json();
        currentMode = data.mode;
        updateModeUI();

        // Reload activities to show new models
        await loadActivities();

        console.log(`Switched to ${mode} mode, updated ${data.updated_count} activities`);
    } catch (e) {
        console.error('Failed to switch mode:', e);
        alert(`Failed to switch mode: ${e.message}`);
    } finally {
        if (container) {
            container.classList.remove('mode-switching');
        }
    }
}

function initModeToggle() {
    document.getElementById('mode-testing')?.addEventListener('click', () => switchMode('testing'));
    document.getElementById('mode-production')?.addEventListener('click', () => switchMode('production'));
}

// =============================================================================
// Model Health Check
// =============================================================================

let modelHealthCache = {};

async function checkModelHealth() {
    const btn = document.getElementById('check-model-health');
    const statusDiv = document.getElementById('model-health-status');
    const contentDiv = document.getElementById('health-content');

    btn.disabled = true;
    btn.textContent = '🩺 Checking...';
    statusDiv.style.display = 'block';
    contentDiv.innerHTML = '<div class="health-checking">Checking free models health...</div>';

    try {
        const response = await fetch(`${API_BASE}/api/v1/config/models/health-check-free`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({})
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();

        // Update cache
        data.results.forEach(r => {
            modelHealthCache[r.model_id] = r;
        });

        // Render results
        let html = `
            <div class="health-summary">
                <span class="health-working">✅ ${data.working} working</span>
                <span class="health-failed">❌ ${data.failed} failed</span>
                of ${data.checked} checked
            </div>
            <div class="health-results">
        `;

        data.results.forEach(r => {
            const icon = r.working ? '✅' : '❌';
            const latency = r.latency_ms ? `${r.latency_ms.toFixed(0)}ms` : '';
            const error = r.error ? `<span class="health-error">${r.error}</span>` : '';
            html += `
                <div class="health-result ${r.working ? 'working' : 'failed'}">
                    ${icon} ${r.model_id.split('/').pop()}
                    ${latency ? `<span class="health-latency">${latency}</span>` : ''}
                    ${error}
                </div>
            `;
        });

        html += '</div>';
        contentDiv.innerHTML = html;

        // Refresh activities to update model status badges
        await loadActivities();

    } catch (e) {
        contentDiv.innerHTML = `<div class="health-error">Health check failed: ${e.message}</div>`;
    } finally {
        btn.disabled = false;
        btn.textContent = '🩺 Health Check';
    }
}

// =============================================================================
// AI-Powered Auto-Selection
// =============================================================================

async function autoSelectModels() {
    const btn = document.getElementById('auto-select-models');

    if (!confirm('Use AI to automatically select the best model for each activity?\n\nThis will analyze each activity\'s requirements and pick optimal models from available free models.')) {
        return;
    }

    btn.disabled = true;
    btn.textContent = '🤖 Selecting...';

    const container = document.querySelector('.activities-list');
    if (container) {
        container.classList.add('mode-switching');
    }

    try {
        const response = await fetch(`${API_BASE}/api/v1/config/activities/auto-select/apply`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                free_only: true,
                prefer_speed: false,
                prefer_quality: false
            })
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const data = await response.json();

        if (data.success) {
            // Show success notification
            const count = Object.keys(data.recommendations).length;
            alert(`✅ Auto-selection complete!\n\n${count} activities updated with optimal models.`);

            // Reload activities to show new models
            await loadActivities();
        } else {
            throw new Error(data.error || 'Auto-selection failed');
        }

    } catch (e) {
        alert(`❌ Auto-selection failed: ${e.message}`);
    } finally {
        btn.disabled = false;
        btn.textContent = '🤖 Auto-Select';
        if (container) {
            container.classList.remove('mode-switching');
        }
    }
}


function initModelSelection() {
    // Initialize mode toggle
    initModeToggle();

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

    // Health Check button
    document.getElementById('check-model-health')?.addEventListener('click', checkModelHealth);
    document.getElementById('close-health-status')?.addEventListener('click', () => {
        document.getElementById('model-health-status').style.display = 'none';
    });

    // Auto-Select button
    document.getElementById('auto-select-models')?.addEventListener('click', autoSelectModels);

    // Load when models config section is shown
    document.querySelectorAll('.config-nav li').forEach(item => {
        item.addEventListener('click', () => {
            if (item.dataset.config === 'models') {
                loadCurrentMode();
                loadModels().then(() => loadActivities());
            }
        });
    });
}


// Add to initialization
document.addEventListener('DOMContentLoaded', () => {
    initProviderConfig();
    initModelSelection();
    initHomeAssistant();
});

// =============================================================================
// Home Assistant
// =============================================================================

let haEntities = [];
let haDomains = [];
let haAreas = [];
let haDevices = [];

function initHomeAssistant() {
    // Entity search
    document.getElementById('entity-search')?.addEventListener('input', debounce(filterEntities, 300));

    // Domain filter
    document.getElementById('entity-type-filter')?.addEventListener('change', filterEntities);

    // Area filter
    document.getElementById('entity-area-filter')?.addEventListener('change', filterEntities);

    // Refresh button
    document.getElementById('refresh-entities')?.addEventListener('click', refreshHAData);

    // HA Tab navigation
    document.querySelectorAll('.ha-tab-btn').forEach(btn => {
        btn.addEventListener('click', () => {
            const tab = btn.dataset.haTab;
            switchHATab(tab);
        });
    });

    // Load when page is shown
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => {
            if (link.dataset.page === 'entities') {
                loadHAStatus();
                loadHAOverviewTab();  // Load overview tab by default
            }
        });
    });

    // Config page HA section
    document.querySelectorAll('.config-nav li').forEach(item => {
        item.addEventListener('click', () => {
            if (item.dataset.config === 'homeassistant') {
                loadHAStatus();
                loadHAConfigStatus();
            }
        });
    });

    // Test connection button
    document.getElementById('test-ha-connection')?.addEventListener('click', testHAConnection);

    // Save HA config button
    document.getElementById('save-ha-config')?.addEventListener('click', saveHAConfig);
}

function switchHATab(tab) {
    // Update tab buttons
    document.querySelectorAll('.ha-tab-btn').forEach(btn => {
        btn.classList.toggle('active', btn.dataset.haTab === tab);
    });

    // Show tab content
    document.querySelectorAll('.ha-tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `ha-tab-${tab}`);
    });

    // Load content for tab
    switch (tab) {
        case 'overview':
            loadHAOverviewTab();
            break;
        case 'entities':
            loadHAEntities();
            break;
        case 'areas':
            loadHAAreasTab();
            break;
        case 'devices':
            loadHADevicesTab();
            break;
        case 'activity':
            loadHAActivityTab();
            break;
    }
}

function debounce(func, wait) {
    let timeout;
    return function (...args) {
        clearTimeout(timeout);
        timeout = setTimeout(() => func.apply(this, args), wait);
    };
}

async function loadHAStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/status`);
        const data = await response.json();

        updateHAStatusDisplay(data);

        // If connected, load overview
        if (data.connected) {
            await loadHAOverview();
        }
    } catch (e) {
        console.error('Failed to load HA status:', e);
        updateHAStatusDisplay({ connected: false, error: 'Failed to connect to BarnabeeNet API' });
    }
}

function updateHAStatusDisplay(data) {
    const statusContainer = document.getElementById('ha-connection-status');
    if (!statusContainer) return;

    if (data.connected) {
        statusContainer.innerHTML = `
            <div class="ha-status-connected">
                <span class="status-indicator connected"></span>
                <span class="status-text">Connected to Home Assistant</span>
            </div>
            <div class="ha-details">
                ${data.version ? `<span class="ha-detail">Version: ${data.version}</span>` : ''}
                ${data.location_name ? `<span class="ha-detail">Name: ${data.location_name}</span>` : ''}
            </div>
        `;
    } else {
        statusContainer.innerHTML = `
            <div class="ha-status-disconnected">
                <span class="status-indicator disconnected"></span>
                <span class="status-text">Not Connected</span>
            </div>
            ${data.error ? `<div class="ha-error">${escapeHtml(data.error)}</div>` : ''}
        `;
    }
}

async function loadHAOverview() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/overview`);
        const data = await response.json();

        // Update domain counts
        const domainCountsContainer = document.getElementById('ha-domain-counts');
        if (domainCountsContainer && data.domain_counts) {
            const sortedDomains = Object.entries(data.domain_counts)
                .sort((a, b) => b[1] - a[1])
                .slice(0, 10);

            domainCountsContainer.innerHTML = sortedDomains.map(([domain, count]) => `
                <div class="domain-count-item">
                    <span class="domain-icon">${getDomainIcon(domain)}</span>
                    <span class="domain-name">${domain}</span>
                    <span class="domain-count">${count}</span>
                </div>
            `).join('');
        }

        // Update snapshot summary
        const snapshotContainer = document.getElementById('ha-snapshot-summary');
        if (snapshotContainer && data.snapshot) {
            snapshotContainer.innerHTML = `
                <div class="snapshot-grid">
                    <div class="snapshot-item">
                        <span class="snapshot-value">${data.snapshot.entities_count || 0}</span>
                        <span class="snapshot-label">Entities</span>
                    </div>
                    <div class="snapshot-item">
                        <span class="snapshot-value">${data.snapshot.devices_count || 0}</span>
                        <span class="snapshot-label">Devices</span>
                    </div>
                    <div class="snapshot-item">
                        <span class="snapshot-value">${data.snapshot.areas_count || 0}</span>
                        <span class="snapshot-label">Areas</span>
                    </div>
                    <div class="snapshot-item">
                        <span class="snapshot-value">${data.snapshot.automations_count || 0}</span>
                        <span class="snapshot-label">Automations</span>
                    </div>
                </div>
            `;
        }
    } catch (e) {
        console.error('Failed to load HA overview:', e);
    }
}

async function loadHAEntities() {
    const container = document.getElementById('entities-list');
    if (!container) return;

    container.innerHTML = '<div class="loading-spinner">Loading entities...</div>';

    try {
        // Load entities
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/entities?limit=500`);
        const data = await response.json();

        haEntities = data.entities || [];
        haDomains = data.domains || [];

        // Update domain filter options
        updateDomainFilter(haDomains);

        // Load areas for filter
        await loadHAAreas();

        // Render entities
        renderEntities(haEntities);
    } catch (e) {
        console.error('Failed to load entities:', e);
        container.innerHTML = `
            <div class="empty-state">
                <p class="text-muted">⚠️ Failed to load entities</p>
                <p class="text-muted">${e.message}</p>
                <button class="btn" onclick="loadHAEntities()">🔄 Retry</button>
            </div>
        `;
    }
}

async function loadHAAreas() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/areas`);
        const data = await response.json();
        haAreas = data.areas || [];

        // Update area filter
        const areaFilter = document.getElementById('entity-area-filter');
        if (areaFilter) {
            areaFilter.innerHTML = '<option value="">All Areas</option>' +
                haAreas.map(a => `<option value="${a.id}">${escapeHtml(a.name)}</option>`).join('');
        }
    } catch (e) {
        console.error('Failed to load areas:', e);
    }
}

// Load Overview Tab - shows what Barnabee knows about HA
async function loadHAOverviewTab() {
    try {
        const [statusRes, overviewRes] = await Promise.all([
            fetch(`${API_BASE}/api/v1/homeassistant/status`),
            fetch(`${API_BASE}/api/v1/homeassistant/overview`)
        ]);

        const status = await statusRes.json();
        const overview = await overviewRes.json();

        // Update discovery stats
        document.getElementById('ha-last-sync').textContent = status.connected
            ? new Date().toLocaleTimeString()
            : 'Not connected';

        // Get counts from snapshot
        const snapshot = overview.snapshot || {};
        document.getElementById('ha-entity-count').textContent = snapshot.entities_count || 0;
        document.getElementById('ha-area-count').textContent = snapshot.areas_count || 0;
        document.getElementById('ha-device-count').textContent = snapshot.devices_count || 0;

        // Update domain counts
        const domainCountsEl = document.getElementById('ha-domain-counts');
        const domainCounts = overview.domain_counts || {};
        if (Object.keys(domainCounts).length > 0) {
            domainCountsEl.innerHTML = Object.entries(domainCounts)
                .sort((a, b) => b[1] - a[1])
                .map(([domain, count]) => `
                    <div class="domain-count-item">
                        <span class="domain-icon">${getDomainIcon(domain)}</span>
                        <span class="domain-name">${getDomainName(domain)}</span>
                        <span class="domain-count">${count}</span>
                    </div>
                `).join('');
        } else {
            domainCountsEl.innerHTML = '<p class="text-muted">Connect to Home Assistant to see domain statistics</p>';
        }

        // Load recent HA activity from the main activity feed (filter for HA actions)
        loadRecentHAActivity();

    } catch (e) {
        console.error('Failed to load HA overview:', e);
    }
}

// Load recent HA activity from state change events
async function loadRecentHAActivity() {
    const container = document.getElementById('ha-recent-activity');
    if (!container) return;

    try {
        // Get state change events from HA WebSocket subscription
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/events?limit=10`);
        const data = await response.json();

        // Filter for "interesting" domains - skip sensors updating every second
        const interestingDomains = ['light', 'switch', 'climate', 'lock', 'cover', 'media_player', 'fan', 'automation', 'scene'];
        const events = (data.events || []).filter(e => interestingDomains.includes(e.domain));

        if (events.length === 0) {
            const subscriptionStatus = data.is_subscribed
                ? 'Listening for state changes...'
                : 'Not subscribed to events';
            container.innerHTML = `<p class="text-muted">No recent Home Assistant activity. ${subscriptionStatus}</p>`;
            return;
        }

        container.innerHTML = events.map(event => `
            <div class="ha-activity-item">
                <span class="activity-time">${formatActivityTime(event.timestamp)}</span>
                <span class="activity-icon">${getDomainIcon(event.domain)}</span>
                <span class="activity-entity">${escapeHtml(event.friendly_name)}</span>
                <span class="activity-change">${escapeHtml(event.old_state || '?')} → ${escapeHtml(event.new_state || '?')}</span>
            </div>
        `).join('');

    } catch (e) {
        console.error('Failed to load HA activity:', e);
        container.innerHTML = '<p class="text-muted">Failed to load activity</p>';
    }
}

// Load Activity Tab - real-time state change log
async function loadHAActivityTab() {
    const container = document.getElementById('ha-activity-log');
    if (!container) return;

    container.innerHTML = '<div class="loading-spinner">Loading activity...</div>';

    try {
        // Get state change events from HA WebSocket subscription
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/events?limit=100`);
        const data = await response.json();

        const events = data.events || [];

        if (events.length === 0) {
            const subscriptionStatus = data.is_subscribed
                ? '<span class="subscription-active">🟢 Subscribed to Home Assistant events</span>'
                : '<span class="subscription-inactive">🔴 Not subscribed to events</span>';
            container.innerHTML = `
                <div class="empty-state">
                    ${subscriptionStatus}
                    <p class="text-muted">No state changes received yet.</p>
                    <p class="text-muted">Toggle a light or change something in Home Assistant to see events here.</p>
                </div>
            `;
            return;
        }

        // Group events by time (last 5 minutes, last 30 minutes, older)
        const now = Date.now();
        const fiveMinutes = 5 * 60 * 1000;
        const thirtyMinutes = 30 * 60 * 1000;

        const recentEvents = events.filter(e => now - new Date(e.timestamp).getTime() < fiveMinutes);
        const olderEvents = events.filter(e => {
            const age = now - new Date(e.timestamp).getTime();
            return age >= fiveMinutes && age < thirtyMinutes;
        });
        const oldestEvents = events.filter(e => now - new Date(e.timestamp).getTime() >= thirtyMinutes);

        let html = '';
        const subscriptionIndicator = data.is_subscribed
            ? '<span class="subscription-active">🟢 Live</span>'
            : '<span class="subscription-inactive">🔴 Not subscribed</span>';

        html += `<div class="activity-section-header">${subscriptionIndicator} <span class="event-count">${events.length} events</span></div>`;

        if (recentEvents.length > 0) {
            html += '<div class="activity-section"><h4>Last 5 minutes</h4>';
            html += recentEvents.map(e => renderStateChangeEvent(e)).join('');
            html += '</div>';
        }

        if (olderEvents.length > 0) {
            html += '<div class="activity-section"><h4>Last 30 minutes</h4>';
            html += olderEvents.map(e => renderStateChangeEvent(e)).join('');
            html += '</div>';
        }

        if (oldestEvents.length > 0) {
            html += '<div class="activity-section"><h4>Earlier</h4>';
            html += oldestEvents.map(e => renderStateChangeEvent(e)).join('');
            html += '</div>';
        }

        container.innerHTML = html;

    } catch (e) {
        console.error('Failed to load HA activity log:', e);
        container.innerHTML = '<div class="empty-state"><p class="text-muted">Failed to load activity</p></div>';
    }
}

function renderStateChangeEvent(event) {
    const stateClass = getStateClass(event.new_state);
    return `
        <div class="ha-event-item ${stateClass}">
            <div class="event-header">
                <span class="event-icon">${getDomainIcon(event.domain)}</span>
                <span class="event-entity">${escapeHtml(event.friendly_name)}</span>
                <span class="event-time">${formatActivityTime(event.timestamp)}</span>
            </div>
            <div class="event-change">
                <span class="old-state">${escapeHtml(event.old_state || 'unknown')}</span>
                <span class="arrow">→</span>
                <span class="new-state ${stateClass}">${escapeHtml(event.new_state || 'unknown')}</span>
            </div>
        </div>
    `;
}

function getStateClass(state) {
    if (!state) return '';
    if (state === 'on') return 'state-on';
    if (state === 'off') return 'state-off';
    if (state === 'unavailable') return 'state-unavailable';
    if (state === 'unknown') return 'state-unknown';
    return '';
}

function formatActivityTime(timestamp) {
    if (!timestamp) return '';
    const date = new Date(timestamp);
    return date.toLocaleTimeString();
}

// Sync HA data button handler
document.getElementById('ha-sync-now')?.addEventListener('click', async () => {
    const btn = document.getElementById('ha-sync-now');
    btn.disabled = true;
    btn.textContent = '⏳ Syncing...';

    try {
        await fetch(`${API_BASE}/api/v1/homeassistant/refresh`, { method: 'POST' });
        await loadHAOverviewTab();
        showToast('✅ Home Assistant data synced');
    } catch (e) {
        showToast('❌ Sync failed', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '🔄 Sync Now';
    }
});

async function loadHAAreasTab() {
    const container = document.getElementById('ha-areas-list');
    if (!container) return;

    container.innerHTML = '<div class="loading-spinner">Loading areas...</div>';

    try {
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/areas`);
        const data = await response.json();

        if (data.areas.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p class="text-muted">🏠 No areas defined in Home Assistant</p>
                    <p class="text-muted">Create areas in Home Assistant Settings → Areas & Zones</p>
                </div>
            `;
            return;
        }

        container.innerHTML = `
            <div class="areas-description">
                <p class="text-muted">These are the areas Barnabee knows about. Say "turn off the lights in [area name]" to control them.</p>
            </div>
        ` + data.areas.map(area => `
            <div class="area-card" data-area-id="${area.area_id}">
                <div class="area-icon">${area.icon || '🏠'}</div>
                <div class="area-info">
                    <div class="area-name">${escapeHtml(area.name)}</div>
                    <div class="area-stats">
                        <span>📱 ${area.device_count} devices</span>
                        <span>💡 ${area.entity_count} entities</span>
                    </div>
                </div>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = `<div class="empty-state"><p class="text-muted">Failed to load areas: ${e.message}</p></div>`;
    }
}

async function loadHADevicesTab() {
    const container = document.getElementById('ha-devices-list');
    if (!container) return;

    container.innerHTML = '<div class="loading-spinner">Loading devices...</div>';

    try {
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/devices`);
        const data = await response.json();

        if (data.devices.length === 0) {
            container.innerHTML = `
                <div class="empty-state">
                    <p class="text-muted">📱 No devices found</p>
                    <p class="text-muted">Devices will appear when integrations are configured in Home Assistant</p>
                </div>
            `;
            return;
        }

        container.innerHTML = data.devices.map(device => `
            <div class="device-card ${device.is_enabled ? '' : 'disabled'}">
                <div class="device-info">
                    <div class="device-name">${escapeHtml(device.name)}</div>
                    <div class="device-model">
                        ${device.manufacturer ? escapeHtml(device.manufacturer) : ''}
                        ${device.model ? ' ' + escapeHtml(device.model) : ''}
                    </div>
                </div>
                <div class="device-meta">
                    ${device.area_name ? `<span class="device-area">${escapeHtml(device.area_name)}</span>` : ''}
                </div>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = `<div class="empty-state"><p class="text-muted">Failed to load devices: ${e.message}</p></div>`;
    }
}

async function loadHAAutomationsTab() {
    const container = document.getElementById('ha-automations-list');
    if (!container) return;

    container.innerHTML = '<div class="loading-spinner">Loading automations...</div>';

    try {
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/automations`);
        const data = await response.json();

        if (data.automations.length === 0) {
            container.innerHTML = '<div class="empty-state"><p class="text-muted">No automations found</p></div>';
            return;
        }

        container.innerHTML = data.automations.map(auto => `
            <div class="automation-card ${auto.state === 'on' ? 'enabled' : 'disabled'}">
                <div class="automation-header">
                    <span class="automation-status ${auto.state}">${auto.state === 'on' ? '🟢' : '⚫'}</span>
                    <div class="automation-name">${escapeHtml(auto.name)}</div>
                </div>
                ${auto.description ? `<div class="automation-desc">${escapeHtml(auto.description)}</div>` : ''}
                <div class="automation-meta">
                    <span class="automation-mode">Mode: ${auto.mode}</span>
                    ${auto.last_triggered ? `<span class="automation-triggered">Last: ${formatDate(auto.last_triggered)}</span>` : ''}
                </div>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = `<div class="empty-state"><p class="text-muted">Failed to load automations: ${e.message}</p></div>`;
    }
}

async function loadHALogsTab() {
    const container = document.getElementById('ha-logs-list');
    if (!container) return;

    container.innerHTML = '<div class="loading-spinner">Loading logs...</div>';

    try {
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/logs?limit=100`);
        const data = await response.json();

        if (data.entries.length === 0) {
            container.innerHTML = '<div class="empty-state"><p class="text-muted">No log entries</p></div>';
            return;
        }

        container.innerHTML = data.entries.map(entry => `
            <div class="log-entry log-${entry.level.toLowerCase()}">
                <span class="log-time">${formatLogTime(entry.timestamp)}</span>
                <span class="log-level">${entry.level}</span>
                <span class="log-source">${escapeHtml(entry.source)}</span>
                <span class="log-message">${escapeHtml(entry.message)}</span>
            </div>
        `).join('');
    } catch (e) {
        container.innerHTML = `<div class="empty-state"><p class="text-muted">Failed to load logs: ${e.message}</p></div>`;
    }
}

function formatDate(isoString) {
    if (!isoString) return 'Never';
    const date = new Date(isoString);
    return date.toLocaleString();
}

function formatLogTime(isoString) {
    if (!isoString) return '';
    const date = new Date(isoString);
    return date.toLocaleTimeString();
}

function updateDomainFilter(domains) {
    const filter = document.getElementById('entity-type-filter');
    if (!filter) return;

    const domainOptions = domains.map(d => `<option value="${d}">${getDomainDisplayName(d)}</option>`).join('');
    filter.innerHTML = '<option value="">All Types</option>' + domainOptions;
}

function filterEntities() {
    const search = document.getElementById('entity-search')?.value?.toLowerCase() || '';
    const domain = document.getElementById('entity-type-filter')?.value || '';
    const area = document.getElementById('entity-area-filter')?.value || '';

    let filtered = haEntities;

    if (search) {
        filtered = filtered.filter(e =>
            e.friendly_name.toLowerCase().includes(search) ||
            e.entity_id.toLowerCase().includes(search)
        );
    }

    if (domain) {
        filtered = filtered.filter(e => e.domain === domain);
    }

    if (area) {
        filtered = filtered.filter(e => e.area_id === area);
    }

    renderEntities(filtered);
}

function renderEntities(entities) {
    const container = document.getElementById('entities-list');
    if (!container) return;

    if (entities.length === 0) {
        container.innerHTML = `
            <div class="empty-state">
                <p class="text-muted">No entities found</p>
                <p class="text-muted">Connect to Home Assistant in Configuration → Home Assistant</p>
            </div>
        `;
        return;
    }

    // Group by domain for better organization
    const grouped = {};
    entities.forEach(e => {
        if (!grouped[e.domain]) grouped[e.domain] = [];
        grouped[e.domain].push(e);
    });

    // Render as grid
    container.innerHTML = entities.map(e => renderEntityCard(e)).join('');
}

function renderEntityCard(entity) {
    const stateClass = getStateClass(entity);
    const icon = getDomainIcon(entity.domain);
    const attrs = entity.attributes || {};

    // Build info section based on domain (read-only display)
    let extraInfo = '';

    if (entity.domain === 'light' && entity.is_on && attrs.brightness) {
        const percent = Math.round((attrs.brightness / 255) * 100);
        extraInfo = `<div class="entity-extra">Brightness: ${percent}%</div>`;
    }

    if (entity.domain === 'climate') {
        const currentTemp = attrs.current_temperature || '--';
        const targetTemp = attrs.temperature || '--';
        extraInfo = `<div class="entity-extra">Current: ${currentTemp}° | Target: ${targetTemp}°</div>`;
    }

    if (entity.domain === 'sensor') {
        const unit = attrs.unit_of_measurement || '';
        extraInfo = `<div class="entity-extra">${entity.state}${unit}</div>`;
    }

    if (entity.domain === 'media_player' && attrs.media_title) {
        extraInfo = `<div class="entity-extra">${escapeHtml(attrs.media_title)}</div>`;
    }

    return `
        <div class="entity-card ${stateClass}" data-entity-id="${entity.entity_id}">
            <div class="entity-header">
                <span class="entity-icon">${icon}</span>
                <div class="entity-info">
                    <div class="entity-name">${escapeHtml(entity.friendly_name)}</div>
                    <div class="entity-id">${entity.entity_id}</div>
                </div>
            </div>
            <div class="entity-state">
                <span class="state-badge ${stateClass}">${formatState(entity)}</span>
                ${entity.area_name ? `<span class="entity-area">${escapeHtml(entity.area_name)}</span>` : ''}
            </div>
            ${extraInfo}
        </div>
    `;
}

function getStateClass(entity) {
    const state = entity.state?.toLowerCase() || '';
    if (state === 'on' || state === 'open' || state === 'unlocked' || state === 'playing') {
        return 'state-on';
    }
    if (state === 'off' || state === 'closed' || state === 'locked' || state === 'paused' || state === 'idle') {
        return 'state-off';
    }
    if (state === 'unavailable' || state === 'unknown') {
        return 'state-unavailable';
    }
    return 'state-other';
}

function formatState(entity) {
    const state = entity.state || 'unknown';
    const attrs = entity.attributes || {};

    // Add extra info for certain domains
    if (entity.domain === 'light' && state === 'on' && attrs.brightness) {
        const percent = Math.round((attrs.brightness / 255) * 100);
        return `${state} (${percent}%)`;
    }
    if (entity.domain === 'climate' && attrs.temperature) {
        return `${attrs.temperature}°`;
    }
    if (entity.domain === 'sensor') {
        const unit = attrs.unit_of_measurement || '';
        return `${state}${unit}`;
    }
    if (entity.domain === 'binary_sensor') {
        return state === 'on' ? (attrs.device_class || 'on') : 'off';
    }

    return state;
}

function getDomainIcon(domain) {
    const icons = {
        'light': '💡',
        'switch': '🔌',
        'fan': '🌀',
        'climate': '🌡️',
        'sensor': '📊',
        'binary_sensor': '⭕',
        'cover': '🪟',
        'lock': '🔒',
        'media_player': '📺',
        'camera': '📷',
        'vacuum': '🤖',
        'automation': '⚙️',
        'script': '📜',
        'scene': '🎬',
        'input_boolean': '☑️',
        'input_number': '🔢',
        'input_select': '📝',
        'input_text': '📝',
        'person': '👤',
        'device_tracker': '📍',
        'weather': '⛅',
        'sun': '☀️',
        'zone': '🗺️',
        'update': '🔄',
        'button': '🔘',
        'number': '🔢',
        'select': '📋',
        'text': '📝',
        'datetime': '📅',
        'timer': '⏱️',
        'counter': '🔢',
        'alarm_control_panel': '🚨',
        'water_heater': '🚿',
        'humidifier': '💧',
        'remote': '📱',
        'siren': '🔔',
    };
    return icons[domain] || '❓';
}

function getDomainDisplayName(domain) {
    const names = {
        'light': 'Lights',
        'switch': 'Switches',
        'fan': 'Fans',
        'climate': 'Climate',
        'sensor': 'Sensors',
        'binary_sensor': 'Binary Sensors',
        'cover': 'Covers',
        'lock': 'Locks',
        'media_player': 'Media Players',
        'camera': 'Cameras',
        'vacuum': 'Vacuums',
        'automation': 'Automations',
        'script': 'Scripts',
        'scene': 'Scenes',
        'input_boolean': 'Input Booleans',
        'person': 'People',
        'device_tracker': 'Device Trackers',
        'weather': 'Weather',
        'update': 'Updates',
        'button': 'Buttons',
    };
    return names[domain] || domain.charAt(0).toUpperCase() + domain.slice(1).replace(/_/g, ' ');
}

async function toggleEntity(entityId) {
    try {
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/entities/${entityId}/toggle`, {
            method: 'POST'
        });

        const data = await response.json();

        if (data.success) {
            // Refresh entity list after toggle
            setTimeout(loadHAEntities, 500);
        } else {
            alert(`Failed to toggle: ${data.message}`);
        }
    } catch (e) {
        console.error('Toggle failed:', e);
        alert(`Toggle failed: ${e.message}`);
    }
}

// Generic service call function
async function callService(service, entityId, data = {}) {
    try {
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/services/call`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                service: service,
                entity_id: entityId,
                data: data
            })
        });

        const result = await response.json();

        if (result.success) {
            // Refresh after service call
            setTimeout(loadHAEntities, 500);
        } else {
            console.error(`Service call failed: ${result.message}`);
        }
        return result;
    } catch (e) {
        console.error('Service call failed:', e);
        return { success: false, message: e.message };
    }
}

// Brightness control for lights
async function setBrightness(entityId, percent) {
    const brightness = Math.round((parseInt(percent) / 100) * 255);
    await callService('light.turn_on', entityId, { brightness: brightness });

    // Update display immediately
    const slider = document.querySelector(`[data-entity="${entityId}"].brightness-slider`);
    if (slider) {
        const valueSpan = slider.parentElement.querySelector('.brightness-value');
        if (valueSpan) valueSpan.textContent = `${percent}%`;
    }
}

// Color temperature control
async function setColorTemp(entityId, kelvin) {
    await callService('light.turn_on', entityId, { color_temp_kelvin: parseInt(kelvin) });

    // Update display
    const slider = document.querySelector(`[data-entity="${entityId}"].color-temp-slider`);
    if (slider) {
        const valueSpan = slider.parentElement.querySelector('.color-temp-value');
        if (valueSpan) valueSpan.textContent = `${kelvin}K`;
    }
}

// Climate temperature adjustment
async function adjustClimate(entityId, delta) {
    try {
        // First get current temperature
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/entities/${entityId}`);
        const entity = await response.json();

        const currentTarget = entity.attributes?.temperature || 20;
        const newTarget = currentTarget + delta;

        await callService('climate.set_temperature', entityId, { temperature: newTarget });
    } catch (e) {
        console.error('Climate adjustment failed:', e);
    }
}

// Set HVAC mode
async function setHvacMode(entityId, mode) {
    await callService('climate.set_hvac_mode', entityId, { hvac_mode: mode });
}

// Cover position control
async function setCoverPosition(entityId, position) {
    await callService('cover.set_cover_position', entityId, { position: parseInt(position) });
}

// Volume control for media players
async function setVolume(entityId, percent) {
    const volume = parseInt(percent) / 100;
    await callService('media_player.volume_set', entityId, { volume_level: volume });
}

// Show entity context menu
function showEntityMenu(entityId, event) {
    event.stopPropagation();

    // Remove any existing menu
    document.querySelectorAll('.entity-context-menu').forEach(m => m.remove());

    const menu = document.createElement('div');
    menu.className = 'entity-context-menu';
    menu.innerHTML = `
        <button onclick="showEntityDetails('${entityId}')">📋 Details</button>
        <button onclick="showServiceCallDialog('${entityId}')">⚙️ Call Service</button>
        <button onclick="copyEntityId('${entityId}')">📋 Copy ID</button>
    `;

    // Position near the button
    const rect = event.target.getBoundingClientRect();
    menu.style.position = 'fixed';
    menu.style.top = `${rect.bottom + 5}px`;
    menu.style.right = `${window.innerWidth - rect.right}px`;

    document.body.appendChild(menu);

    // Close on click outside
    setTimeout(() => {
        document.addEventListener('click', function closeMenu() {
            menu.remove();
            document.removeEventListener('click', closeMenu);
        }, { once: true });
    }, 10);
}

// Copy entity ID to clipboard
function copyEntityId(entityId) {
    navigator.clipboard.writeText(entityId).then(() => {
        // Brief toast notification
        const toast = document.createElement('div');
        toast.className = 'toast';
        toast.textContent = `Copied: ${entityId}`;
        document.body.appendChild(toast);
        setTimeout(() => toast.remove(), 2000);
    });
}

// Show entity details in a modal
async function showEntityDetails(entityId) {
    try {
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/entities/${entityId}`);
        const entity = await response.json();

        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.style.display = 'flex';
        modal.innerHTML = `
            <div class="modal-content">
                <div class="modal-header">
                    <h3>${getDomainIcon(entity.domain)} ${entity.friendly_name}</h3>
                    <button class="btn btn-small close-modal">✕</button>
                </div>
                <div class="modal-body">
                    <div class="entity-detail-grid">
                        <div class="detail-row">
                            <span class="detail-label">Entity ID:</span>
                            <span class="detail-value">${entity.entity_id}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">State:</span>
                            <span class="detail-value state-badge ${getStateClass(entity)}">${entity.state}</span>
                        </div>
                        <div class="detail-row">
                            <span class="detail-label">Domain:</span>
                            <span class="detail-value">${entity.domain}</span>
                        </div>
                        ${entity.area_name ? `
                            <div class="detail-row">
                                <span class="detail-label">Area:</span>
                                <span class="detail-value">${entity.area_name}</span>
                            </div>
                        ` : ''}
                        ${entity.device_name ? `
                            <div class="detail-row">
                                <span class="detail-label">Device:</span>
                                <span class="detail-value">${entity.device_name}</span>
                            </div>
                        ` : ''}
                    </div>
                    <h4>Attributes</h4>
                    <pre class="attributes-json">${JSON.stringify(entity.attributes || {}, null, 2)}</pre>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        modal.querySelector('.close-modal').addEventListener('click', () => modal.remove());
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });
    } catch (e) {
        console.error('Failed to load entity details:', e);
        alert(`Failed to load details: ${e.message}`);
    }
}

// Show service call dialog
function showServiceCallDialog(entityId) {
    const modal = document.createElement('div');
    modal.className = 'modal';
    modal.style.display = 'flex';
    modal.innerHTML = `
        <div class="modal-content">
            <div class="modal-header">
                <h3>⚙️ Call Service</h3>
                <button class="btn btn-small close-modal">✕</button>
            </div>
            <div class="modal-body">
                <div class="form-group">
                    <label>Entity ID:</label>
                    <input type="text" class="form-control" id="service-entity-id" value="${entityId}" readonly>
                </div>
                <div class="form-group">
                    <label>Service:</label>
                    <input type="text" class="form-control" id="service-name" placeholder="e.g., light.turn_on">
                    <div class="service-suggestions">
                        <button class="btn btn-tiny" onclick="document.getElementById('service-name').value='light.turn_on'">light.turn_on</button>
                        <button class="btn btn-tiny" onclick="document.getElementById('service-name').value='light.turn_off'">light.turn_off</button>
                        <button class="btn btn-tiny" onclick="document.getElementById('service-name').value='switch.turn_on'">switch.turn_on</button>
                        <button class="btn btn-tiny" onclick="document.getElementById('service-name').value='switch.turn_off'">switch.turn_off</button>
                    </div>
                </div>
                <div class="form-group">
                    <label>Data (JSON):</label>
                    <textarea class="form-control" id="service-data" rows="4" placeholder='{"brightness": 255}'>{}</textarea>
                </div>
                <div class="form-actions">
                    <button class="btn btn-primary" onclick="executeServiceCall()">▶️ Execute</button>
                </div>
                <div id="service-call-result"></div>
            </div>
        </div>
    `;

    document.body.appendChild(modal);

    modal.querySelector('.close-modal').addEventListener('click', () => modal.remove());
    modal.addEventListener('click', (e) => {
        if (e.target === modal) modal.remove();
    });
}

// Execute service call from dialog
async function executeServiceCall() {
    const entityId = document.getElementById('service-entity-id').value;
    const service = document.getElementById('service-name').value;
    const dataStr = document.getElementById('service-data').value;
    const resultDiv = document.getElementById('service-call-result');

    if (!service) {
        resultDiv.innerHTML = '<div class="test-result error">Please enter a service name</div>';
        return;
    }

    let data = {};
    try {
        data = JSON.parse(dataStr);
    } catch (e) {
        resultDiv.innerHTML = '<div class="test-result error">Invalid JSON data</div>';
        return;
    }

    resultDiv.innerHTML = '<div class="test-result">Calling service...</div>';

    const result = await callService(service, entityId, data);

    if (result.success) {
        resultDiv.innerHTML = `<div class="test-result success">✓ ${result.message || 'Service called successfully'}</div>`;
    } else {
        resultDiv.innerHTML = `<div class="test-result error">✗ ${result.message}</div>`;
    }
}

// =============================================================================
// Area Quick Actions
// =============================================================================

// Turn all lights on in an area
async function areaLightsOn(areaId) {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '⏳';

    try {
        // Get all entities in this area
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/entities?area=${areaId}`);
        const data = await response.json();

        // Filter for lights
        const lights = data.entities.filter(e => e.domain === 'light');

        // Turn them all on
        for (const light of lights) {
            await callService('light.turn_on', light.entity_id);
        }

        // Show success toast
        showToast(`💡 Turned on ${lights.length} lights`);
    } catch (e) {
        console.error('Failed to turn on area lights:', e);
        showToast('❌ Failed to turn on lights', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '💡 On';
    }
}

// Turn all lights off in an area
async function areaLightsOff(areaId) {
    const btn = event.target;
    btn.disabled = true;
    btn.textContent = '⏳';

    try {
        // Get all entities in this area
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/entities?area=${areaId}`);
        const data = await response.json();

        // Filter for lights
        const lights = data.entities.filter(e => e.domain === 'light');

        // Turn them all off
        for (const light of lights) {
            await callService('light.turn_off', light.entity_id);
        }

        // Show success toast
        showToast(`🌙 Turned off ${lights.length} lights`);
    } catch (e) {
        console.error('Failed to turn off area lights:', e);
        showToast('❌ Failed to turn off lights', 'error');
    } finally {
        btn.disabled = false;
        btn.textContent = '🌙 Off';
    }
}

// Show entities in a specific area
async function showAreaEntities(areaId, areaName) {
    try {
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/entities?area=${areaId}`);
        const data = await response.json();

        const modal = document.createElement('div');
        modal.className = 'modal';
        modal.style.display = 'flex';

        let entitiesHtml = '';
        if (data.entities.length === 0) {
            entitiesHtml = '<p class="text-muted">No entities in this area</p>';
        } else {
            // Group by domain
            const byDomain = {};
            data.entities.forEach(e => {
                if (!byDomain[e.domain]) byDomain[e.domain] = [];
                byDomain[e.domain].push(e);
            });

            for (const [domain, entities] of Object.entries(byDomain)) {
                entitiesHtml += `
                    <div class="area-domain-group">
                        <h4>${getDomainIcon(domain)} ${getDomainName(domain)} (${entities.length})</h4>
                        <div class="area-entities-list">
                            ${entities.map(e => `
                                <div class="area-entity-item ${e.is_on ? 'state-on' : 'state-off'}">
                                    <span class="entity-name">${escapeHtml(e.friendly_name)}</span>
                                    <span class="state-badge ${getStateClass(e)}">${e.state}</span>
                                    ${['light', 'switch', 'fan'].includes(domain) ? `
                                        <button class="btn btn-tiny" onclick="toggleEntity('${e.entity_id}')">
                                            ${e.is_on ? '🔴' : '🟢'}
                                        </button>
                                    ` : ''}
                                </div>
                            `).join('')}
                        </div>
                    </div>
                `;
            }
        }

        modal.innerHTML = `
            <div class="modal-content modal-large">
                <div class="modal-header">
                    <h3>🏠 ${areaName}</h3>
                    <button class="btn btn-small close-modal">✕</button>
                </div>
                <div class="modal-body">
                    <div class="area-actions">
                        <button class="btn" onclick="areaLightsOn('${areaId}')">💡 All Lights On</button>
                        <button class="btn" onclick="areaLightsOff('${areaId}')">🌙 All Lights Off</button>
                    </div>
                    <div class="area-entities-content">
                        ${entitiesHtml}
                    </div>
                </div>
            </div>
        `;

        document.body.appendChild(modal);

        modal.querySelector('.close-modal').addEventListener('click', () => modal.remove());
        modal.addEventListener('click', (e) => {
            if (e.target === modal) modal.remove();
        });
    } catch (e) {
        console.error('Failed to load area entities:', e);
        showToast(`Failed to load area entities: ${e.message}`, 'error');
    }
}

// Toast notification helper
function showToast(message, type = 'success') {
    const toast = document.createElement('div');
    toast.className = `toast ${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);
    setTimeout(() => toast.remove(), 3000);
}

async function refreshHAData() {
    const btn = document.getElementById('refresh-entities');
    if (btn) {
        btn.disabled = true;
        btn.textContent = '🔄 Refreshing...';
    }

    try {
        // Call refresh endpoint
        await fetch(`${API_BASE}/api/v1/homeassistant/refresh`, { method: 'POST' });

        // Reload entities
        await loadHAEntities();

        // Reload overview
        await loadHAOverview();
    } catch (e) {
        console.error('Refresh failed:', e);
        alert(`Refresh failed: ${e.message}`);
    } finally {
        if (btn) {
            btn.disabled = false;
            btn.textContent = '🔄 Refresh';
        }
    }
}

async function testHAConnection() {
    const urlInput = document.getElementById('ha-url-input');
    const tokenInput = document.getElementById('ha-token-input');
    const result = document.getElementById('ha-test-result');

    const url = urlInput?.value?.trim();
    const token = tokenInput?.value?.trim();

    if (!url || !token) {
        if (result) {
            result.className = 'test-result error';
            result.textContent = '✗ Please enter both URL and token';
            result.style.display = 'block';
        }
        return;
    }

    if (result) {
        result.className = 'test-result loading';
        result.textContent = 'Testing connection...';
        result.style.display = 'block';
    }

    try {
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/config/test`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, token })
        });
        const data = await response.json();

        if (data.success) {
            if (result) {
                result.className = 'test-result success';
                result.innerHTML = `✓ Connected to ${data.location_name || 'Home Assistant'}!<br>
                    Version: ${data.version || 'Unknown'}<br>
                    Entities: ${data.entity_count || 0}<br>
                    Latency: ${data.latency_ms?.toFixed(0) || 'N/A'}ms`;
            }
        } else {
            if (result) {
                result.className = 'test-result error';
                result.textContent = `✗ ${data.message}`;
            }
        }
    } catch (e) {
        if (result) {
            result.className = 'test-result error';
            result.textContent = `✗ Error: ${e.message}`;
        }
    }
}

async function saveHAConfig() {
    const urlInput = document.getElementById('ha-url-input');
    const tokenInput = document.getElementById('ha-token-input');
    const result = document.getElementById('ha-test-result');
    const saveBtn = document.getElementById('save-ha-config');

    const url = urlInput?.value?.trim();
    const token = tokenInput?.value?.trim();

    if (!url || !token) {
        if (result) {
            result.className = 'test-result error';
            result.textContent = '✗ Please enter both URL and token';
            result.style.display = 'block';
        }
        return;
    }

    if (saveBtn) {
        saveBtn.disabled = true;
        saveBtn.textContent = '💾 Saving...';
    }

    if (result) {
        result.className = 'test-result loading';
        result.textContent = 'Saving configuration...';
        result.style.display = 'block';
    }

    try {
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/config`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ url, token })
        });
        const data = await response.json();

        if (data.success) {
            if (result) {
                result.className = 'test-result success';
                result.innerHTML = `✓ ${data.message}`;
                if (data.connected && data.version) {
                    result.innerHTML += `<br>Version: ${data.version}`;
                }
            }
            // Clear token field for security
            if (tokenInput) tokenInput.value = '';

            // Reload status displays
            await loadHAStatus();
            await loadHAConfigStatus();
        } else {
            if (result) {
                result.className = 'test-result error';
                result.textContent = `✗ ${data.message}`;
            }
        }
    } catch (e) {
        if (result) {
            result.className = 'test-result error';
            result.textContent = `✗ Error: ${e.message}`;
        }
    } finally {
        if (saveBtn) {
            saveBtn.disabled = false;
            saveBtn.textContent = '💾 Save';
        }
    }
}

async function loadHAConfigStatus() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/config`);
        const data = await response.json();

        const urlInput = document.getElementById('ha-url-input');
        if (urlInput && data.url) {
            urlInput.value = data.url;
        }

        // Update config status display
        const configStatus = document.getElementById('ha-config-connection-status');
        if (configStatus) {
            if (data.has_token && data.url) {
                configStatus.innerHTML = `
                    <div class="ha-status-configured">
                        <span class="status-indicator connected"></span>
                        <span class="status-text">Configured (${data.source})</span>
                    </div>
                `;
            } else {
                configStatus.innerHTML = `
                    <div class="ha-status-not-configured">
                        <span class="status-indicator disconnected"></span>
                        <span class="status-text">Not Configured</span>
                    </div>
                `;
            }
        }
    } catch (e) {
        console.error('Failed to load HA config:', e);
    }
}

// =============================================================================
// Logs Page - Performance Metrics & Log Stream
// =============================================================================

// Chart.js instances
let sttChart = null;
let ttsChart = null;
let llmChart = null;
let pipelineChart = null;

// Log stream state
let logAutoScroll = true;
let logs = [];
const MAX_LOGS = 1000;

// Dashboard WebSocket for logs
let dashboardWs = null;

function initLogsPage() {
    // Initialize charts
    initPerformanceCharts();

    // Set up filters
    document.getElementById('log-component-filter')?.addEventListener('change', filterLogs);
    document.getElementById('log-level-filter')?.addEventListener('change', filterLogs);
    document.getElementById('log-search')?.addEventListener('input', debounce(filterLogs, 300));

    // Auto-scroll toggle
    document.getElementById('log-auto-scroll')?.addEventListener('change', (e) => {
        logAutoScroll = e.target.checked;
    });

    // Buttons
    document.getElementById('export-logs')?.addEventListener('click', exportLogs);
    document.getElementById('clear-logs')?.addEventListener('click', clearLogs);
    document.getElementById('refresh-metrics')?.addEventListener('click', loadMetricsData);

    // Time range change
    document.getElementById('metrics-time-range')?.addEventListener('change', loadMetricsData);

    // Connect to dashboard WebSocket for real-time logs
    connectDashboardWebSocket();

    // Initial data load
    loadMetricsData();
}

function initPerformanceCharts() {
    const chartConfig = (label, color) => ({
        type: 'line',
        data: {
            labels: [],
            datasets: [{
                label: label,
                data: [],
                borderColor: color,
                backgroundColor: color + '20',
                tension: 0.3,
                fill: true,
                pointRadius: 2,
            }]
        },
        options: {
            responsive: true,
            maintainAspectRatio: false,
            plugins: {
                legend: { display: false }
            },
            scales: {
                x: {
                    display: true,
                    grid: { color: '#333' },
                    ticks: { color: '#888', maxTicksLimit: 6 }
                },
                y: {
                    display: true,
                    grid: { color: '#333' },
                    ticks: { color: '#888' },
                    title: { display: true, text: 'ms', color: '#888' }
                }
            }
        }
    });

    const sttCtx = document.getElementById('stt-latency-chart')?.getContext('2d');
    const ttsCtx = document.getElementById('tts-latency-chart')?.getContext('2d');
    const llmCtx = document.getElementById('llm-latency-chart')?.getContext('2d');
    const pipelineCtx = document.getElementById('pipeline-latency-chart')?.getContext('2d');

    if (sttCtx) sttChart = new Chart(sttCtx, chartConfig('STT Latency', '#60a5fa'));
    if (ttsCtx) ttsChart = new Chart(ttsCtx, chartConfig('TTS Latency', '#34d399'));
    if (llmCtx) llmChart = new Chart(llmCtx, chartConfig('LLM Latency', '#f472b6'));
    if (pipelineCtx) pipelineChart = new Chart(pipelineCtx, chartConfig('Pipeline Total', '#fbbf24'));
}

async function loadMetricsData() {
    const minutes = parseInt(document.getElementById('metrics-time-range')?.value || '60');

    try {
        // Load latency history for each component
        await Promise.all([
            loadComponentMetrics('stt', sttChart, 'stt-stats', minutes),
            loadComponentMetrics('tts', ttsChart, 'tts-stats', minutes),
            loadComponentMetrics('llm', llmChart, 'llm-stats', minutes),
            loadComponentMetrics('pipeline', pipelineChart, 'pipeline-stats', minutes),
        ]);
    } catch (e) {
        console.error('Failed to load metrics:', e);
    }
}

async function loadComponentMetrics(component, chart, statsId, minutes) {
    try {
        const response = await fetch(`${API_BASE}/api/v1/dashboard/metrics/${component}?minutes=${minutes}`);
        if (!response.ok) return;

        const data = await response.json();

        if (chart && data.history) {
            // Update chart
            chart.data.labels = data.history.map(h => {
                const d = new Date(h.timestamp);
                return d.toLocaleTimeString('en-US', { hour: '2-digit', minute: '2-digit' });
            });
            chart.data.datasets[0].data = data.history.map(h => h.avg_ms);
            chart.update('none');
        }

        // Update stats display
        const statsEl = document.getElementById(statsId);
        if (statsEl && data.stats) {
            statsEl.innerHTML = `
                <span class="stat">P50: <strong>${data.stats.p50_ms?.toFixed(0) || '--'}</strong>ms</span>
                <span class="stat">P95: <strong>${data.stats.p95_ms?.toFixed(0) || '--'}</strong>ms</span>
                <span class="stat">Avg: <strong>${data.stats.avg_ms?.toFixed(0) || '--'}</strong>ms</span>
            `;
        }
    } catch (e) {
        console.error(`Failed to load ${component} metrics:`, e);
    }
}

function connectDashboardWebSocket() {
    const dashboardWsUrl = `ws://${window.location.host}/api/v1/ws/dashboard`;

    try {
        dashboardWs = new WebSocket(dashboardWsUrl);

        dashboardWs.onopen = () => {
            console.log('Dashboard WebSocket connected');
            addLogEntry({
                timestamp: new Date().toISOString(),
                level: 'info',
                component: 'system',
                message: 'Connected to log stream'
            });
        };

        dashboardWs.onmessage = (event) => {
            try {
                const msg = JSON.parse(event.data);

                if (msg.type === 'activity') {
                    // Add to logs page
                    addLogEntry({
                        timestamp: msg.data.timestamp,
                        level: msg.data.level,
                        component: msg.data.source,
                        message: msg.data.title + (msg.data.detail ? ': ' + msg.data.detail : '')
                    });

                    // Also add to main activity feed
                    addActivityItem({
                        type: msg.data.type,
                        message: msg.data.title,
                        timestamp: msg.data.timestamp,
                        latency: msg.data.duration_ms
                    });

                    // Track trace if present
                    if (msg.data.trace_id) {
                        if (!activeTraces.has(msg.data.trace_id)) {
                            activeTraces.set(msg.data.trace_id, {
                                trace_id: msg.data.trace_id,
                                signals: [],
                                started_at: msg.data.timestamp
                            });
                        }
                        activeTraces.get(msg.data.trace_id).signals.push(msg.data);
                    }
                } else if (msg.type === 'metrics') {
                    // Update metrics on the fly
                    updateMetricsFromWs(msg.data);
                }
            } catch (e) {
                console.error('Failed to parse dashboard message:', e);
            }
        };

        dashboardWs.onclose = () => {
            console.log('Dashboard WebSocket disconnected');
            // Reconnect after delay
            setTimeout(connectDashboardWebSocket, 5000);
        };

        dashboardWs.onerror = (e) => {
            console.error('Dashboard WebSocket error:', e);
        };
    } catch (e) {
        console.error('Failed to connect dashboard WebSocket:', e);
    }
}

function addLogEntry(entry) {
    logs.unshift(entry);
    if (logs.length > MAX_LOGS) {
        logs.pop();
    }

    renderLogEntry(entry, true);
}

function renderLogEntry(entry, prepend = false) {
    const logStream = document.getElementById('log-stream');
    if (!logStream) return;

    // Apply filters
    const componentFilter = document.getElementById('log-component-filter')?.value;
    const levelFilter = document.getElementById('log-level-filter')?.value;
    const searchFilter = document.getElementById('log-search')?.value?.toLowerCase();

    if (componentFilter && entry.component !== componentFilter) return;
    if (levelFilter && entry.level !== levelFilter) return;
    if (searchFilter && !entry.message?.toLowerCase().includes(searchFilter)) return;

    const time = new Date(entry.timestamp);
    const timeStr = time.toLocaleTimeString('en-US', {
        hour: '2-digit',
        minute: '2-digit',
        second: '2-digit'
    });

    const levelClass = entry.level || 'info';
    const levelText = (entry.level || 'info').toUpperCase();

    const el = document.createElement('div');
    el.className = `log-entry ${levelClass}`;
    el.innerHTML = `
        <span class="log-time">${timeStr}</span>
        <span class="log-level ${levelClass}">${levelText}</span>
        <span class="log-component">${entry.component || 'system'}</span>
        <span class="log-message">${escapeHtml(entry.message || '')}</span>
        ${entry.trace_id ? `<span class="log-trace" data-trace="${entry.trace_id}">🔗</span>` : ''}
    `;

    if (prepend) {
        logStream.insertBefore(el, logStream.firstChild);
    } else {
        logStream.appendChild(el);
    }

    // Auto-scroll
    if (logAutoScroll) {
        logStream.scrollTop = 0;
    }

    // Limit displayed entries
    while (logStream.children.length > 500) {
        logStream.removeChild(logStream.lastChild);
    }
}

function filterLogs() {
    const logStream = document.getElementById('log-stream');
    if (!logStream) return;

    // Clear and re-render
    logStream.innerHTML = '';
    logs.forEach(entry => renderLogEntry(entry, false));
}

function clearLogs() {
    logs = [];
    const logStream = document.getElementById('log-stream');
    if (logStream) {
        logStream.innerHTML = `
            <div class="log-entry info">
                <span class="log-time">--:--:--</span>
                <span class="log-level info">INFO</span>
                <span class="log-component">system</span>
                <span class="log-message">Logs cleared</span>
            </div>
        `;
    }
}

function exportLogs() {
    const data = JSON.stringify(logs, null, 2);
    const blob = new Blob([data], { type: 'application/json' });
    const url = URL.createObjectURL(blob);

    const a = document.createElement('a');
    a.href = url;
    a.download = `barnabeenet-logs-${new Date().toISOString().slice(0, 19).replace(/:/g, '-')}.json`;
    document.body.appendChild(a);
    a.click();
    document.body.removeChild(a);
    URL.revokeObjectURL(url);
}

function updateMetricsFromWs(data) {
    // Called when metrics update comes via WebSocket
    // Could update charts in real-time here
}

function debounce(func, wait) {
    let timeout;
    return function executedFunction(...args) {
        const later = () => {
            clearTimeout(timeout);
            func(...args);
        };
        clearTimeout(timeout);
        timeout = setTimeout(later, wait);
    };
}

function escapeHtml(str) {
    const div = document.createElement('div');
    div.textContent = str;
    return div.innerHTML;
}

// =============================================================================
// PROMPTS PAGE - Agent System Prompts Management
// =============================================================================

const AGENT_INFO = {
    meta_agent: { displayName: 'MetaAgent', description: 'Intent classification and routing', icon: '🎯' },
    instant_agent: { displayName: 'InstantAgent', description: 'Zero-latency pattern responses (no LLM)', icon: '⚡' },
    action_agent: { displayName: 'ActionAgent', description: 'Device control and action parsing', icon: '🎮' },
    interaction_agent: { displayName: 'InteractionAgent', description: 'Complex conversations with Barnabee persona', icon: '💬' },
    memory_agent: { displayName: 'MemoryAgent', description: 'Memory storage and retrieval', icon: '🧠' }
};

let promptsLoaded = false;
let currentPrompt = null;
let originalPromptContent = '';

async function initPromptsPage() {
    if (promptsLoaded) return;
    promptsLoaded = true;

    await loadPrompts();
    setupPromptEventListeners();
}

async function loadPrompts() {
    const grid = document.getElementById('prompts-grid');

    try {
        const response = await fetch('/api/v1/prompts/');
        if (!response.ok) throw new Error('Failed to load prompts');

        const prompts = await response.json();

        grid.innerHTML = prompts.map(prompt => {
            const info = AGENT_INFO[prompt.agent_name] || {
                displayName: prompt.agent_name,
                description: 'Agent prompt',
                icon: '🤖'
            };

            return `
                <div class="prompt-card" data-agent="${prompt.agent_name}">
                    <div class="prompt-card-header">
                        <span class="prompt-card-icon">${info.icon}</span>
                        <div class="prompt-card-title">
                            <h3>${info.displayName}</h3>
                            <small>${info.description}</small>
                        </div>
                    </div>
                    <div class="prompt-card-preview">${escapeHtml(prompt.preview)}</div>
                    <div class="prompt-card-footer">
                        <span class="prompt-card-version">v${prompt.version}</span>
                        <span class="prompt-card-modified">${prompt.last_modified ? formatRelativeTime(prompt.last_modified) : 'Never modified'}</span>
                    </div>
                </div>
            `;
        }).join('');

        // Add click handlers
        grid.querySelectorAll('.prompt-card').forEach(card => {
            card.addEventListener('click', () => openPromptEditor(card.dataset.agent));
        });

    } catch (error) {
        console.error('Failed to load prompts:', error);
        grid.innerHTML = '<div class="loading-indicator">❌ Failed to load prompts</div>';
    }
}

async function openPromptEditor(agentName) {
    const modal = document.getElementById('prompt-modal');
    const editor = document.getElementById('prompt-editor');

    try {
        const response = await fetch(`/api/v1/prompts/${agentName}`);
        if (!response.ok) throw new Error('Failed to load prompt');

        currentPrompt = await response.json();
        originalPromptContent = currentPrompt.content;

        const info = AGENT_INFO[agentName] || { displayName: agentName, description: '', icon: '🤖' };

        // Update modal header
        document.getElementById('prompt-agent-icon').textContent = info.icon;
        document.getElementById('prompt-agent-name').textContent = info.displayName;
        document.getElementById('prompt-agent-description').textContent = info.description;

        // Update editor
        editor.value = currentPrompt.content;
        document.getElementById('prompt-version').textContent = currentPrompt.version;
        updateCharCount();

        modal.style.display = 'flex';
    } catch (error) {
        console.error('Failed to open prompt editor:', error);
        alert('Failed to load prompt: ' + error.message);
    }
}

function updateCharCount() {
    const editor = document.getElementById('prompt-editor');
    const count = editor.value.length;
    document.getElementById('prompt-char-count').textContent = count.toLocaleString();
}

async function savePrompt() {
    if (!currentPrompt) return;

    const editor = document.getElementById('prompt-editor');
    const content = editor.value;

    if (content.length < 10) {
        alert('Prompt must be at least 10 characters');
        return;
    }

    try {
        const response = await fetch(`/api/v1/prompts/${currentPrompt.agent_name}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ content })
        });

        if (!response.ok) throw new Error('Failed to save prompt');

        const result = await response.json();

        // Update version display
        document.getElementById('prompt-version').textContent = result.version;
        originalPromptContent = content;

        // Show success
        const saveBtn = document.getElementById('prompt-save-btn');
        const originalText = saveBtn.textContent;
        saveBtn.textContent = '✅ Saved!';
        saveBtn.disabled = true;
        setTimeout(() => {
            saveBtn.textContent = originalText;
            saveBtn.disabled = false;
        }, 2000);

        // Refresh cards
        await loadPrompts();

    } catch (error) {
        console.error('Failed to save prompt:', error);
        alert('Failed to save prompt: ' + error.message);
    }
}

function resetPrompt() {
    if (!currentPrompt) return;

    if (confirm('Reset to original content? This will discard unsaved changes.')) {
        document.getElementById('prompt-editor').value = originalPromptContent;
        updateCharCount();
    }
}

async function showPromptHistory() {
    if (!currentPrompt) return;

    const historyModal = document.getElementById('prompt-history-modal');
    const historyList = document.getElementById('prompt-history-list');

    try {
        const response = await fetch(`/api/v1/prompts/${currentPrompt.agent_name}/history`);
        if (!response.ok) throw new Error('Failed to load history');

        const history = await response.json();

        if (history.length === 0) {
            historyList.innerHTML = '<p class="text-muted">No history available. Prompts are saved with version history when edited.</p>';
        } else {
            historyList.innerHTML = history.map(item => `
                <div class="history-item" data-version="${item.version}">
                    <div class="history-item-header">
                        <span class="history-item-version">Version ${item.version}</span>
                        <span class="history-item-date">${formatRelativeTime(item.updated_at)}</span>
                    </div>
                    <div class="history-item-preview">${escapeHtml(item.content.slice(0, 200))}${item.content.length > 200 ? '...' : ''}</div>
                    <div class="history-item-actions">
                        <button class="btn btn-small btn-secondary restore-version-btn">↩️ Restore</button>
                    </div>
                </div>
            `).join('');

            // Add restore handlers
            historyList.querySelectorAll('.restore-version-btn').forEach(btn => {
                btn.addEventListener('click', async (e) => {
                    const item = e.target.closest('.history-item');
                    const version = parseInt(item.dataset.version);

                    if (confirm(`Restore version ${version}? Current content will be saved as a new version.`)) {
                        await restorePromptVersion(version);
                    }
                });
            });
        }

        historyModal.style.display = 'flex';

    } catch (error) {
        console.error('Failed to load history:', error);
        alert('Failed to load history: ' + error.message);
    }
}

async function restorePromptVersion(version) {
    if (!currentPrompt) return;

    try {
        const response = await fetch(`/api/v1/prompts/${currentPrompt.agent_name}/restore/${version}`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error('Failed to restore version');

        // Reload the prompt
        await openPromptEditor(currentPrompt.agent_name);

        // Close history modal
        document.getElementById('prompt-history-modal').style.display = 'none';

        // Refresh cards
        await loadPrompts();

        alert(`Restored version ${version}`);

    } catch (error) {
        console.error('Failed to restore version:', error);
        alert('Failed to restore version: ' + error.message);
    }
}

function formatRelativeTime(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diffMs = now - date;
    const diffMins = Math.floor(diffMs / 60000);
    const diffHours = Math.floor(diffMs / 3600000);
    const diffDays = Math.floor(diffMs / 86400000);

    if (diffMins < 1) return 'Just now';
    if (diffMins < 60) return `${diffMins}m ago`;
    if (diffHours < 24) return `${diffHours}h ago`;
    if (diffDays < 7) return `${diffDays}d ago`;
    return date.toLocaleDateString();
}

function setupPromptEventListeners() {
    // Close buttons
    document.getElementById('close-prompt-modal')?.addEventListener('click', () => {
        document.getElementById('prompt-modal').style.display = 'none';
        currentPrompt = null;
    });

    document.getElementById('close-history-modal')?.addEventListener('click', () => {
        document.getElementById('prompt-history-modal').style.display = 'none';
    });

    // Editor actions
    document.getElementById('prompt-save-btn')?.addEventListener('click', savePrompt);
    document.getElementById('prompt-reset-btn')?.addEventListener('click', resetPrompt);
    document.getElementById('prompt-history-btn')?.addEventListener('click', showPromptHistory);

    // Character count
    document.getElementById('prompt-editor')?.addEventListener('input', updateCharCount);

    // Close modals on backdrop click
    document.getElementById('prompt-modal')?.addEventListener('click', (e) => {
        if (e.target.id === 'prompt-modal') {
            document.getElementById('prompt-modal').style.display = 'none';
            currentPrompt = null;
        }
    });

    document.getElementById('prompt-history-modal')?.addEventListener('click', (e) => {
        if (e.target.id === 'prompt-history-modal') {
            document.getElementById('prompt-history-modal').style.display = 'none';
        }
    });

    // Keyboard shortcuts
    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (document.getElementById('prompt-history-modal').style.display !== 'none') {
                document.getElementById('prompt-history-modal').style.display = 'none';
            } else if (document.getElementById('prompt-modal').style.display !== 'none') {
                document.getElementById('prompt-modal').style.display = 'none';
                currentPrompt = null;
            }
        }

        // Ctrl/Cmd + S to save
        if ((e.ctrlKey || e.metaKey) && e.key === 's') {
            if (document.getElementById('prompt-modal').style.display !== 'none' && currentPrompt) {
                e.preventDefault();
                savePrompt();
            }
        }
    });
}

// Initialize logs page when navigating to it
document.addEventListener('DOMContentLoaded', () => {
    // Watch for navigation to logs and prompts pages
    document.querySelectorAll('.nav-link').forEach(link => {
        link.addEventListener('click', () => {
            if (link.dataset.page === 'logs') {
                // Initialize on first visit
                if (!sttChart) {
                    initLogsPage();
                }
            }
            if (link.dataset.page === 'prompts') {
                // Initialize prompts page on first visit
                if (!promptsLoaded) {
                    initPromptsPage();
                }
            }
            if (link.dataset.page === 'chat') {
                // Initialize chat page on first visit
                if (!chatInitialized) {
                    initChatPage();
                }
            }
        });
    });
});


// =============================================================================
// Chat Page - Talk to Barnabee
// =============================================================================

let chatInitialized = false;
let chatMessages = [];
let voiceRecorder = null;
let isRecording = false;
let mediaStream = null;

function initChatPage() {
    chatInitialized = true;

    // Set up event listeners
    const chatInput = document.getElementById('chat-input');
    const sendBtn = document.getElementById('chat-send-btn');
    const clearBtn = document.getElementById('chat-clear-btn');
    const micBtn = document.getElementById('chat-mic-btn');

    // Send on button click
    sendBtn?.addEventListener('click', sendChatMessage);

    // Send on Enter key
    chatInput?.addEventListener('keypress', (e) => {
        if (e.key === 'Enter' && !e.shiftKey) {
            e.preventDefault();
            sendChatMessage();
        }
    });

    // Clear conversation
    clearBtn?.addEventListener('click', clearChat);

    // Microphone button - click to toggle recording
    if (micBtn) {
        micBtn.addEventListener('click', toggleVoiceRecording);
    }

    // Suggestion chips
    document.querySelectorAll('.suggestion-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const suggestion = chip.dataset.suggestion;
            if (suggestion) {
                document.getElementById('chat-input').value = suggestion;
                sendChatMessage();
            }
        });
    });

    // Check if browser supports audio recording
    if (micBtn) {
        if (!navigator.mediaDevices || !navigator.mediaDevices.getUserMedia) {
            micBtn.disabled = true;
            if (!window.isSecureContext) {
                micBtn.title = 'Voice input requires HTTPS. Try accessing via localhost or enable HTTPS.';
                console.warn('Microphone disabled: page not served over HTTPS');
            } else {
                micBtn.title = 'Voice input not supported in this browser';
                console.warn('Microphone disabled: getUserMedia not available');
            }
        } else {
            console.log('Microphone API available');
        }
    }

    console.log('Chat page initialized with voice support');
}

async function sendChatMessage() {
    const input = document.getElementById('chat-input');
    const messagesContainer = document.getElementById('chat-messages');
    const sendBtn = document.getElementById('chat-send-btn');

    const message = input.value.trim();
    if (!message) return;

    // Clear input
    input.value = '';

    // Remove welcome screen if present
    const welcome = messagesContainer.querySelector('.chat-welcome');
    if (welcome) {
        welcome.remove();
    }

    // Add user message
    addChatMessage('user', message);

    // Show thinking indicator
    const thinkingId = showThinkingIndicator();

    // Update status
    updateChatStatus('Thinking...', true);
    sendBtn.disabled = true;

    try {
        // Call the text process endpoint
        const response = await fetch(`${API_BASE}/api/v1/voice/process`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                text: message,
                speaker: 'Dashboard User',
                room: 'Dashboard'
            }),
        });

        const data = await response.json();

        // Remove thinking indicator
        removeThinkingIndicator(thinkingId);

        if (response.ok) {
            // Add assistant response
            const assistantMessage = data.response || data.text || 'I received your message but have no response.';
            const agent = data.agent_used || data.agent || null;
            const intent = data.intent || null;
            const traceId = data.trace_id || null;

            addChatMessage('assistant', assistantMessage, { agent, intent, fullResponse: data, traceId });
            updateChatStatus('Ready to chat');

            // Fetch and display agent chain if we have a trace_id
            if (traceId) {
                setTimeout(() => fetchAndDisplayAgentChain(traceId), 100);
            }
        } else {
            // Error response
            const errorMsg = data.detail || data.error || 'Something went wrong';
            addChatMessage('assistant', errorMsg, { error: true });
            updateChatStatus('Error occurred');
        }
    } catch (error) {
        // Network error
        removeThinkingIndicator(thinkingId);
        addChatMessage('assistant', `Connection error: ${error.message}`, { error: true });
        updateChatStatus('Connection error');
    } finally {
        sendBtn.disabled = false;
        input.focus();
    }
}

function addChatMessage(role, content, meta = {}) {
    const messagesContainer = document.getElementById('chat-messages');

    const messageEl = document.createElement('div');
    messageEl.className = `chat-message ${role}`;

    const avatar = role === 'user' ? '👤' : '🐝';
    const time = new Date().toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' });

    let metaHtml = `<span class="message-time">${time}</span>`;
    if (meta.agent) {
        metaHtml += ` <span class="agent-badge">${meta.agent}</span>`;
    }
    if (meta.intent) {
        metaHtml += ` <span class="agent-badge">${meta.intent}</span>`;
    }

    const bubbleClass = meta.error ? 'message-bubble message-error' : 'message-bubble';
    const clickable = role === 'assistant' && meta.fullResponse ? 'clickable' : '';

    messageEl.innerHTML = `
        <div class="message-avatar">${avatar}</div>
        <div class="message-content">
            <div class="${bubbleClass} ${clickable}">${escapeHtml(content)}</div>
            <div class="message-meta">${metaHtml}</div>
        </div>
    `;

    // Add click handler for assistant messages with response data
    if (role === 'assistant' && meta.fullResponse) {
        const bubble = messageEl.querySelector('.message-bubble');
        bubble.style.cursor = 'pointer';
        bubble.title = 'Click to see details';
        bubble.addEventListener('click', () => showChatResponseDetails(meta.fullResponse));
    }

    messagesContainer.appendChild(messageEl);

    // Scroll to bottom
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    // Store in history
    chatMessages.push({ role, content, time, meta });
}

function showThinkingIndicator() {
    const messagesContainer = document.getElementById('chat-messages');
    const id = 'thinking-' + Date.now();

    const thinkingEl = document.createElement('div');
    thinkingEl.id = id;
    thinkingEl.className = 'chat-message assistant';
    thinkingEl.innerHTML = `
        <div class="message-avatar">🐝</div>
        <div class="message-content">
            <div class="message-bubble thinking-indicator">
                <div class="thinking-dot"></div>
                <div class="thinking-dot"></div>
                <div class="thinking-dot"></div>
            </div>
        </div>
    `;

    messagesContainer.appendChild(thinkingEl);
    messagesContainer.scrollTop = messagesContainer.scrollHeight;

    return id;
}

function removeThinkingIndicator(id) {
    const el = document.getElementById(id);
    if (el) {
        el.remove();
    }
}

function updateChatStatus(status, thinking = false) {
    const statusEl = document.getElementById('chat-status');
    if (statusEl) {
        statusEl.textContent = status;
        statusEl.className = thinking ? 'chat-status thinking' : 'chat-status';
    }
}

function clearChat() {
    const messagesContainer = document.getElementById('chat-messages');
    chatMessages = [];

    // Restore welcome screen
    messagesContainer.innerHTML = `
        <div class="chat-welcome">
            <div class="welcome-avatar">🐝</div>
            <h3>Hello! I'm Barnabee</h3>
            <p>Your friendly home assistant. I can help you with:</p>
            <div class="welcome-suggestions">
                <button class="suggestion-chip" data-suggestion="What time is it?">🕐 What time is it?</button>
                <button class="suggestion-chip" data-suggestion="What's the weather like?">🌤️ Weather</button>
                <button class="suggestion-chip" data-suggestion="Turn on the living room lights">💡 Control lights</button>
                <button class="suggestion-chip" data-suggestion="Tell me a joke">😄 Tell me a joke</button>
                <button class="suggestion-chip" data-suggestion="What can you do?">❓ What can you do?</button>
            </div>
        </div>
    `;

    // Re-attach suggestion chip listeners
    document.querySelectorAll('.suggestion-chip').forEach(chip => {
        chip.addEventListener('click', () => {
            const suggestion = chip.dataset.suggestion;
            if (suggestion) {
                document.getElementById('chat-input').value = suggestion;
                sendChatMessage();
            }
        });
    });

    updateChatStatus('Ready to chat');
    showToast('Conversation cleared');
}

async function fetchAndDisplayAgentChain(traceId) {
    try {
        const response = await fetch(`${API_BASE}/api/v1/activity/traces/${traceId}`);
        if (!response.ok) return;

        const trace = await response.json();
        if (!trace.steps || trace.steps.length === 0) return;

        // Find the last assistant message and add the agent chain
        const messages = document.querySelectorAll('.chat-message.assistant');
        const lastMessage = messages[messages.length - 1];
        if (!lastMessage) return;

        // Create agent chain element
        const chainEl = document.createElement('div');
        chainEl.className = 'agent-chain';

        let chainHtml = `
            <div class="agent-chain-header" onclick="this.parentElement.classList.toggle('expanded')">
                <span class="chain-toggle">▶</span>
                <span class="chain-title">🔗 Agent Chain (${trace.steps.length} steps)</span>
                <span class="chain-duration">${trace.total_duration_ms?.toFixed(0) || '?'}ms</span>
            </div>
            <div class="agent-chain-steps">
        `;

        trace.steps.forEach((step, index) => {
            const icon = getAgentIcon(step.agent);
            const durationStr = step.duration_ms ? `${step.duration_ms.toFixed(0)}ms` : '';
            chainHtml += `
                <div class="chain-step">
                    <span class="step-number">${index + 1}</span>
                    <span class="step-icon">${icon}</span>
                    <span class="step-agent">${step.agent}</span>
                    <span class="step-action">${step.action}</span>
                    <span class="step-summary">${escapeHtml(step.summary || '')}</span>
                    ${durationStr ? `<span class="step-duration">${durationStr}</span>` : ''}
                </div>
            `;
        });

        chainHtml += '</div>';
        chainEl.innerHTML = chainHtml;

        // Add after the message content
        const messageContent = lastMessage.querySelector('.message-content');
        if (messageContent) {
            messageContent.appendChild(chainEl);
        }
    } catch (e) {
        console.warn('Failed to fetch agent chain:', e);
    }
}

function getAgentIcon(agent) {
    const icons = {
        'meta': '🧠',
        'instant': '⚡',
        'action': '🎯',
        'interaction': '💬',
        'memory': '📝',
        'orchestrator': '🎭'
    };
    return icons[agent?.toLowerCase()] || '🔧';
}

function showChatResponseDetails(data) {
    // Create modal overlay
    const modal = document.createElement('div');
    modal.className = 'chat-details-modal';
    modal.onclick = (e) => {
        if (e.target === modal) modal.remove();
    };

    // Build details content
    const intent = data.intent || 'unknown';
    const agent = data.agent_used || data.agent || 'unknown';
    const latency = data.latency_ms?.toFixed(1) || data.total_latency_ms?.toFixed(1) || '?';
    const traceId = data.trace_id || 'N/A';
    const actions = data.actions || [];
    const llmDetails = data.llm_details || null;

    let actionsHtml = '';
    if (actions.length > 0) {
        actionsHtml = `
            <div class="detail-section">
                <h4>🎯 Actions</h4>
                ${actions.map(action => {
            const executed = action.executed !== undefined ? action.executed : 'Not tracked';
            const executionMsg = action.execution_message || '';
            const entityName = action.entity_name || 'Unknown';
            const entityId = action.entity_id || 'Not resolved';
            const service = action.service || 'Unknown';
            const domain = action.domain || 'Unknown';

            const statusClass = action.executed === true ? 'success' :
                action.executed === false ? 'error' : 'pending';

            return `
                        <div class="action-detail ${statusClass}">
                            <div class="action-header">
                                <span class="action-service">${service}</span>
                                <span class="action-status ${statusClass}">
                                    ${action.executed === true ? '✅ Executed' :
                    action.executed === false ? '❌ Failed' : '⏳ Not executed'}
                                </span>
                            </div>
                            <div class="action-info">
                                <div><strong>Entity Name:</strong> ${entityName}</div>
                                <div><strong>Entity ID:</strong> ${entityId}</div>
                                <div><strong>Domain:</strong> ${domain}</div>
                                ${executionMsg ? `<div><strong>Message:</strong> ${executionMsg}</div>` : ''}
                            </div>
                        </div>
                    `;
        }).join('')}
            </div>
        `;
    } else if (intent === 'action') {
        actionsHtml = `
            <div class="detail-section">
                <h4>🎯 Actions</h4>
                <div class="action-detail pending">
                    <div class="action-header">
                        <span class="action-status pending">⚠️ No action data captured</span>
                    </div>
                    <div class="action-info">
                        The action may not have been executed. Check if Home Assistant is connected
                        and the entity exists.
                    </div>
                </div>
            </div>
        `;
    }

    // Build LLM details section
    let llmHtml = '';
    if (llmDetails) {
        const model = llmDetails.model || 'Unknown';
        const inputTokens = llmDetails.input_tokens ?? 'N/A';
        const outputTokens = llmDetails.output_tokens ?? 'N/A';
        const cost = llmDetails.cost_usd ? `$${llmDetails.cost_usd.toFixed(6)}` : 'N/A';
        const llmLatency = llmDetails.llm_latency_ms ? `${llmDetails.llm_latency_ms.toFixed(1)}ms` : 'N/A';
        const messages = llmDetails.messages_sent || [];
        const responseText = llmDetails.response_text || '';

        let messagesHtml = messages.map(msg => {
            const role = msg.role || 'unknown';
            const content = msg.content || '';
            const roleClass = role === 'system' ? 'msg-system' : role === 'user' ? 'msg-user' : 'msg-assistant';
            return `
                <div class="llm-message ${roleClass}">
                    <div class="llm-message-role">${role}</div>
                    <pre class="llm-message-content">${escapeHtml(content)}</pre>
                </div>
            `;
        }).join('');

        llmHtml = `
            <div class="detail-section">
                <h4>🤖 LLM Details</h4>
                <div class="detail-grid">
                    <div class="detail-item">
                        <span class="detail-label">Model</span>
                        <span class="detail-value llm-model">${model}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Input Tokens</span>
                        <span class="detail-value">${inputTokens}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Output Tokens</span>
                        <span class="detail-value">${outputTokens}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">Cost</span>
                        <span class="detail-value">${cost}</span>
                    </div>
                    <div class="detail-item">
                        <span class="detail-label">LLM Latency</span>
                        <span class="detail-value">${llmLatency}</span>
                    </div>
                </div>
                <div class="llm-messages-section">
                    <h5>📤 Messages Sent</h5>
                    <div class="llm-messages-container">
                        ${messagesHtml}
                    </div>
                </div>
                <div class="llm-response-section">
                    <h5>📥 LLM Response</h5>
                    <pre class="llm-response-content">${escapeHtml(responseText)}</pre>
                </div>
            </div>
        `;
    }

    modal.innerHTML = `
        <div class="chat-details-content">
            <div class="chat-details-header">
                <h3>🐝 Response Details</h3>
                <button class="close-btn" onclick="this.closest('.chat-details-modal').remove()">×</button>
            </div>
            <div class="chat-details-body">
                <div class="detail-section">
                    <h4>📊 Processing Info</h4>
                    <div class="detail-grid">
                        <div class="detail-item">
                            <span class="detail-label">Intent</span>
                            <span class="detail-value badge-${intent}">${intent}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Agent</span>
                            <span class="detail-value">${agent}</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Latency</span>
                            <span class="detail-value">${latency}ms</span>
                        </div>
                        <div class="detail-item">
                            <span class="detail-label">Trace ID</span>
                            <span class="detail-value trace-id">${traceId}</span>
                        </div>
                    </div>
                </div>
                ${actionsHtml}
                ${llmHtml}
                <div class="detail-section">
                    <h4>📄 Full Response</h4>
                    <pre class="json-response">${JSON.stringify(data, null, 2)}</pre>
                </div>
            </div>
        </div>
    `;

    document.body.appendChild(modal);
}

function escapeHtml(text) {
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// =============================================================================
// Voice Recording for Chat
// =============================================================================

async function toggleVoiceRecording() {
    if (isRecording) {
        stopVoiceRecording();
    } else {
        await startVoiceRecording();
    }
}

async function startVoiceRecording() {
    if (isRecording) return;

    const micBtn = document.getElementById('chat-mic-btn');
    const voiceIndicator = document.getElementById('chat-voice-indicator');

    try {
        // Request microphone access
        mediaStream = await navigator.mediaDevices.getUserMedia({
            audio: {
                sampleRate: 16000,
                channelCount: 1,
                echoCancellation: true,
                noiseSuppression: true
            }
        });

        // Create MediaRecorder - prefer WAV if supported, otherwise WebM
        let mimeType = 'audio/webm';
        if (MediaRecorder.isTypeSupported('audio/wav')) {
            mimeType = 'audio/wav';
        } else if (MediaRecorder.isTypeSupported('audio/webm;codecs=opus')) {
            mimeType = 'audio/webm;codecs=opus';
        }

        console.log('Recording with mimeType:', mimeType);

        voiceRecorder = new MediaRecorder(mediaStream, { mimeType });
        const audioChunks = [];

        voiceRecorder.ondataavailable = (event) => {
            if (event.data.size > 0) {
                audioChunks.push(event.data);
            }
        };

        voiceRecorder.onstop = async () => {
            // Combine chunks
            const audioBlob = new Blob(audioChunks, { type: mimeType });
            console.log('Recorded blob:', audioBlob.size, 'bytes,', mimeType);

            // Stop all tracks
            mediaStream?.getTracks().forEach(track => track.stop());
            mediaStream = null;

            // Only process if we have actual audio data
            if (audioBlob.size > 0) {
                await processVoiceRecording(audioBlob);
            } else {
                updateChatStatus('No audio recorded');
                voiceIndicator?.classList.remove('active', 'processing');
                micBtn?.classList.remove('recording', 'processing');
            }
        };

        voiceRecorder.onerror = (error) => {
            console.error('Recording error:', error);
            showToast('Recording error: ' + error.message, 'error');
            cleanupRecording();
        };

        // Start recording
        voiceRecorder.start(100); // Collect data every 100ms
        isRecording = true;

        // Update UI
        micBtn?.classList.add('recording');
        voiceIndicator?.classList.add('active');
        voiceIndicator?.classList.remove('processing');
        const statusEl = voiceIndicator?.querySelector('.voice-status');
        if (statusEl) statusEl.textContent = 'Listening...';

        updateChatStatus('Recording...', true);
        console.log('Voice recording started');

    } catch (error) {
        console.error('Failed to start recording:', error);
        if (error.name === 'NotAllowedError') {
            showToast('Microphone access denied. Please allow microphone access in your browser settings.', 'error');
        } else if (error.name === 'NotFoundError') {
            showToast('No microphone found. Please connect a microphone.', 'error');
        } else {
            showToast('Could not start recording: ' + error.message, 'error');
        }
        cleanupRecording();
    }
}

function stopVoiceRecording() {
    if (!isRecording || !voiceRecorder) return;

    const micBtn = document.getElementById('chat-mic-btn');
    const voiceIndicator = document.getElementById('chat-voice-indicator');

    try {
        if (voiceRecorder.state === 'recording') {
            voiceRecorder.stop();
        }
    } catch (error) {
        console.error('Error stopping recording:', error);
    }

    isRecording = false;

    // Update UI to processing state
    micBtn?.classList.remove('recording');
    micBtn?.classList.add('processing');
    voiceIndicator?.classList.add('processing');
    const statusEl = voiceIndicator?.querySelector('.voice-status');
    if (statusEl) statusEl.textContent = 'Processing...';

    updateChatStatus('Processing voice...', true);
    console.log('Voice recording stopped');
}

function cleanupRecording() {
    const micBtn = document.getElementById('chat-mic-btn');
    const voiceIndicator = document.getElementById('chat-voice-indicator');

    isRecording = false;
    voiceRecorder = null;

    if (mediaStream) {
        mediaStream.getTracks().forEach(track => track.stop());
        mediaStream = null;
    }

    micBtn?.classList.remove('recording', 'processing');
    voiceIndicator?.classList.remove('active', 'processing');
    updateChatStatus('Ready to chat');
}

async function processVoiceRecording(audioBlob) {
    const micBtn = document.getElementById('chat-mic-btn');
    const voiceIndicator = document.getElementById('chat-voice-indicator');
    const messagesContainer = document.getElementById('chat-messages');
    const sendBtn = document.getElementById('chat-send-btn');

    try {
        // Send audio directly - server handles format conversion
        // This is much faster than browser-side WebM->WAV conversion
        console.log('Sending audio:', audioBlob.size, 'bytes,', audioBlob.type);

        // Convert blob to base64
        const arrayBuffer = await audioBlob.arrayBuffer();
        const base64Audio = btoa(
            new Uint8Array(arrayBuffer)
                .reduce((data, byte) => data + String.fromCharCode(byte), '')
        );

        // Remove welcome screen if present
        const welcome = messagesContainer?.querySelector('.chat-welcome');
        if (welcome) {
            welcome.remove();
        }

        // Add user voice message indicator
        addChatMessage('user', '🎤 Voice message', { isVoice: true });

        // Show thinking indicator
        const thinkingId = showThinkingIndicator();

        // Disable send button during processing
        if (sendBtn) sendBtn.disabled = true;

        // Call the voice pipeline endpoint
        const response = await fetch(`${API_BASE}/api/v1/voice/pipeline`, {
            method: 'POST',
            headers: {
                'Content-Type': 'application/json',
            },
            body: JSON.stringify({
                audio_base64: base64Audio,
                sample_rate: 16000,
                language: 'en',
                speaker: 'Dashboard User',
                room: 'Dashboard'
            }),
        });

        const data = await response.json();

        // Remove thinking indicator
        removeThinkingIndicator(thinkingId);

        if (response.ok) {
            // Update the user message with transcribed text
            const userMessages = document.querySelectorAll('.chat-message.user');
            const lastUserMessage = userMessages[userMessages.length - 1];
            if (lastUserMessage && data.input_text) {
                const bubble = lastUserMessage.querySelector('.message-bubble');
                if (bubble) {
                    bubble.textContent = `🎤 "${data.input_text}"`;
                }
            }

            // Add assistant response - voice pipeline uses response_text
            const assistantMessage = data.response_text || data.response || data.output_text || 'I heard you, but I have no response.';
            const agent = data.agent || data.agent_used || null;
            const intent = data.intent || null;
            const traceId = data.trace_id || data.request_id || null;

            addChatMessage('assistant', assistantMessage, {
                agent,
                intent,
                fullResponse: data,
                traceId,
                hasAudio: !!data.audio_base64
            });

            // Play audio response if available
            if (data.audio_base64) {
                playAudioResponse(data.audio_base64);
            }

            updateChatStatus('Ready to chat');

            // Fetch and display agent chain if we have a trace_id
            if (traceId) {
                setTimeout(() => fetchAndDisplayAgentChain(traceId), 100);
            }
        } else {
            // Error response - handle both string and object errors
            let errorMsg = 'Voice processing failed';
            if (data.detail) {
                errorMsg = typeof data.detail === 'string' ? data.detail :
                    (data.detail.message || data.detail.error || JSON.stringify(data.detail));
            } else if (data.error) {
                errorMsg = typeof data.error === 'string' ? data.error :
                    (data.error.message || JSON.stringify(data.error));
            } else if (data.message) {
                errorMsg = data.message;
            }

            // Update user message to show error
            const userMessages = document.querySelectorAll('.chat-message.user');
            const lastUserMessage = userMessages[userMessages.length - 1];
            if (lastUserMessage) {
                const bubble = lastUserMessage.querySelector('.message-bubble');
                if (bubble) {
                    bubble.textContent = '🎤 (Voice not recognized)';
                    bubble.classList.add('message-error');
                }
            }
            addChatMessage('assistant', errorMsg, { error: true });
            updateChatStatus('Voice error');
            console.error('Voice pipeline error:', data);
        }
    } catch (error) {
        // Network error
        console.error('Voice processing error:', error);
        addChatMessage('assistant', `Voice processing failed: ${error.message}`, { error: true });
        updateChatStatus('Connection error');
    } finally {
        // Cleanup
        cleanupRecording();
        if (sendBtn) sendBtn.disabled = false;
    }
}

function playAudioResponse(base64Audio) {
    try {
        // Create audio element
        const audioData = atob(base64Audio);
        const audioArray = new Uint8Array(audioData.length);
        for (let i = 0; i < audioData.length; i++) {
            audioArray[i] = audioData.charCodeAt(i);
        }

        const audioBlob = new Blob([audioArray], { type: 'audio/wav' });
        const audioUrl = URL.createObjectURL(audioBlob);

        const audio = new Audio(audioUrl);
        audio.onended = () => {
            URL.revokeObjectURL(audioUrl);
        };
        audio.onerror = (e) => {
            console.warn('Audio playback error:', e);
            URL.revokeObjectURL(audioUrl);
        };

        audio.play().catch(err => {
            console.warn('Could not auto-play audio:', err);
            // Show a play button in the chat if autoplay fails
            showToast('Click to hear Barnabee\'s response 🔊', 'info');
        });
    } catch (error) {
        console.error('Failed to play audio response:', error);
    }
}

// Convert audio blob to WAV format using Web Audio API
async function convertToWav(audioBlob) {
    const audioContext = new (window.AudioContext || window.webkitAudioContext)({
        sampleRate: 16000
    });

    const arrayBuffer = await audioBlob.arrayBuffer();
    const audioBuffer = await audioContext.decodeAudioData(arrayBuffer);

    // Get mono channel data
    const channelData = audioBuffer.getChannelData(0);
    const sampleRate = audioBuffer.sampleRate;

    // Resample to 16kHz if needed
    let samples = channelData;
    if (sampleRate !== 16000) {
        const ratio = 16000 / sampleRate;
        const newLength = Math.round(channelData.length * ratio);
        samples = new Float32Array(newLength);
        for (let i = 0; i < newLength; i++) {
            const srcIndex = i / ratio;
            const srcIndexFloor = Math.floor(srcIndex);
            const srcIndexCeil = Math.min(srcIndexFloor + 1, channelData.length - 1);
            const t = srcIndex - srcIndexFloor;
            samples[i] = channelData[srcIndexFloor] * (1 - t) + channelData[srcIndexCeil] * t;
        }
    }

    // Convert to 16-bit PCM
    const pcmData = new Int16Array(samples.length);
    for (let i = 0; i < samples.length; i++) {
        const s = Math.max(-1, Math.min(1, samples[i]));
        pcmData[i] = s < 0 ? s * 0x8000 : s * 0x7FFF;
    }

    // Create WAV file
    const wavBuffer = createWavBuffer(pcmData, 16000);

    audioContext.close();
    return new Blob([wavBuffer], { type: 'audio/wav' });
}

// Create WAV file buffer from PCM data
function createWavBuffer(pcmData, sampleRate) {
    const numChannels = 1;
    const bitsPerSample = 16;
    const byteRate = sampleRate * numChannels * (bitsPerSample / 8);
    const blockAlign = numChannels * (bitsPerSample / 8);
    const dataSize = pcmData.length * (bitsPerSample / 8);
    const bufferSize = 44 + dataSize;

    const buffer = new ArrayBuffer(bufferSize);
    const view = new DataView(buffer);

    // RIFF header
    writeString(view, 0, 'RIFF');
    view.setUint32(4, bufferSize - 8, true);
    writeString(view, 8, 'WAVE');

    // fmt chunk
    writeString(view, 12, 'fmt ');
    view.setUint32(16, 16, true); // chunk size
    view.setUint16(20, 1, true);  // audio format (PCM)
    view.setUint16(22, numChannels, true);
    view.setUint32(24, sampleRate, true);
    view.setUint32(28, byteRate, true);
    view.setUint16(32, blockAlign, true);
    view.setUint16(34, bitsPerSample, true);

    // data chunk
    writeString(view, 36, 'data');
    view.setUint32(40, dataSize, true);

    // PCM data
    const pcmOffset = 44;
    for (let i = 0; i < pcmData.length; i++) {
        view.setInt16(pcmOffset + i * 2, pcmData[i], true);
    }

    return buffer;
}

function writeString(view, offset, string) {
    for (let i = 0; i < string.length; i++) {
        view.setUint8(offset + i, string.charCodeAt(i));
    }
}
