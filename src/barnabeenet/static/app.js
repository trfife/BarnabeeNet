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
let isOnline = navigator.onLine;

// =============================================================================
// Toast Notification System
// =============================================================================

/**
 * Show a toast notification
 * @param {Object|string} optionsOrMessage - Toast options object OR message string (legacy)
 * @param {string} optionsOrMessage.title - Toast title
 * @param {string} optionsOrMessage.message - Toast message
 * @param {string} optionsOrMessage.type - 'success' | 'error' | 'warning' | 'info'
 * @param {number} optionsOrMessage.duration - Auto-dismiss duration in ms (0 = manual)
 * @param {string} legacyType - Legacy: type if first arg is string
 */
function showToast(optionsOrMessage, legacyType = 'success') {
    // Handle both old style: showToast('message', 'type')
    // and new style: showToast({ title, message, type, duration })
    let title, message, type, duration;

    if (typeof optionsOrMessage === 'string') {
        // Legacy style: showToast('message', 'type')
        message = optionsOrMessage;
        type = legacyType;
        title = type === 'error' ? 'Error' : type === 'warning' ? 'Warning' : 'Notice';
        duration = 5000;
    } else {
        // New style: showToast({ title, message, type, duration })
        ({ title, message, type = 'info', duration = 5000 } = optionsOrMessage);
    }

    const container = document.getElementById('toast-container');
    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;

    const icons = {
        success: '✓',
        error: '✕',
        warning: '⚠',
        info: 'ℹ'
    };

    toast.innerHTML = `
        <span class="toast-icon">${icons[type]}</span>
        <div class="toast-content">
            <div class="toast-title">${title}</div>
            ${message ? `<div class="toast-message">${message}</div>` : ''}
        </div>
        <button class="toast-close" onclick="dismissToast(this.parentElement)">×</button>
        ${duration > 0 ? `<div class="toast-progress" style="animation-duration: ${duration}ms"></div>` : ''}
    `;

    container.appendChild(toast);

    // Auto-dismiss
    if (duration > 0) {
        setTimeout(() => dismissToast(toast), duration);
    }

    return toast;
}

function dismissToast(toast) {
    if (!toast || toast.classList.contains('toast-exit')) return;
    toast.classList.add('toast-exit');
    setTimeout(() => toast.remove(), 300);
}

// =============================================================================
// Loading Skeletons
// =============================================================================

function showCardSkeleton(containerId, rows = 3) {
    const container = document.getElementById(containerId);
    if (!container) return;

    let html = '<div class="card-loading-content">';
    for (let i = 0; i < rows; i++) {
        html += `
            <div class="skeleton-row">
                <div class="skeleton skeleton-label"></div>
                <div class="skeleton skeleton-value"></div>
            </div>
        `;
    }
    html += '</div>';
    container.innerHTML = html;
}

function showStatsSkeleton() {
    const statsIds = ['stat-requests', 'stat-signals', 'stat-memories', 'stat-actions'];
    statsIds.forEach(id => {
        const el = document.getElementById(id);
        if (el) {
            el.innerHTML = '<div class="skeleton skeleton-stat"></div>';
        }
    });
}

function showCardError(containerId, message, retryFn) {
    const container = document.getElementById(containerId);
    if (!container) return;

    container.innerHTML = `
        <div class="card-error">
            <span class="error-icon">⚠️</span>
            <div class="error-message">${message}</div>
            ${retryFn ? `<button class="retry-btn" onclick="${retryFn}()">
                <span class="retry-icon">↻</span> Retry
            </button>` : ''}
        </div>
    `;
}

// =============================================================================
// Offline Detection
// =============================================================================

function initOfflineDetection() {
    const banner = document.getElementById('offline-banner');

    function updateOnlineStatus() {
        isOnline = navigator.onLine;
        if (isOnline) {
            banner.classList.remove('visible');
            document.body.classList.remove('offline');
            // Reconnect WebSocket if disconnected
            if (!ws || ws.readyState !== WebSocket.OPEN) {
                connectWebSocket();
            }
        } else {
            banner.classList.add('visible');
            document.body.classList.add('offline');
            showToast({
                title: 'Connection Lost',
                message: 'You appear to be offline',
                type: 'warning',
                duration: 0
            });
        }
    }

    window.addEventListener('online', updateOnlineStatus);
    window.addEventListener('offline', updateOnlineStatus);
    updateOnlineStatus();
}

// =============================================================================
// Initialization
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initClock();
    initActivityControls();
    initConfigNav();
    // initTestButtons(); // Removed - Setup & Test page no longer exists
    initTraceModal();
    initOfflineDetection();

    // Show loading skeletons
    showCardSkeleton('system-status', 3);
    showCardSkeleton('services-health', 4);
    showStatsSkeleton();

    // Load initial data
    loadSystemStatus();
    loadStats();
    loadTraces();
    loadActiveSISessions();

    // Connect WebSocket
    connectWebSocket();

    // Refresh data periodically
    setInterval(loadSystemStatus, 30000);
    setInterval(loadStats, 60000);
    setInterval(loadTraces, 10000);
    setInterval(loadActiveSISessions, 10000);
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

    // Initialize Logic page when navigating to it
    if (pageId === 'logic') {
        const logicPage = document.getElementById('page-logic');
        if (logicPage && !logicPage.dataset.initialized) {
            initLogicPage();
            logicPage.dataset.initialized = 'true';
        }
    }

    // Initialize Self-Improve page when navigating to it
    if (pageId === 'self-improve') {
        const siPage = document.getElementById('page-self-improve');
        if (siPage && !siPage.dataset.initialized) {
            SelfImprovement.init();
            siPage.dataset.initialized = 'true';
        }
    }
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

let wsReconnectAttempts = 0;
const WS_MAX_RECONNECT_DELAY = 30000;

function connectWebSocket() {
    const statusEl = document.getElementById('ws-status');

    // Don't reconnect if offline
    if (!isOnline) {
        statusEl.className = 'status-indicator disconnected';
        return;
    }

    try {
        ws = new WebSocket(WS_URL);

        ws.onopen = () => {
            statusEl.className = 'status-indicator connected';
            wsReconnectAttempts = 0;

            if (wsReconnectAttempts > 0) {
                showToast({
                    title: 'Connected',
                    message: 'Real-time updates restored',
                    type: 'success',
                    duration: 3000
                });
            }

            addActivityItem({
                type: 'system',
                message: 'Connected to activity stream',
                timestamp: new Date().toISOString()
            });
        };

        ws.onclose = () => {
            statusEl.className = 'status-indicator disconnected';
            wsReconnectAttempts++;

            // Exponential backoff with max delay
            const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempts), WS_MAX_RECONNECT_DELAY);

            addActivityItem({
                type: 'error',
                message: `Disconnected. Reconnecting in ${Math.round(delay / 1000)}s...`,
                timestamp: new Date().toISOString()
            });

            setTimeout(connectWebSocket, delay);
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
        const delay = Math.min(1000 * Math.pow(2, wsReconnectAttempts), WS_MAX_RECONNECT_DELAY);
        setTimeout(connectWebSocket, delay);
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

    // Apply filter (same logic as filterActivityFeed)
    if (activityFilter) {
        const itemType = data.type || '';
        let isVisible = false;
        if (activityFilter.startsWith('category:')) {
            const category = activityFilter.split(':')[1];
            isVisible = matchesCategory(itemType, category);
        } else {
            isVisible = itemType === activityFilter || itemType.startsWith(activityFilter + '.') || itemType.startsWith(activityFilter + '_');
        }
        if (!isVisible) {
            item.style.display = 'none';
        }
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
        const itemType = item.dataset.type || '';
        if (!activityFilter) {
            item.style.display = '';
        } else if (activityFilter.startsWith('category:')) {
            // Category-based filtering
            const category = activityFilter.split(':')[1];
            const isMatch = matchesCategory(itemType, category);
            item.style.display = isMatch ? '' : 'none';
        } else {
            // Exact or prefix match
            const isMatch = itemType === activityFilter || itemType.startsWith(activityFilter + '.') || itemType.startsWith(activityFilter + '_');
            item.style.display = isMatch ? '' : 'none';
        }
    });
}

// Check if activity type matches a category
function matchesCategory(type, category) {
    const categories = {
        ha: ['ha.state_change', 'ha.service_call', 'ha.event', 'ha.sensor_update', 'ha_state_change', 'ha_service_call'],
        llm: ['llm.request', 'llm.response', 'llm.error', 'llm_request', 'llm_call'],
        agent: ['meta.classify', 'meta.route', 'instant.match', 'instant.respond', 'action.parse', 'action.execute',
            'interaction.think', 'interaction.respond', 'agent.thinking', 'agent.decision', 'agent.response'],
        memory: ['memory.search', 'memory.retrieve', 'memory.store', 'memory.fact_extracted', 'memory.consolidated']
    };
    const patterns = categories[category] || [];
    return patterns.some(p => type === p || type.startsWith(p.split('.')[0] + '.') || type.startsWith(p.split('.')[0] + '_'));
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
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        updateSystemStatus(data);
        updateServicesHealth(data.services || []);
    } catch (e) {
        console.error('Failed to load system status:', e);
        showCardError('system-status', 'Failed to load status', 'loadSystemStatus');
        showCardError('services-health', 'Failed to load services', 'loadSystemStatus');
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
        if (!response.ok) throw new Error(`HTTP ${response.status}`);
        const data = await response.json();

        document.getElementById('stat-requests').textContent = formatNumber(data.total_requests || 0);
        document.getElementById('stat-signals').textContent = formatNumber(data.total_signals || 0);
        document.getElementById('stat-memories').textContent = formatNumber(data.total_memories || 0);
        document.getElementById('stat-actions').textContent = formatNumber(data.total_actions || 0);
    } catch (e) {
        console.error('Failed to load stats:', e);
        ['stat-requests', 'stat-signals', 'stat-memories', 'stat-actions'].forEach(id => {
            document.getElementById(id).textContent = '-';
        });
    }
}

/**
 * Format large numbers with K/M suffix
 */
function formatNumber(num) {
    if (num >= 1000000) return (num / 1000000).toFixed(1) + 'M';
    if (num >= 1000) return (num / 1000).toFixed(1) + 'K';
    return num.toString();
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

// Load and display active self-improvement sessions on dashboard
async function loadActiveSISessions() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/self-improve/sessions`);
        if (!response.ok) return;

        const sessions = await response.json();
        const container = document.getElementById('active-si-sessions');
        if (!container) return;

        // Filter to recent/active sessions (last 24 hours or not completed)
        const recentSessions = sessions
            .filter(s => !['completed', 'failed', 'rejected', 'stopped'].includes(s.status) ||
                (new Date() - new Date(s.started_at)) < 24 * 60 * 60 * 1000)
            .slice(0, 5);

        if (recentSessions.length === 0) {
            container.innerHTML = '<p class="text-muted">No recent sessions</p>';
            return;
        }

        container.innerHTML = recentSessions.map(session => {
            const needsAttention = session.status === 'awaiting_plan_approval' || session.status === 'awaiting_approval';
            const relativeTime = formatRelativeTime(session.started_at);
            const statusIcon = {
                'pending': '⏳',
                'diagnosing': '🔍',
                'awaiting_plan_approval': '📋',
                'implementing': '⚙️',
                'testing': '🧪',
                'awaiting_approval': '📝',
                'committing': '💾',
                'completed': '✅',
                'failed': '❌',
                'rejected': '🚫',
                'stopped': '⏹️'
            }[session.status] || '❓';

            return `
                <div class="si-session-card ${session.status}" onclick="navigateToSelfImprove('${session.session_id}')">
                    <div class="si-session-status">${statusIcon} ${session.status.replace(/_/g, ' ')}</div>
                    <div class="si-session-request">${escapeHtml((session.request || '').substring(0, 60))}${session.request?.length > 60 ? '...' : ''}</div>
                    <div class="si-session-time">${relativeTime}</div>
                    ${needsAttention ? '<div class="si-needs-attention">⚠️ Needs your attention</div>' : ''}
                </div>
            `;
        }).join('');
    } catch (error) {
        console.error('Failed to load SI sessions:', error);
    }
}

// Navigate to self-improve page and select a session
function navigateToSelfImprove(sessionId) {
    showPage('self-improve');
    if (sessionId && typeof SelfImprovement !== 'undefined') {
        SelfImprovement.activeSessionId = sessionId;
        SelfImprovement.loadActiveSession();
    }
}

// Helper for relative time display
function formatRelativeTime(dateStr) {
    const date = new Date(dateStr);
    const now = new Date();
    const diff = (now - date) / 1000;

    if (diff < 60) return 'just now';
    if (diff < 3600) return `${Math.floor(diff / 60)}m ago`;
    if (diff < 86400) return `${Math.floor(diff / 3600)}h ago`;
    return `${Math.floor(diff / 86400)}d ago`;
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
// Model Selection Configuration (Simplified - one model per agent)
// =============================================================================

async function loadAgentModels() {
    const container = document.getElementById('agent-models-list');
    if (!container) return;

    try {
        const response = await fetch(`${API_BASE}/api/v1/config/agents/models`);
        const data = await response.json();

        const agentIcons = {
            'meta': '🎯',
            'action': '🏠',
            'interaction': '💬',
            'memory': '🧠',
            'instant': '⚡'
        };

        const agentNames = {
            'meta': 'MetaAgent',
            'action': 'ActionAgent',
            'interaction': 'InteractionAgent',
            'memory': 'MemoryAgent',
            'instant': 'InstantAgent'
        };

        let html = '<div class="agent-models-grid">';
        for (const [agent, config] of Object.entries(data.agents)) {
            html += `
                <div class="agent-model-card">
                    <div class="agent-model-header">
                        <span class="agent-icon">${agentIcons[agent] || '🤖'}</span>
                        <div>
                            <h4>${agentNames[agent] || agent}</h4>
                            <p class="agent-desc">${config.description || ''}</p>
                        </div>
                    </div>
                    <div class="agent-model-info">
                        <div class="model-field">
                            <label>Model:</label>
                            <code>${config.model}</code>
                        </div>
                        <div class="model-field">
                            <label>Temperature:</label>
                            <span>${config.temperature}</span>
                        </div>
                        <div class="model-field">
                            <label>Max Tokens:</label>
                            <span>${config.max_tokens}</span>
                        </div>
                    </div>
                    <div class="agent-model-source">
                        <small>Source: ${data.source}</small>
                    </div>
                </div>
            `;
        }
        html += '</div>';
        container.innerHTML = html;
    } catch (e) {
        console.error('Failed to load agent models:', e);
        container.innerHTML = `<div class="error-message">Failed to load agent models: ${e.message}</div>`;
    }
}

function initModelSelection() {
    // Load agent models when models config section is shown
    document.querySelectorAll('.config-nav li').forEach(item => {
        item.addEventListener('click', () => {
            if (item.dataset.config === 'models') {
                loadAgentModels();
            }
        });
    });
    
    // Load on initial page load if models section is active
    const modelsNav = document.querySelector('.config-nav li[data-config="models"]');
    if (modelsNav && modelsNav.classList.contains('active')) {
        loadAgentModels();
    }
}


// Add to initialization
document.addEventListener('DOMContentLoaded', () => {
    initProviderConfig();
    initModelSelection();
    initHomeAssistant();
    
    // Load agent models if on config page
    if (document.getElementById('agent-models-list')) {
        loadAgentModels();
    }
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
        case 'analysis':
            // Just show the tab, analysis runs on button click
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

// Log Analysis button handler
document.getElementById('run-log-analysis')?.addEventListener('click', runLogAnalysis);

async function runLogAnalysis() {
    const btn = document.getElementById('run-log-analysis');
    const statusEl = document.getElementById('analysis-status');
    const resultsEl = document.getElementById('ha-analysis-results');

    btn.disabled = true;
    btn.textContent = '⏳ Analyzing...';
    statusEl.textContent = 'Analyzing logs with AI...';
    resultsEl.innerHTML = '<div class="loading-spinner">AI is analyzing your logs...</div>';

    try {
        const response = await fetch(`${API_BASE}/api/v1/homeassistant/logs/analyze`, {
            method: 'POST',
        });
        const data = await response.json();

        if (!data.analyzed) {
            resultsEl.innerHTML = `
                <div class="analysis-error">
                    <p>⚠️ ${escapeHtml(data.error || 'Analysis could not be performed')}</p>
                </div>
            `;
            statusEl.textContent = 'Analysis failed';
            return;
        }

        // Render results
        let html = `
            <div class="analysis-summary">
                <div class="summary-icon">${getSummaryIcon(data.issues)}</div>
                <div class="summary-text">
                    <h4>${escapeHtml(data.summary)}</h4>
                    <p class="text-muted">${data.log_count} log entries analyzed</p>
                </div>
            </div>
        `;

        if (data.issues && data.issues.length > 0) {
            html += '<div class="analysis-issues">';
            html += '<h4>Issues Found</h4>';

            // Sort by severity (high first)
            const sortedIssues = [...data.issues].sort((a, b) => {
                const severityOrder = { high: 0, medium: 1, low: 2 };
                return (severityOrder[a.severity] || 3) - (severityOrder[b.severity] || 3);
            });

            for (const issue of sortedIssues) {
                html += renderAnalysisIssue(issue);
            }
            html += '</div>';
        } else {
            html += `
                <div class="no-issues">
                    <p>✅ No significant issues found. Your Home Assistant is running smoothly!</p>
                </div>
            `;
        }

        resultsEl.innerHTML = html;
        statusEl.textContent = `Analysis complete - ${data.issues?.length || 0} issues found`;

    } catch (e) {
        console.error('Log analysis failed:', e);
        resultsEl.innerHTML = `
            <div class="analysis-error">
                <p>❌ Failed to analyze logs: ${escapeHtml(e.message)}</p>
            </div>
        `;
        statusEl.textContent = 'Analysis failed';
    } finally {
        btn.disabled = false;
        btn.textContent = '🔍 Analyze Logs';
    }
}

function getSummaryIcon(issues) {
    if (!issues || issues.length === 0) return '✅';
    const hasHigh = issues.some(i => i.severity === 'high');
    const hasMedium = issues.some(i => i.severity === 'medium');
    if (hasHigh) return '🔴';
    if (hasMedium) return '🟡';
    return '🟢';
}

function renderAnalysisIssue(issue) {
    const severityClass = `severity-${issue.severity}`;
    const severityIcon = {
        high: '🔴',
        medium: '🟡',
        low: '🟢'
    }[issue.severity] || '⚪';

    return `
        <div class="analysis-issue ${severityClass}">
            <div class="issue-header">
                <span class="issue-severity">${severityIcon} ${issue.severity.toUpperCase()}</span>
                <span class="issue-category">${escapeHtml(issue.category)}</span>
            </div>
            <h5 class="issue-title">${escapeHtml(issue.title)}</h5>
            <p class="issue-description">${escapeHtml(issue.description)}</p>
            ${issue.affected_entities && issue.affected_entities.length > 0 ? `
                <div class="issue-entities">
                    <strong>Affected:</strong> ${issue.affected_entities.map(e => escapeHtml(e)).join(', ')}
                </div>
            ` : ''}
            <div class="issue-recommendation">
                <strong>💡 Recommendation:</strong> ${escapeHtml(issue.recommendation)}
            </div>
        </div>
    `;
}

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

// Toast notification helper - REMOVED: Using the proper showToast at the top of the file
// This was conflicting with the object-style showToast function
// function showToast(message, type = 'success') { ... }

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
let chatConversationId = null; // Tracks conversation for history
let voiceRecorder = null;
let isRecording = false;
let mediaStream = null;
let sttEngineStatus = null; // Current STT engine status

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

    // Initialize STT settings
    initSTTSettings();

    // Fix This button - launch self-improvement from chat
    const fixThisBtn = document.getElementById('chat-self-improve-btn');
    if (fixThisBtn) {
        fixThisBtn.addEventListener('click', async () => {
            // Get the last exchange from chat
            const lastUserMsg = [...chatMessages].reverse().find(m => m.role === 'user');
            const lastAssistantMsg = [...chatMessages].reverse().find(m => m.role === 'assistant');

            if (!lastUserMsg && !lastAssistantMsg) {
                showToast('No conversation to fix', 'warning');
                return;
            }

            // Build improvement request from chat context
            const request = `Fix incorrect chat response:

**User said:** ${lastUserMsg?.content || 'N/A'}

**Barnabee responded:** ${lastAssistantMsg?.content || 'N/A'}

Please investigate why this response was incorrect and propose a fix. Consider:
- Was the intent understood correctly?
- Was the correct action taken?
- Was the response appropriate?`;

            // Navigate to self-improvement page
            showPage('self-improve');

            // Wait for page to load
            await new Promise(resolve => setTimeout(resolve, 100));

            // Submit the improvement request
            try {
                const response = await fetch(`${API_BASE}/api/v1/self-improve/improve`, {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({
                        request: request,
                        model: 'opusplan',
                        auto_approve: false,
                        source: 'chat_fix_button'
                    }),
                });

                if (!response.ok) throw new Error(`HTTP ${response.status}`);

                const result = await response.json();
                showToast('Self-improvement session started', 'success');

                if (result.session_id && SelfImprovement) {
                    SelfImprovement.activeSessionId = result.session_id;
                    SelfImprovement.startStreaming(result.session_id);
                    await SelfImprovement.loadActiveSession();
                }
            } catch (error) {
                console.error('Failed to start self-improvement:', error);
                showToast('Failed to start self-improvement: ' + error.message, 'error');
            }
        });
    }

    console.log('Chat page initialized with voice support');
}

// =============================================================================
// STT Settings and Status
// =============================================================================

async function initSTTSettings() {
    // Load STT engine status
    await refreshSTTStatus();

    // Set up change listeners for STT selectors
    const modeSelect = document.getElementById('stt-mode-select');
    const engineSelect = document.getElementById('stt-engine-select');

    modeSelect?.addEventListener('change', () => {
        console.log('STT mode changed to:', modeSelect.value);
    });

    engineSelect?.addEventListener('change', async () => {
        console.log('STT engine changed to:', engineSelect.value);
        // Validate engine availability
        if (sttEngineStatus && engineSelect.value !== 'auto') {
            const engines = sttEngineStatus.engines || {};
            const selected = engines[engineSelect.value];
            if (selected && !selected.available) {
                showToast(`Warning: ${engineSelect.value} engine is currently unavailable`, 'warning');
            }
        }
    });

    // Refresh status periodically
    setInterval(refreshSTTStatus, 30000);
}

async function refreshSTTStatus() {
    const statusIndicator = document.getElementById('stt-status-indicator');
    const statusDot = statusIndicator?.querySelector('.stt-status-dot');
    const statusText = statusIndicator?.querySelector('.stt-status-text');
    const engineSelect = document.getElementById('stt-engine-select');

    try {
        const response = await fetch(`${API_BASE}/api/v1/voice/stt/status`);
        if (!response.ok) throw new Error('Failed to fetch STT status');

        sttEngineStatus = await response.json();

        // Update status indicator
        const engines = sttEngineStatus.engines || {};
        const availableEngines = Object.entries(engines)
            .filter(([_, info]) => info.available)
            .map(([name]) => name);

        if (availableEngines.includes('parakeet')) {
            statusDot?.classList.remove('partial', 'disconnected');
            statusDot?.classList.add('connected');
            statusText && (statusText.textContent = 'GPU Ready');
        } else if (availableEngines.includes('azure')) {
            statusDot?.classList.remove('connected', 'disconnected');
            statusDot?.classList.add('partial');
            statusText && (statusText.textContent = 'Azure Ready');
        } else if (availableEngines.includes('whisper')) {
            statusDot?.classList.remove('connected', 'partial');
            statusDot?.classList.add('disconnected');
            statusText && (statusText.textContent = 'CPU Only');
        }

        // Update engine select options with availability
        if (engineSelect) {
            Array.from(engineSelect.options).forEach(option => {
                if (option.value === 'auto') return;
                const engineInfo = engines[option.value];
                const available = engineInfo?.available ?? false;
                const suffix = available ? ' ✓' : ' ✗';
                const baseName = option.text.replace(/ [✓✗]$/, '');
                option.text = baseName + suffix;
                option.disabled = !available && option.value !== 'whisper';
            });
        }

        console.log('STT status refreshed:', sttEngineStatus);

    } catch (error) {
        console.error('Failed to refresh STT status:', error);
        statusDot?.classList.remove('connected', 'partial');
        statusDot?.classList.add('disconnected');
        statusText && (statusText.textContent = 'Error');
    }
}

function getSelectedSTTConfig() {
    return {
        mode: document.getElementById('stt-mode-select')?.value || 'command',
        engine: document.getElementById('stt-engine-select')?.value || 'auto'
    };
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
                room: 'Dashboard',
                conversation_id: chatConversationId
            }),
        });

        const data = await response.json();

        // Remove thinking indicator
        removeThinkingIndicator(thinkingId);

        if (response.ok) {
            // Store conversation_id for subsequent messages
            if (data.conversation_id) {
                chatConversationId = data.conversation_id;
            }

            // Add assistant response
            const assistantMessage = data.response || data.text || 'I received your message but have no response.';
            const agent = data.agent_used || data.agent || null;
            const intent = data.intent || null;
            const traceId = data.trace_id || null;

            addChatMessage('assistant', assistantMessage, { agent, intent, fullResponse: data, traceId });
            updateChatStatus('Ready to chat');

            // Show processing flow immediately from response data, then enhance with trace
            showProcessingFlow(data, traceId);
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
    chatConversationId = null; // Reset conversation for fresh start

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

function showProcessingFlow(data, traceId) {
    // Find the last assistant message
    const messages = document.querySelectorAll('.chat-message.assistant');
    const lastMessage = messages[messages.length - 1];
    if (!lastMessage) return;

    const messageContent = lastMessage.querySelector('.message-content');
    if (!messageContent) return;

    // Build processing flow from response data
    const flowEl = document.createElement('div');
    flowEl.className = 'processing-flow expanded';

    const intent = data.intent || 'unknown';
    const agent = data.agent_used || data.agent || 'unknown';
    const llmDetails = data.llm_details;
    const traceDetails = data.trace_details || {};
    const latency = data.latency_ms?.toFixed(0) || data.total_latency_ms?.toFixed(0) || '?';
    const memoriesRetrieved = data.memories_retrieved || 0;
    const memoriesStored = data.memories_stored || 0;
    const actions = data.actions || [];

    // Build flow steps
    let flowHtml = `
        <div class="flow-header" onclick="this.parentElement.classList.toggle('expanded')">
            <span class="flow-toggle">▼</span>
            <span class="flow-title">📊 Processing Flow</span>
            <span class="flow-duration">${latency}ms total</span>
        </div>
        <div class="flow-steps">
    `;

    // Step 1: Input
    flowHtml += `
        <div class="flow-step flow-input">
            <div class="flow-step-icon">📥</div>
            <div class="flow-step-content">
                <div class="flow-step-label">Input</div>
                <div class="flow-step-value">"${escapeHtml(data.text || '')}"</div>
            </div>
        </div>
        <div class="flow-arrow">↓</div>
    `;

    // Step 2: Classification with routing reason
    let classificationHtml = `Intent: <strong>${intent}</strong>`;
    if (traceDetails.routing_reason) {
        classificationHtml += `<br><span class="flow-routing-reason">${escapeHtml(traceDetails.routing_reason)}</span>`;
    }
    if (traceDetails.pattern_matched) {
        classificationHtml += `<br><span class="flow-pattern">Pattern: <code>${escapeHtml(traceDetails.pattern_matched)}</code></span>`;
    }
    if (traceDetails.meta_processing_time_ms) {
        classificationHtml += `<br><span class="flow-timing">Classification: ${traceDetails.meta_processing_time_ms.toFixed(0)}ms</span>`;
    }

    flowHtml += `
        <div class="flow-step flow-classify">
            <div class="flow-step-icon">🧠</div>
            <div class="flow-step-content">
                <div class="flow-step-label">MetaAgent Classification</div>
                <div class="flow-step-value">${classificationHtml}</div>
            </div>
        </div>
        <div class="flow-arrow">↓</div>
    `;

    // Step 3: Memory retrieval (if any)
    if (memoriesRetrieved > 0 || (traceDetails.memory_queries && traceDetails.memory_queries.length > 0)) {
        let memoryHtml = `Retrieved ${memoriesRetrieved} relevant memories`;

        // Show what queries were used
        if (traceDetails.memory_queries && traceDetails.memory_queries.length > 0) {
            memoryHtml += `<br><span class="flow-memory-queries">Queries: ${traceDetails.memory_queries.map(q => `"${escapeHtml(q)}"`).join(', ')}</span>`;
        }

        // Show context evaluation (it's an object with emotional_tone, urgency_level, empathy_needed)
        if (traceDetails.context_evaluation && typeof traceDetails.context_evaluation === 'object') {
            const ctx = traceDetails.context_evaluation;
            const parts = [];
            if (ctx.emotional_tone) parts.push(`Tone: ${ctx.emotional_tone}`);
            if (ctx.urgency_level) parts.push(`Urgency: ${ctx.urgency_level}`);
            if (ctx.empathy_needed) parts.push('Empathy needed');
            if (parts.length > 0) {
                memoryHtml += `<br><span class="flow-context">${escapeHtml(parts.join(' • '))}</span>`;
            }
        } else if (traceDetails.context_evaluation) {
            memoryHtml += `<br><span class="flow-context">${escapeHtml(String(traceDetails.context_evaluation))}</span>`;
        }

        flowHtml += `
            <div class="flow-step flow-memory">
                <div class="flow-step-icon">📝</div>
                <div class="flow-step-content">
                    <div class="flow-step-label">Memory Retrieval</div>
                    <div class="flow-step-value">${memoryHtml}</div>
                </div>
            </div>
            <div class="flow-arrow">↓</div>
        `;
    }

    // Step 4: Agent routing and processing
    const agentIcon = getAgentIcon(agent);
    let agentDetails = `Routed to: <strong>${agent}</strong>`;

    if (llmDetails && llmDetails.model) {
        const modelName = llmDetails.model.split('/').pop(); // Get just model name
        const tokens = (llmDetails.input_tokens || 0) + (llmDetails.output_tokens || 0);
        const llmLatency = llmDetails.llm_latency_ms?.toFixed(0) || '?';
        agentDetails += `<br><span class="flow-model">Model: <code>${modelName}</code></span>`;
        agentDetails += `<br><span class="flow-tokens">${tokens} tokens • ${llmLatency}ms LLM time</span>`;
    }

    // Show action agent mode if available
    if (agent === 'action' && traceDetails.action_agent_mode) {
        agentDetails += `<br><span class="flow-mode">Mode: <code>${traceDetails.action_agent_mode}</code></span>`;
    }

    flowHtml += `
        <div class="flow-step flow-agent">
            <div class="flow-step-icon">${agentIcon}</div>
            <div class="flow-step-content">
                <div class="flow-step-label">Agent Processing</div>
                <div class="flow-step-value">${agentDetails}</div>
            </div>
        </div>
    `;

    // Step 4b: Parsed segments (for compound commands)
    if (traceDetails.parsed_segments && traceDetails.parsed_segments.length > 1) {
        flowHtml += `<div class="flow-arrow">↓</div>`;
        let segmentsHtml = traceDetails.parsed_segments.map((seg, i) => {
            const parts = [];
            if (seg.action) parts.push(`<strong>${escapeHtml(seg.action)}</strong>`);
            if (seg.target) parts.push(escapeHtml(seg.target));
            if (seg.location) parts.push(`in ${escapeHtml(seg.location)}`);
            if (seg.value) parts.push(`to ${escapeHtml(seg.value)}`);
            return `<div class="flow-segment-item">${i + 1}. ${parts.join(' ')}</div>`;
        }).join('');

        flowHtml += `
            <div class="flow-step flow-parsing">
                <div class="flow-step-icon">🔀</div>
                <div class="flow-step-content">
                    <div class="flow-step-label">Compound Command Parsed</div>
                    <div class="flow-step-value">${segmentsHtml}</div>
                </div>
            </div>
        `;
    }

    // Step 5: Service calls (enhanced with full details)
    const serviceCalls = traceDetails.service_calls || [];
    if (serviceCalls.length > 0) {
        flowHtml += `<div class="flow-arrow">↓</div>`;
        let callsHtml = serviceCalls.map(call => {
            let details = [];

            // Service name
            details.push(`<code>${escapeHtml(call.service || 'unknown')}</code>`);

            // Target description
            if (call.target_desc) {
                details.push(`<span class="flow-service-target">Target: ${escapeHtml(call.target_desc)}</span>`);
            } else if (call.target) {
                // Build target description from target object
                if (call.target.floor_id) {
                    const floors = Array.isArray(call.target.floor_id) ? call.target.floor_id.join(', ') : call.target.floor_id;
                    details.push(`<span class="flow-service-target">Floors: ${escapeHtml(floors)}</span>`);
                } else if (call.target.area_id) {
                    const areas = Array.isArray(call.target.area_id) ? call.target.area_id.join(', ') : call.target.area_id;
                    details.push(`<span class="flow-service-target">Areas: ${escapeHtml(areas)}</span>`);
                } else if (call.target.entity_id) {
                    details.push(`<span class="flow-service-target">Entity: ${escapeHtml(call.target.entity_id)}</span>`);
                }
            } else if (call.entity_id) {
                details.push(`<span class="flow-service-target">Entity: ${escapeHtml(call.entity_id)}</span>`);
            }

            // Batch indicator
            if (call.is_batch) {
                details.push(`<span class="flow-service-batch">batch</span>`);
            }

            // Affected count
            if (call.affected_count !== undefined && call.affected_count !== null) {
                details.push(`<span class="flow-service-affected">${call.affected_count} entities affected</span>`);
            }

            // Success indicator
            if (call.executed !== undefined) {
                const statusClass = call.success ? 'flow-success' : 'flow-failure';
                const statusIcon = call.success ? '✓' : '✗';
                details.push(`<span class="${statusClass}">${statusIcon}</span>`);
            }

            return `<div class="flow-service-call">${details.join(' ')}</div>`;
        }).join('');

        flowHtml += `
            <div class="flow-step flow-action">
                <div class="flow-step-icon">🎯</div>
                <div class="flow-step-content">
                    <div class="flow-step-label">HA Service Calls</div>
                    <div class="flow-step-value">${callsHtml}</div>
                </div>
            </div>
        `;
    } else if (actions.length > 0) {
        // Fallback to old actions format
        flowHtml += `<div class="flow-arrow">↓</div>`;
        flowHtml += `
            <div class="flow-step flow-action">
                <div class="flow-step-icon">🎯</div>
                <div class="flow-step-content">
                    <div class="flow-step-label">Actions Executed</div>
                    <div class="flow-step-value">${actions.map(a => `<div class="flow-action-item">${escapeHtml(JSON.stringify(a))}</div>`).join('')}</div>
                </div>
            </div>
        `;
    }

    // Step 5b: Timer info (if present)
    if (traceDetails.timer_info) {
        flowHtml += `<div class="flow-arrow">↓</div>`;
        const timer = traceDetails.timer_info;
        let timerHtml = `<strong>${timer.type || 'timer'}</strong>`;
        if (timer.duration) timerHtml += ` for ${timer.duration}`;
        if (timer.action) timerHtml += ` then: ${escapeHtml(timer.action)}`;
        if (timer.entity_id) timerHtml += `<br><span class="flow-timer-entity">Entity: <code>${timer.entity_id}</code></span>`;

        flowHtml += `
            <div class="flow-step flow-timer">
                <div class="flow-step-icon">⏱️</div>
                <div class="flow-step-content">
                    <div class="flow-step-label">Timer Started</div>
                    <div class="flow-step-value">${timerHtml}</div>
                </div>
            </div>
        `;
    }

    // Step 6: Memory storage (if any)
    if (memoriesStored > 0) {
        flowHtml += `<div class="flow-arrow">↓</div>`;
        flowHtml += `
            <div class="flow-step flow-memory-store">
                <div class="flow-step-icon">💾</div>
                <div class="flow-step-content">
                    <div class="flow-step-label">Memory Storage</div>
                    <div class="flow-step-value">Stored ${memoriesStored} new memories</div>
                </div>
            </div>
        `;
    }

    // Final: Response
    flowHtml += `<div class="flow-arrow">↓</div>`;
    const responsePreview = (data.response || '').substring(0, 100) + ((data.response || '').length > 100 ? '...' : '');
    flowHtml += `
        <div class="flow-step flow-response">
            <div class="flow-step-icon">💬</div>
            <div class="flow-step-content">
                <div class="flow-step-label">Response Generated</div>
                <div class="flow-step-value">"${escapeHtml(responsePreview)}"</div>
            </div>
        </div>
    `;

    flowHtml += '</div>'; // Close flow-steps

    flowEl.innerHTML = flowHtml;
    messageContent.appendChild(flowEl);

    // If we have a trace_id, fetch additional details asynchronously
    if (traceId) {
        fetchTraceEnhancements(traceId, flowEl);
    }
}

async function fetchTraceEnhancements(traceId, flowEl) {
    try {
        const response = await fetch(`${API_BASE}/api/v1/activity/traces/${traceId}`);
        if (!response.ok) return;

        const trace = await response.json();
        if (!trace.steps || trace.steps.length === 0) return;

        // Update duration with accurate trace timing
        const durationEl = flowEl.querySelector('.flow-duration');
        if (durationEl && trace.total_duration_ms) {
            durationEl.textContent = `${trace.total_duration_ms.toFixed(0)}ms total`;
        }

        // Could enhance individual steps with trace timing here if needed
    } catch (e) {
        console.warn('Failed to fetch trace enhancements:', e);
    }
}

async function fetchAndDisplayAgentChain(traceId) {
    // Legacy function - now handled by showProcessingFlow
    // Kept for compatibility
    return;
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

    // Get STT settings
    const sttConfig = getSelectedSTTConfig();

    try {
        // Send audio directly - server handles format conversion
        // This is much faster than browser-side WebM->WAV conversion
        console.log('Sending audio:', audioBlob.size, 'bytes,', audioBlob.type, 'engine:', sttConfig.engine, 'mode:', sttConfig.mode);

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

        // Add user voice message indicator with STT info
        const engineLabel = sttConfig.engine === 'auto' ? 'auto' : sttConfig.engine;
        addChatMessage('user', `🎤 Voice message (${engineLabel})`, { isVoice: true });

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
                room: 'Dashboard',
                // Include STT settings (if the endpoint supports them)
                stt_engine: sttConfig.engine,
                stt_mode: sttConfig.mode
            }),
        });

        const data = await response.json();

        // Remove thinking indicator
        removeThinkingIndicator(thinkingId);

        if (response.ok) {
            // Get STT engine used from response
            const sttEngine = data.stt_engine || data.engine_used || sttConfig.engine;

            // Update the user message with transcribed text and engine used
            const userMessages = document.querySelectorAll('.chat-message.user');
            const lastUserMessage = userMessages[userMessages.length - 1];
            if (lastUserMessage && data.input_text) {
                const bubble = lastUserMessage.querySelector('.message-bubble');
                if (bubble) {
                    const engineBadge = `<span class="stt-engine-badge ${sttEngine}">${sttEngine}</span>`;
                    bubble.innerHTML = `🎤 "${escapeHtml(data.input_text)}" ${engineBadge}`;
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
                hasAudio: !!data.audio_base64,
                sttEngine
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
// =============================================================================
// Memory System
// =============================================================================

let memoryCurrentPage = 1;
let memoryPageSize = 20;
let memoryInitialized = false;

function initMemory() {
    if (memoryInitialized) return;
    memoryInitialized = true;

    // Tab switching
    document.querySelectorAll('.memory-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.dataset.tab;
            switchMemoryTab(tabId);
        });
    });

    // Filter controls
    const typeFilter = document.getElementById('memory-type-filter');
    const participantFilter = document.getElementById('memory-participant-filter');
    const refreshBtn = document.getElementById('memory-refresh-btn');

    if (typeFilter) typeFilter.addEventListener('change', () => loadMemories(1));
    if (participantFilter) participantFilter.addEventListener('change', () => loadMemories(1));
    if (refreshBtn) refreshBtn.addEventListener('click', () => loadMemories(memoryCurrentPage));

    // Search
    const searchBtn = document.getElementById('memory-search-btn');
    const searchInput = document.getElementById('memory-search-input');
    if (searchBtn) searchBtn.addEventListener('click', searchMemories);
    if (searchInput) {
        searchInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') searchMemories();
        });
    }

    // Add memory
    const addBtn = document.getElementById('add-memory-btn');
    if (addBtn) addBtn.addEventListener('click', addMemory);

    // Diary generation
    const generateDiaryBtn = document.getElementById('generate-diary-btn');
    const diaryDatePicker = document.getElementById('diary-date-picker');

    // Set default date to today
    if (diaryDatePicker) {
        const today = new Date().toISOString().split('T')[0];
        diaryDatePicker.value = today;
    }

    if (generateDiaryBtn) {
        generateDiaryBtn.addEventListener('click', generateDiaryEntry);
    }

    // Initial load
    loadMemoryStats();
    loadMemories(1);
}

function switchMemoryTab(tabId) {
    // Update tab buttons
    document.querySelectorAll('.memory-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.tab === tabId);
    });

    // Update tab content
    document.querySelectorAll('.memory-tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `tab-${tabId}`);
    });

    // Load data for tab
    switch (tabId) {
        case 'all':
            loadMemories(1);
            break;
        case 'semantic':
            loadMemoriesByType('semantic');
            break;
        case 'episodic':
            loadMemoriesByType('episodic');
            break;
        case 'diary':
            loadDiary();
            break;
    }
}

async function loadMemoryStats() {
    try {
        const resp = await fetch(`${API_BASE}/api/v1/memory/stats`);
        if (!resp.ok) throw new Error('Failed to load stats');
        const data = await resp.json();

        document.getElementById('memory-total').textContent = data.total_memories || 0;
        document.getElementById('memory-24h').textContent = data.memories_24h || 0;
        document.getElementById('memory-7d').textContent = data.memories_7d || 0;
        document.getElementById('memory-backend').textContent = data.storage_backend || '-';
    } catch (error) {
        console.error('Error loading memory stats:', error);
    }
}

async function loadMemories(page = 1) {
    memoryCurrentPage = page;
    const list = document.getElementById('memory-list');
    list.innerHTML = '<div class="loading">Loading memories...</div>';

    try {
        const typeFilter = document.getElementById('memory-type-filter')?.value || '';
        const participantFilter = document.getElementById('memory-participant-filter')?.value || '';

        let url = `${API_BASE}/api/v1/memory/?skip=${(page - 1) * memoryPageSize}&limit=${memoryPageSize}`;
        if (typeFilter) url += `&memory_type=${typeFilter}`;
        if (participantFilter) url += `&participant=${encodeURIComponent(participantFilter)}`;

        const resp = await fetch(url);
        if (!resp.ok) throw new Error('Failed to load memories');
        const data = await resp.json();

        if (data.memories.length === 0) {
            list.innerHTML = `
                <div class="memory-empty">
                    <div class="memory-empty-icon">🧠</div>
                    <h3>No memories yet</h3>
                    <p>Barnabee will start remembering things as you interact!</p>
                </div>
            `;
        } else {
            list.innerHTML = data.memories.map(renderMemoryCard).join('');
        }

        renderPagination(data.total, page);
    } catch (error) {
        console.error('Error loading memories:', error);
        list.innerHTML = `<div class="error">Failed to load memories: ${error.message}</div>`;
    }
}

async function loadMemoriesByType(memoryType) {
    const listId = `${memoryType}-list`;
    const list = document.getElementById(listId);
    if (!list) return;

    list.innerHTML = '<div class="loading">Loading...</div>';

    try {
        const resp = await fetch(`${API_BASE}/api/v1/memory/?memory_type=${memoryType}&limit=50`);
        if (!resp.ok) throw new Error('Failed to load memories');
        const data = await resp.json();

        if (data.memories.length === 0) {
            list.innerHTML = `
                <div class="memory-empty">
                    <div class="memory-empty-icon">📭</div>
                    <h3>No ${memoryType} memories</h3>
                </div>
            `;
        } else {
            list.innerHTML = data.memories.map(renderMemoryCard).join('');
        }
    } catch (error) {
        console.error(`Error loading ${memoryType} memories:`, error);
        list.innerHTML = `<div class="error">Failed to load: ${error.message}</div>`;
    }
}

function renderMemoryCard(memory) {
    const typeIcons = {
        semantic: '💡',
        episodic: '📝',
        procedural: '⚙️',
        working: '⏱️'
    };

    const icon = typeIcons[memory.memory_type] || '💭';
    const timestamp = new Date(memory.timestamp).toLocaleString();
    const participants = memory.participants?.join(', ') || '-';
    const importance = memory.importance ? `${Math.round(memory.importance * 100)}%` : '-';

    const tags = (memory.tags || []).map(tag =>
        `<span class="memory-tag">${escapeHtml(tag)}</span>`
    ).join('');

    return `
        <div class="memory-card" data-id="${memory.id}">
            <div class="memory-card-header">
                <span class="memory-type-badge ${memory.memory_type}">${icon} ${memory.memory_type}</span>
                <div class="memory-actions">
                    <button class="memory-action-btn" onclick="deleteMemory('${memory.id}')" title="Delete">🗑️</button>
                </div>
            </div>
            <div class="memory-content">${escapeHtml(memory.content)}</div>
            <div class="memory-meta">
                <span class="memory-meta-item">📅 ${timestamp}</span>
                <span class="memory-meta-item">👥 ${escapeHtml(participants)}</span>
                <span class="memory-meta-item">⭐ ${importance}</span>
            </div>
            ${tags ? `<div class="memory-tags">${tags}</div>` : ''}
        </div>
    `;
}

function renderPagination(total, currentPage) {
    const pagination = document.getElementById('memory-pagination');
    if (!pagination) return;

    const totalPages = Math.ceil(total / memoryPageSize);
    if (totalPages <= 1) {
        pagination.innerHTML = '';
        return;
    }

    let html = '';
    html += `<button ${currentPage === 1 ? 'disabled' : ''} onclick="loadMemories(${currentPage - 1})">← Prev</button>`;

    for (let i = 1; i <= totalPages; i++) {
        if (i === 1 || i === totalPages || (i >= currentPage - 2 && i <= currentPage + 2)) {
            html += `<button class="${i === currentPage ? 'active' : ''}" onclick="loadMemories(${i})">${i}</button>`;
        } else if (i === currentPage - 3 || i === currentPage + 3) {
            html += `<span>...</span>`;
        }
    }

    html += `<button ${currentPage === totalPages ? 'disabled' : ''} onclick="loadMemories(${currentPage + 1})">Next →</button>`;
    pagination.innerHTML = html;
}

async function searchMemories() {
    const input = document.getElementById('memory-search-input');
    const results = document.getElementById('memory-search-results');
    const query = input?.value?.trim();

    if (!query) {
        results.innerHTML = '<p class="search-hint">Enter a question or topic to search.</p>';
        return;
    }

    results.innerHTML = '<div class="loading">Searching...</div>';

    try {
        const resp = await fetch(`${API_BASE}/api/v1/memory/search`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ query, limit: 10 })
        });
        if (!resp.ok) throw new Error('Search failed');
        const data = await resp.json();

        if (data.results.length === 0) {
            results.innerHTML = '<p class="search-hint">No matching memories found.</p>';
        } else {
            results.innerHTML = data.results.map(r => `
                <div class="search-result-item">
                    <div class="memory-card-header">
                        <span class="memory-type-badge ${r.memory.memory_type}">${r.memory.memory_type}</span>
                        <span class="similarity-score">🎯 ${Math.round(r.similarity * 100)}% match</span>
                    </div>
                    <div class="memory-content">${escapeHtml(r.memory.content)}</div>
                </div>
            `).join('');
        }
    } catch (error) {
        console.error('Search error:', error);
        results.innerHTML = `<div class="error">Search failed: ${error.message}</div>`;
    }
}

async function addMemory() {
    const content = document.getElementById('add-memory-content')?.value?.trim();
    const memoryType = document.getElementById('add-memory-type')?.value || 'semantic';
    const importance = parseFloat(document.getElementById('add-memory-importance')?.value) || 0.5;
    const participantsStr = document.getElementById('add-memory-participants')?.value?.trim();
    const tagsStr = document.getElementById('add-memory-tags')?.value?.trim();

    if (!content) {
        showToast('Please enter memory content', 'error');
        return;
    }

    const participants = participantsStr ? participantsStr.split(',').map(s => s.trim()).filter(Boolean) : [];
    const tags = tagsStr ? tagsStr.split(',').map(s => s.trim()).filter(Boolean) : [];

    try {
        const resp = await fetch(`${API_BASE}/api/v1/memory/store`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                content,
                memory_type: memoryType,
                importance,
                participants,
                tags
            })
        });

        if (!resp.ok) throw new Error('Failed to store memory');

        showToast('Memory stored successfully! 🧠', 'success');

        // Clear form
        document.getElementById('add-memory-content').value = '';
        document.getElementById('add-memory-participants').value = '';
        document.getElementById('add-memory-tags').value = '';

        // Refresh stats and list
        loadMemoryStats();
        switchMemoryTab('all');
    } catch (error) {
        console.error('Error storing memory:', error);
        showToast(`Failed to store memory: ${error.message}`, 'error');
    }
}

async function deleteMemory(memoryId) {
    if (!confirm('Delete this memory?')) return;

    try {
        const resp = await fetch(`${API_BASE}/api/v1/memory/${memoryId}`, {
            method: 'DELETE'
        });

        if (!resp.ok) throw new Error('Failed to delete');

        showToast('Memory deleted', 'success');
        loadMemoryStats();
        loadMemories(memoryCurrentPage);
    } catch (error) {
        console.error('Delete error:', error);
        showToast(`Failed to delete: ${error.message}`, 'error');
    }
}

async function loadDiary() {
    const container = document.getElementById('diary-entries');
    if (!container) return;

    container.innerHTML = '<div class="loading">Loading diary...</div>';

    try {
        const resp = await fetch(`${API_BASE}/api/v1/memory/diary?days=7`);
        if (!resp.ok) throw new Error('Failed to load diary');
        const data = await resp.json();

        if (data.entries.length === 0) {
            container.innerHTML = `
                <div class="memory-empty">
                    <div class="memory-empty-icon">📖</div>
                    <h3>No diary entries yet</h3>
                    <p>Barnabee will write daily summaries as interactions happen.</p>
                    <p>Click "Generate Today's Entry" to create one using AI!</p>
                </div>
            `;
        } else {
            container.innerHTML = data.entries.map(renderDiaryEntry).join('');
        }
    } catch (error) {
        console.error('Error loading diary:', error);
        container.innerHTML = `<div class="error">Failed to load diary: ${error.message}</div>`;
    }
}

async function generateDiaryEntry() {
    const btn = document.getElementById('generate-diary-btn');
    const datePicker = document.getElementById('diary-date-picker');
    const container = document.getElementById('diary-entries');

    const date = datePicker?.value || new Date().toISOString().split('T')[0];

    // Show loading state
    const originalText = btn.textContent;
    btn.textContent = '⏳ Generating...';
    btn.disabled = true;

    try {
        const resp = await fetch(`${API_BASE}/api/v1/memory/diary/generate?date=${date}`, {
            method: 'POST'
        });

        if (!resp.ok) {
            const error = await resp.json();
            throw new Error(error.detail || 'Failed to generate diary');
        }

        const entry = await resp.json();

        // Prepend the new entry to the list
        const entryHtml = renderDiaryEntry(entry, true);
        const existingContent = container.innerHTML;

        if (existingContent.includes('memory-empty')) {
            container.innerHTML = entryHtml;
        } else {
            container.innerHTML = entryHtml + existingContent;
        }

        showToast('✨ Diary entry generated!', 'success');
    } catch (error) {
        console.error('Error generating diary:', error);
        showToast(`Failed to generate diary: ${error.message}`, 'error');
    } finally {
        btn.textContent = originalText;
        btn.disabled = false;
    }
}

function renderDiaryEntry(entry, isNew = false) {
    const date = new Date(entry.date).toLocaleDateString('en-US', {
        weekday: 'long',
        year: 'numeric',
        month: 'long',
        day: 'numeric'
    });

    const moodEmoji = {
        'positive': '😊',
        'neutral': '😐',
        'concerned': '😟'
    };

    const moodBadge = entry.mood ? `<span class="mood-badge ${entry.mood}">${moodEmoji[entry.mood] || '📝'} ${entry.mood}</span>` : '';
    const newBadge = isNew ? '<span class="new-badge">✨ New</span>' : '';

    const highlights = (entry.highlights || []).map(h =>
        `<li>${escapeHtml(h)}</li>`
    ).join('');

    const highlightsSection = highlights ? `
        <div class="diary-highlights">
            <strong>Notable moments:</strong>
            <ul>${highlights}</ul>
        </div>
    ` : '';

    const participants = (entry.participants_mentioned || []).join(', ');
    const participantsSection = participants ? `
        <div class="diary-participants">
            <strong>People involved:</strong> ${escapeHtml(participants)}
        </div>
    ` : '';

    return `
        <div class="diary-entry ${isNew ? 'new-entry' : ''}">
            <div class="diary-entry-header">
                <span class="diary-date">📅 ${date}</span>
                <div class="diary-badges">
                    ${newBadge}
                    ${moodBadge}
                    <span class="diary-summary-badge">${entry.memory_count || 0} memories</span>
                </div>
            </div>
            <div class="diary-content">
                ${entry.summary || '<em>No summary available</em>'}
            </div>
            ${highlightsSection}
            ${participantsSection}
        </div>
    `;
}

// Escape HTML helper (if not already defined)
function escapeHtml(text) {
    if (!text) return '';
    const div = document.createElement('div');
    div.textContent = text;
    return div.innerHTML;
}

// Hook into page navigation to initialize memory when shown
const origShowPage = window.showPage || showPage;
window.showPage = function (pageId) {
    origShowPage(pageId);
    if (pageId === 'memory') {
        initMemory();
    }
    if (pageId === 'family') {
        initFamily();
    }
};

// =============================================================================
// Family Profiles Page
// =============================================================================

let familyInitialized = false;
let currentProfileId = null;
let currentDiffMemberId = null;

function initFamily() {
    if (familyInitialized) {
        loadFamilyData();
        return;
    }

    // Tab navigation
    document.querySelectorAll('.family-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabId = tab.dataset.familyTab;
            switchFamilyTab(tabId);
        });
    });

    // Add member form
    const addForm = document.getElementById('add-member-form');
    if (addForm) {
        addForm.addEventListener('submit', handleAddMember);
    }

    // Profile modal close
    const profileModal = document.getElementById('profile-modal');
    if (profileModal) {
        profileModal.querySelector('.close-modal').addEventListener('click', () => {
            profileModal.classList.remove('active');
        });
        profileModal.addEventListener('click', (e) => {
            if (e.target === profileModal) {
                profileModal.classList.remove('active');
            }
        });
    }

    // Diff modal handlers
    const diffModal = document.getElementById('diff-modal');
    if (diffModal) {
        diffModal.querySelector('.close-modal').addEventListener('click', () => {
            diffModal.classList.remove('active');
        });
        diffModal.addEventListener('click', (e) => {
            if (e.target === diffModal) {
                diffModal.classList.remove('active');
            }
        });

        document.getElementById('diff-approve-btn').addEventListener('click', approvePendingUpdate);
        document.getElementById('diff-reject-btn').addEventListener('click', rejectPendingUpdate);
    }

    familyInitialized = true;
    loadFamilyData();
}

function switchFamilyTab(tabId) {
    document.querySelectorAll('.family-tab').forEach(tab => {
        tab.classList.toggle('active', tab.dataset.familyTab === tabId);
    });

    document.querySelectorAll('.family-tab-content').forEach(content => {
        content.classList.toggle('active', content.id === `family-tab-${tabId}`);
    });

    if (tabId === 'pending') {
        loadPendingUpdates();
    }
}

async function loadFamilyData() {
    try {
        // Load stats
        const statsResp = await fetch(`${API_BASE}/api/v1/profiles/stats`);
        if (statsResp.ok) {
            const stats = await statsResp.json();
            document.getElementById('family-total').textContent = stats.total_profiles || 0;
            document.getElementById('family-pending').textContent = stats.pending_updates || 0;
            document.getElementById('family-events').textContent = stats.total_events_unprocessed || 0;
        }

        // Load profiles
        const profilesResp = await fetch(`${API_BASE}/api/v1/profiles`);
        if (profilesResp.ok) {
            const data = await profilesResp.json();
            renderFamilyGrid(data.profiles);
        } else {
            document.getElementById('family-list').innerHTML = renderNoProfiles();
        }
    } catch (error) {
        console.error('Error loading family data:', error);
        document.getElementById('family-list').innerHTML = `
            <div class="error-message">
                <p>Failed to load family profiles. Make sure the API is running.</p>
                <small>${error.message}</small>
            </div>
        `;
    }
}

function renderFamilyGrid(profiles) {
    const grid = document.getElementById('family-list');

    if (!profiles || profiles.length === 0) {
        grid.innerHTML = renderNoProfiles();
        return;
    }

    grid.innerHTML = profiles.map(profile => renderFamilyCard(profile)).join('');

    // Add click handlers
    grid.querySelectorAll('.family-card').forEach(card => {
        card.addEventListener('click', () => {
            const memberId = card.dataset.memberId;
            if (memberId) {
                showProfileDetails(memberId);
            }
        });
    });
}

function renderFamilyCard(profile) {
    const avatar = getAvatarForRelationship(profile.relationship_to_primary);
    const hasPending = profile.pending_update !== null;

    const interests = profile.public?.interests || [];
    const tagsHtml = interests.slice(0, 3).map(i =>
        `<span class="pref-tag">${escapeHtml(i)}</span>`
    ).join('');

    return `
        <div class="card family-card" data-member-id="${escapeHtml(profile.member_id)}">
            ${hasPending ? '<div class="pending-indicator" title="Pending update"></div>' : ''}
            <div class="family-avatar">${avatar}</div>
            <span class="profile-badge">${escapeHtml(profile.relationship_to_primary)}</span>
            <h4>${escapeHtml(profile.name)}</h4>
            <div class="family-prefs">${tagsHtml || '<span class="pref-tag">No interests set</span>'}</div>
            <div class="profile-version">v${profile.version}</div>
        </div>
    `;
}

function renderNoProfiles() {
    return `
        <div class="no-profiles">
            <div class="no-profiles-icon">👨‍👩‍👧‍👦</div>
            <h3>No Family Profiles Yet</h3>
            <p>Create your first family member profile to get started with personalized interactions.</p>
        </div>
    `;
}

function getAvatarForRelationship(relationship) {
    const avatars = {
        'self': '👤',
        'spouse': '💑',
        'child': '👧',
        'parent': '👴',
        'sibling': '👫',
        'extended_family': '👪',
        'guest': '🧑‍🤝‍🧑'
    };
    return avatars[relationship] || '👤';
}

async function showProfileDetails(memberId) {
    currentProfileId = memberId;
    const modal = document.getElementById('profile-modal');
    const body = document.getElementById('profile-modal-body');

    body.innerHTML = '<div class="loading">Loading profile...</div>';
    modal.classList.add('active');

    try {
        const resp = await fetch(`${API_BASE}/api/v1/profiles/${memberId}`);
        if (!resp.ok) throw new Error('Failed to load profile');

        const data = await resp.json();
        const profile = data.profile;

        document.getElementById('profile-modal-title').textContent = `${profile.name}'s Profile`;

        body.innerHTML = renderProfileDetails(profile, data.has_pending_update);
    } catch (error) {
        body.innerHTML = `<div class="error-message">Error: ${error.message}</div>`;
    }
}

function renderProfileDetails(profile, hasPending) {
    const pub = profile.public || {};
    const priv = profile.private || {};

    let html = `
        <div class="profile-section">
            <h4>Identity</h4>
            <div class="profile-field">
                <span class="profile-field-label">Member ID:</span>
                <span class="profile-field-value">${escapeHtml(profile.member_id)}</span>
            </div>
            <div class="profile-field">
                <span class="profile-field-label">Relationship:</span>
                <span class="profile-field-value">${escapeHtml(profile.relationship_to_primary)}</span>
            </div>
            <div class="profile-field">
                <span class="profile-field-label">Version:</span>
                <span class="profile-field-value">${profile.version}</span>
            </div>
            <div class="profile-field">
                <span class="profile-field-label">Last Updated:</span>
                <span class="profile-field-value">${new Date(profile.last_updated).toLocaleString()}</span>
            </div>
        </div>
    `;

    // Public block
    html += `
        <div class="profile-section">
            <h4>🌐 Public Information</h4>
            <div class="profile-block">
                <div class="profile-block-title public">Shared with all family members</div>
                ${pub.schedule_summary ? `
                    <div class="profile-field">
                        <span class="profile-field-label">Schedule:</span>
                        <span class="profile-field-value">${escapeHtml(pub.schedule_summary)}</span>
                    </div>
                ` : ''}
                ${pub.communication_style ? `
                    <div class="profile-field">
                        <span class="profile-field-label">Communication:</span>
                        <span class="profile-field-value">${escapeHtml(pub.communication_style)}</span>
                    </div>
                ` : ''}
                ${(pub.interests || []).length > 0 ? `
                    <div class="profile-field">
                        <span class="profile-field-label">Interests:</span>
                        <span class="profile-field-value">
                            <div class="profile-tags">
                                ${pub.interests.map(i => `<span class="profile-tag">${escapeHtml(i)}</span>`).join('')}
                            </div>
                        </span>
                    </div>
                ` : ''}
                ${(pub.household_responsibilities || []).length > 0 ? `
                    <div class="profile-field">
                        <span class="profile-field-label">Responsibilities:</span>
                        <span class="profile-field-value">
                            <div class="profile-tags">
                                ${pub.household_responsibilities.map(r => `<span class="profile-tag">${escapeHtml(r)}</span>`).join('')}
                            </div>
                        </span>
                    </div>
                ` : ''}
            </div>
        </div>
    `;

    // Private block
    html += `
        <div class="profile-section">
            <h4>🔒 Private Information</h4>
            <div class="profile-block">
                <div class="profile-block-title private">Only used in direct interactions</div>
                ${priv.emotional_patterns ? `
                    <div class="profile-field">
                        <span class="profile-field-label">Patterns:</span>
                        <span class="profile-field-value">${escapeHtml(priv.emotional_patterns)}</span>
                    </div>
                ` : ''}
                ${priv.relationship_notes ? `
                    <div class="profile-field">
                        <span class="profile-field-label">Notes:</span>
                        <span class="profile-field-value">${escapeHtml(priv.relationship_notes)}</span>
                    </div>
                ` : ''}
                ${(priv.sensitive_topics || []).length > 0 ? `
                    <div class="profile-field">
                        <span class="profile-field-label">Sensitive Topics:</span>
                        <span class="profile-field-value">
                            <div class="profile-tags">
                                ${priv.sensitive_topics.map(t => `<span class="profile-tag">${escapeHtml(t)}</span>`).join('')}
                            </div>
                        </span>
                    </div>
                ` : ''}
                ${priv.wellness_notes ? `
                    <div class="profile-field">
                        <span class="profile-field-label">Wellness:</span>
                        <span class="profile-field-value">${escapeHtml(priv.wellness_notes)}</span>
                    </div>
                ` : ''}
            </div>
        </div>
    `;

    // Actions
    html += `
        <div class="profile-section">
            <div class="profile-actions" style="display: flex; gap: 8px;">
                <button class="btn btn-primary" onclick="generateProfileUpdate('${escapeHtml(profile.member_id)}')">
                    🔄 Generate Update
                </button>
                ${hasPending ? `
                    <button class="btn btn-warning" onclick="showPendingDiff('${escapeHtml(profile.member_id)}')">
                        ⏳ View Pending Update
                    </button>
                ` : ''}
                <button class="btn btn-danger" onclick="deleteProfile('${escapeHtml(profile.member_id)}')">
                    🗑️ Delete Profile
                </button>
            </div>
        </div>
    `;

    return html;
}

async function handleAddMember(e) {
    e.preventDefault();

    const memberId = document.getElementById('new-member-id').value.trim().toLowerCase();
    const name = document.getElementById('new-member-name').value.trim();
    const relationship = document.getElementById('new-member-relationship').value;

    try {
        const resp = await fetch(`${API_BASE}/api/v1/profiles`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                member_id: memberId,
                name: name,
                relationship: relationship
            })
        });

        if (!resp.ok) {
            const error = await resp.json();
            throw new Error(error.detail || 'Failed to create profile');
        }

        // Reset form and switch to members tab
        e.target.reset();
        switchFamilyTab('members');
        loadFamilyData();
        showToast('Profile created successfully!', 'success');
    } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
    }
}

async function generateProfileUpdate(memberId) {
    try {
        showToast('Generating profile update...', 'info');

        const resp = await fetch(`${API_BASE}/api/v1/profiles/${memberId}/generate-update`, {
            method: 'POST'
        });

        if (!resp.ok) {
            const error = await resp.json();
            throw new Error(error.detail || 'Failed to generate update');
        }

        const diff = await resp.json();
        showDiffModal(diff);
        showToast('Profile update generated!', 'success');
    } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
    }
}

async function showPendingDiff(memberId) {
    try {
        const resp = await fetch(`${API_BASE}/api/v1/profiles/${memberId}/pending-update`);
        if (!resp.ok) throw new Error('No pending update found');

        const diff = await resp.json();
        showDiffModal(diff);
    } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
    }
}

function showDiffModal(diff) {
    currentDiffMemberId = diff.member_id;
    const modal = document.getElementById('diff-modal');
    const body = document.getElementById('diff-modal-body');

    document.getElementById('diff-modal-title').textContent = `Update Preview: ${diff.name}`;

    body.innerHTML = renderDiffPreview(diff);
    modal.classList.add('active');
}

function renderDiffPreview(diff) {
    let html = `
        <div class="diff-summary">
            <strong>Summary:</strong> ${escapeHtml(diff.summary)}
            ${diff.confidence_notes ? `<br><em>Note: ${escapeHtml(diff.confidence_notes)}</em>` : ''}
        </div>
    `;

    if (diff.additions && diff.additions.length > 0) {
        html += `
            <div class="diff-section">
                <h4 class="additions">➕ Additions (${diff.additions.length})</h4>
                ${diff.additions.map(e => renderDiffEntry(e, 'addition')).join('')}
            </div>
        `;
    }

    if (diff.modifications && diff.modifications.length > 0) {
        html += `
            <div class="diff-section">
                <h4 class="modifications">✏️ Modifications (${diff.modifications.length})</h4>
                ${diff.modifications.map(e => renderDiffEntry(e, 'modification')).join('')}
            </div>
        `;
    }

    if (diff.removals && diff.removals.length > 0) {
        html += `
            <div class="diff-section">
                <h4 class="removals">➖ Removals (${diff.removals.length})</h4>
                ${diff.removals.map(e => renderDiffEntry(e, 'removal')).join('')}
            </div>
        `;
    }

    if (!diff.additions?.length && !diff.modifications?.length && !diff.removals?.length) {
        html += '<p class="text-muted">No changes detected.</p>';
    }

    return html;
}

function renderDiffEntry(entry, type) {
    const oldVal = entry.old ? JSON.stringify(entry.old) : '-';
    const newVal = entry.new ? JSON.stringify(entry.new) : '-';

    return `
        <div class="diff-entry">
            <div class="diff-entry-header">
                <span class="diff-entry-field">${escapeHtml(entry.field)}</span>
                <span class="diff-entry-block">${entry.block_display || entry.block}</span>
            </div>
            ${type === 'modification' || type === 'removal' ? `
                <div><span class="diff-old-value">${escapeHtml(oldVal)}</span></div>
            ` : ''}
            ${type === 'modification' || type === 'addition' ? `
                <div><span class="diff-new-value">${escapeHtml(newVal)}</span></div>
            ` : ''}
            ${entry.reason ? `<div class="diff-reason">${escapeHtml(entry.reason)}</div>` : ''}
        </div>
    `;
}

async function approvePendingUpdate() {
    if (!currentDiffMemberId) return;

    try {
        const resp = await fetch(`${API_BASE}/api/v1/profiles/${currentDiffMemberId}/approve-update`, {
            method: 'POST'
        });

        if (!resp.ok) {
            const error = await resp.json();
            throw new Error(error.detail || 'Failed to approve update');
        }

        document.getElementById('diff-modal').classList.remove('active');
        document.getElementById('profile-modal').classList.remove('active');
        loadFamilyData();
        showToast('Profile update approved!', 'success');
    } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
    }
}

async function rejectPendingUpdate() {
    if (!currentDiffMemberId) return;

    const reason = prompt('Reason for rejection (optional):');

    try {
        let url = `${API_BASE}/api/v1/profiles/${currentDiffMemberId}/reject-update`;
        if (reason) {
            url += `?reason=${encodeURIComponent(reason)}`;
        }

        const resp = await fetch(url, { method: 'POST' });

        if (!resp.ok) {
            const error = await resp.json();
            throw new Error(error.detail || 'Failed to reject update');
        }

        document.getElementById('diff-modal').classList.remove('active');
        loadFamilyData();
        showToast('Profile update rejected', 'info');
    } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
    }
}

async function deleteProfile(memberId) {
    if (!confirm(`Are you sure you want to delete the profile for "${memberId}"? This cannot be undone.`)) {
        return;
    }

    try {
        const resp = await fetch(`${API_BASE}/api/v1/profiles/${memberId}`, {
            method: 'DELETE'
        });

        if (!resp.ok) {
            const error = await resp.json();
            throw new Error(error.detail || 'Failed to delete profile');
        }

        document.getElementById('profile-modal').classList.remove('active');
        loadFamilyData();
        showToast('Profile deleted', 'success');
    } catch (error) {
        showToast(`Error: ${error.message}`, 'error');
    }
}

async function loadPendingUpdates() {
    const container = document.getElementById('pending-updates-list');
    container.innerHTML = '<div class="loading">Loading pending updates...</div>';

    try {
        const resp = await fetch(`${API_BASE}/api/v1/profiles/pending-updates`);
        if (!resp.ok) throw new Error('Failed to load pending updates');

        const data = await resp.json();

        if (data.pending_updates.length === 0) {
            container.innerHTML = `
                <div class="no-profiles">
                    <div class="no-profiles-icon">✓</div>
                    <h3>No Pending Updates</h3>
                    <p>All profiles are up to date.</p>
                </div>
            `;
            return;
        }

        container.innerHTML = data.pending_updates.map(item => `
            <div class="pending-update-item">
                <div class="pending-update-info">
                    <div class="pending-update-avatar">${getAvatarForRelationship('self')}</div>
                    <div class="pending-update-details">
                        <h4>${escapeHtml(item.name)}</h4>
                        <p>Version ${item.current_version} • ${item.trigger_count} triggers • ${item.generated_at ? new Date(item.generated_at).toLocaleString() : 'Unknown'}</p>
                    </div>
                </div>
                <div class="pending-update-actions">
                    <button class="btn btn-primary btn-sm" onclick="showPendingDiff('${escapeHtml(item.member_id)}')">
                        Review
                    </button>
                </div>
            </div>
        `).join('');
    } catch (error) {
        container.innerHTML = `<div class="error-message">Error: ${error.message}</div>`;
    }
}

// Toast notification helper (ensure it exists)
function showToast(message, type = 'info') {
    const existing = document.querySelector('.toast');
    if (existing) existing.remove();

    const toast = document.createElement('div');
    toast.className = `toast toast-${type}`;
    toast.textContent = message;
    document.body.appendChild(toast);

    setTimeout(() => toast.classList.add('show'), 10);
    setTimeout(() => {
        toast.classList.remove('show');
        setTimeout(() => toast.remove(), 300);
    }, 3000);
}

// =============================================================================
// Logic Browser Page
// =============================================================================

let logicData = {
    patterns: {},
    routing: {},
    overrides: {},
    aliases: []
};
let currentEditPattern = null;

function initLogicPage() {
    // Tab switching
    document.querySelectorAll('.logic-tab').forEach(tab => {
        tab.addEventListener('click', () => {
            const tabName = tab.dataset.tab;

            // Update active tab
            document.querySelectorAll('.logic-tab').forEach(t => t.classList.remove('active'));
            tab.classList.add('active');

            // Show corresponding content
            document.querySelectorAll('.logic-tab-content').forEach(c => c.classList.remove('active'));
            document.getElementById(`logic-tab-${tabName}`).classList.add('active');
        });
    });

    // Pattern group filter
    const groupFilter = document.getElementById('pattern-group-filter');
    if (groupFilter) {
        groupFilter.addEventListener('change', () => renderPatternGroups());
    }

    // Show disabled toggle
    const showDisabled = document.getElementById('show-disabled-patterns');
    if (showDisabled) {
        showDisabled.addEventListener('change', () => renderPatternGroups());
    }

    // Refresh button
    const refreshBtn = document.getElementById('patterns-refresh-btn');
    if (refreshBtn) {
        refreshBtn.addEventListener('click', loadLogicData);
    }

    // Pattern test button
    const testBtn = document.getElementById('run-pattern-test');
    if (testBtn) {
        testBtn.addEventListener('click', runPatternTest);
    }

    // Pattern test on enter key
    const testInput = document.getElementById('pattern-test-input');
    if (testInput) {
        testInput.addEventListener('keypress', (e) => {
            if (e.key === 'Enter') runPatternTest();
        });
    }

    // Save pattern button
    const saveBtn = document.getElementById('save-pattern-btn');
    if (saveBtn) {
        saveBtn.addEventListener('click', savePatternEdit);
    }

    // Modal close buttons
    document.querySelectorAll('#pattern-modal .modal-close-btn').forEach(btn => {
        btn.addEventListener('click', closePatternModal);
    });

    // Close modal on outside click
    const modal = document.getElementById('pattern-modal');
    if (modal) {
        modal.addEventListener('click', (e) => {
            if (e.target === modal) closePatternModal();
        });
    }

    // History refresh button
    const historyRefreshBtn = document.getElementById('history-refresh-btn');
    if (historyRefreshBtn) {
        historyRefreshBtn.addEventListener('click', loadDecisionHistory);
    }

    // History filter change handlers
    const agentFilter = document.getElementById('history-agent-filter');
    const statusFilter = document.getElementById('history-status-filter');
    const searchInput = document.getElementById('history-search');

    if (agentFilter) {
        agentFilter.addEventListener('change', renderDecisionHistory);
    }
    if (statusFilter) {
        statusFilter.addEventListener('change', renderDecisionHistory);
    }
    if (searchInput) {
        // Debounce search input
        let searchTimeout;
        searchInput.addEventListener('input', () => {
            clearTimeout(searchTimeout);
            searchTimeout = setTimeout(renderDecisionHistory, 300);
        });
    }

    // Load initial data
    loadLogicData();
}

async function loadLogicData() {
    try {
        // Use the main logic endpoint which returns everything in one call
        const response = await fetch('/api/v1/logic/');

        if (!response.ok) {
            throw new Error(`HTTP ${response.status}`);
        }

        const data = await response.json();

        // Store the data - structure is: patterns, routing, overrides, entity_aliases, stats, metadata
        logicData.patterns = data.patterns || {};
        logicData.routing = data.routing || {};
        logicData.overrides = data.overrides || {};
        logicData.aliases = data.entity_aliases || {};
        logicData.stats = data.stats || {};

        updateLogicStats();
        renderPatternGroups();
        renderRoutingRules();
        renderOverrides();
        renderAliases();

        // Also load decision history
        loadDecisionHistory();
    } catch (error) {
        console.error('Failed to load logic data:', error);
        showToast('Failed to load logic data', 'error');
    }
}

// Decision history for Logic Browser - uses dashboard traces which have the actual request data
let decisionHistory = [];

async function loadDecisionHistory() {
    try {
        // Use dashboard traces endpoint which captures all requests
        const [tracesResponse, statsResponse] = await Promise.all([
            fetch('/api/v1/dashboard/traces?limit=50'),
            fetch('/api/v1/dashboard/stats')
        ]);

        if (!tracesResponse.ok || !statsResponse.ok) {
            throw new Error(`HTTP error`);
        }

        const tracesData = await tracesResponse.json();
        const statsData = await statsResponse.json();

        decisionHistory = tracesData.traces || [];

        renderDecisionStats(statsData);
        renderDecisionHistory();
    } catch (error) {
        console.error('Failed to load decision history:', error);
        const container = document.getElementById('history-list');
        if (container) {
            container.innerHTML = '<div class="text-muted">Failed to load decision history. Try sending some requests to BarnabeeNet first.</div>';
        }
    }
}

function renderDecisionStats(stats) {
    const container = document.getElementById('history-stats');
    if (!container) return;

    container.innerHTML = `
        <div class="history-stats-grid">
            <div class="stat-mini">
                <span class="stat-value-small">${stats.total_requests_24h || 0}</span>
                <span class="stat-label-small">Requests (24h)</span>
            </div>
            <div class="stat-mini">
                <span class="stat-value-small">${stats.avg_latency_ms ? stats.avg_latency_ms.toFixed(0) : 0}ms</span>
                <span class="stat-label-small">Avg Latency</span>
            </div>
            <div class="stat-mini">
                <span class="stat-value-small">${(stats.error_rate_percent || 0).toFixed(1)}%</span>
                <span class="stat-label-small">Error Rate</span>
            </div>
            <div class="stat-mini">
                <span class="stat-value-small">$${(stats.total_cost_24h || 0).toFixed(4)}</span>
                <span class="stat-label-small">LLM Cost (24h)</span>
            </div>
        </div>
    `;
}

function renderDecisionHistory() {
    const container = document.getElementById('history-list');
    if (!container) return;

    if (!decisionHistory || decisionHistory.length === 0) {
        container.innerHTML = '<div class="text-muted">No request history yet. Try sending some requests to BarnabeeNet!</div>';
        return;
    }

    // Get filter values
    const agentFilter = document.getElementById('history-agent-filter')?.value || '';
    const statusFilter = document.getElementById('history-status-filter')?.value || '';
    const searchTerm = document.getElementById('history-search')?.value?.toLowerCase() || '';

    // Apply filters
    let filteredHistory = decisionHistory.filter(trace => {
        // Agent filter
        if (agentFilter && trace.agent_used !== agentFilter) return false;

        // Status filter
        if (statusFilter === 'success' && !trace.success) return false;
        if (statusFilter === 'error' && trace.success) return false;

        // Search filter
        if (searchTerm) {
            const inputText = (trace.input_preview || '').toLowerCase();
            const responseText = (trace.response_preview || '').toLowerCase();
            if (!inputText.includes(searchTerm) && !responseText.includes(searchTerm)) return false;
        }

        return true;
    });

    const agentIcons = {
        instant: '⚡',
        action: '🎯',
        memory: '📝',
        interaction: '💬',
        emergency: '🚨'
    };

    if (filteredHistory.length === 0) {
        container.innerHTML = `<div class="text-muted">No matching requests found. ${decisionHistory.length} total requests available.</div>`;
        return;
    }

    let html = `<div class="filter-results-count">${filteredHistory.length} of ${decisionHistory.length} requests</div>`;
    filteredHistory.forEach(trace => {
        const icon = agentIcons[trace.agent_used] || '❓';
        const time = trace.timestamp ? new Date(trace.timestamp).toLocaleTimeString() : '';
        const duration = trace.total_latency_ms ? `${trace.total_latency_ms.toFixed(1)}ms` : '';
        const successClass = trace.success ? 'success' : 'error';
        const successColor = trace.success ? 'var(--success)' : 'var(--danger)';

        // Determine which pattern was matched based on agent and intent
        let logicInfo = '';
        if (trace.intent) {
            logicInfo = `Intent: ${trace.intent}`;
        } else if (trace.agent_used) {
            logicInfo = `Routed to: ${trace.agent_used} agent`;
        }

        html += `
            <div class="decision-card clickable" onclick="openTraceDetail('${trace.trace_id}')">
                <div class="decision-header">
                    <span class="decision-icon">${icon}</span>
                    <span class="decision-name">${trace.agent_used || 'unknown'} agent</span>
                    <span class="decision-component">${escapeHtml(trace.intent || '')}</span>
                    <span class="decision-time">${time}</span>
                </div>
                <div class="decision-body">
                    <div class="decision-input"><strong>Input:</strong> "${escapeHtml(trace.input_preview || '')}"</div>
                    <div class="decision-result">
                        <span class="decision-outcome" style="color: ${successColor}">
                            ${trace.success ? 'SUCCESS' : 'ERROR'}
                        </span>
                    </div>
                    <div class="decision-response"><strong>Response:</strong> "${escapeHtml(trace.response_preview || '')}"</div>
                    ${logicInfo ? `<div class="decision-logic">${escapeHtml(logicInfo)}</div>` : ''}
                </div>
                <div class="decision-footer">
                    ${duration ? `<span class="decision-duration">${duration}</span>` : ''}
                    <span class="decision-id" title="${trace.trace_id}">${trace.trace_id?.substring(0, 12) || ''}...</span>
                    <span class="click-hint">Click for details →</span>
                </div>
            </div>
        `;
    });

    container.innerHTML = html;
}

// Open trace detail modal - exposed globally for onclick handlers
window.openTraceDetail = async function (traceId) {
    const modal = document.getElementById('trace-modal');
    const body = document.getElementById('trace-modal-body');

    modal.style.display = 'flex';
    body.innerHTML = '<div class="loading-skeleton"><div class="skeleton-card"></div></div>';

    try {
        const response = await fetch(`/api/v1/dashboard/traces/${traceId}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const trace = await response.json();
        body.innerHTML = renderTraceDetail(trace);
    } catch (error) {
        console.error('Failed to load trace details:', error);
        body.innerHTML = `<div class="error-message">Failed to load trace details: ${error.message}</div>`;
    }
}

function renderTraceDetail(trace) {
    const agentIcons = {
        instant: '⚡',
        action: '🎯',
        memory: '📝',
        interaction: '💬',
        emergency: '🚨'
    };

    const icon = agentIcons[trace.agent_used] || '❓';
    const startTime = trace.started_at ? new Date(trace.started_at).toLocaleString() : 'N/A';
    const endTime = trace.completed_at ? new Date(trace.completed_at).toLocaleString() : 'N/A';
    const successColor = trace.success ? 'var(--success)' : 'var(--danger)';

    // Build waterfall timeline from signals
    const waterfallHtml = renderWaterfallTimeline(trace);

    let html = `
        <div class="trace-detail">
            <!-- Header Summary -->
            <div class="trace-detail-header">
                <div class="trace-status-badge" style="background: ${successColor}20; color: ${successColor}; border: 1px solid ${successColor}">
                    ${trace.success ? '✓ SUCCESS' : '✗ ERROR'}
                </div>
                <div class="trace-agent-badge">
                    <span>${icon}</span> ${trace.agent_used || 'unknown'} agent
                </div>
                <div class="trace-timing">
                    <strong>${trace.total_latency_ms?.toFixed(2) || 0}ms</strong> total
                </div>
                <button class="btn btn-danger btn-sm mark-wrong-btn" onclick="window.openCorrectionModal('${trace.trace_id}')">
                    🔴 Mark as Wrong
                </button>
            </div>

            <!-- Waterfall Timeline -->
            ${waterfallHtml}

            <!-- Input/Output Section -->
            <div class="trace-section">
                <h4>📥 Input</h4>
                <div class="trace-code-block">
                    <div class="trace-field"><span class="label">Text:</span> "${escapeHtml(trace.input_text || '')}"</div>
                    <div class="trace-field"><span class="label">Type:</span> ${trace.input_type || 'text'}</div>
                    ${trace.speaker ? `<div class="trace-field"><span class="label">Speaker:</span> ${escapeHtml(trace.speaker)}</div>` : ''}
                    ${trace.room ? `<div class="trace-field"><span class="label">Room:</span> ${escapeHtml(trace.room)}</div>` : ''}
                </div>
            </div>

            <div class="trace-section">
                <h4>📤 Output</h4>
                <div class="trace-code-block">
                    <div class="trace-field"><span class="label">Response:</span> "${escapeHtml(trace.response_text || '')}"</div>
                    <div class="trace-field"><span class="label">Type:</span> ${trace.response_type || 'spoken'}</div>
                    ${trace.error ? `<div class="trace-field error"><span class="label">Error:</span> ${escapeHtml(trace.error)}</div>` : ''}
                </div>
            </div>

            <!-- Classification & Routing -->
            <div class="trace-section">
                <h4>🧠 Classification & Routing</h4>
                <div class="trace-code-block">
                    <div class="trace-field"><span class="label">Intent:</span> <strong>${trace.intent || 'unknown'}</strong></div>
                    ${trace.intent_confidence ? `<div class="trace-field"><span class="label">Confidence:</span> ${(trace.intent_confidence * 100).toFixed(0)}%</div>` : ''}
                    <div class="trace-field"><span class="label">Agent:</span> <strong>${trace.agent_used || 'unknown'}</strong></div>
                    ${trace.route_reason ? `<div class="trace-field"><span class="label">Routing Reason:</span> ${escapeHtml(trace.route_reason)}</div>` : ''}
                    ${trace.context_type ? `<div class="trace-field"><span class="label">Context:</span> ${trace.context_type}</div>` : ''}
                    ${trace.mood ? `<div class="trace-field"><span class="label">Mood:</span> ${trace.mood}</div>` : ''}
                </div>
            </div>

            <!-- Memory Operations -->
            ${trace.memories_retrieved?.length > 0 ? `
            <div class="trace-section">
                <h4>🧠 Memories Retrieved</h4>
                <div class="trace-code-block">
                    ${trace.memories_retrieved.map(m => `<div class="trace-memory-item">${escapeHtml(typeof m === 'string' ? m : JSON.stringify(m))}</div>`).join('')}
                </div>
            </div>
            ` : ''}

            <!-- Home Assistant Actions -->
            ${trace.ha_actions?.length > 0 ? `
            <div class="trace-section">
                <h4>🏠 Home Assistant Actions</h4>
                <div class="trace-code-block">
                    ${trace.ha_actions.map(a => `
                        <div class="trace-action-item">
                            <strong>${a.service || a.action_type || 'action'}</strong>
                            ${a.entity_id ? ` → ${a.entity_id}` : ''}
                            ${a.executed !== undefined ? `<span class="${a.executed ? 'success' : 'error'}">[${a.executed ? 'executed' : 'failed'}]</span>` : ''}
                        </div>
                    `).join('')}
                </div>
            </div>
            ` : ''}

            <!-- LLM Details -->
            ${trace.total_tokens > 0 || trace.total_cost_usd > 0 ? `
            <div class="trace-section">
                <h4>🤖 LLM Usage</h4>
                <div class="trace-code-block">
                    <div class="trace-field"><span class="label">Total Tokens:</span> ${trace.total_tokens}</div>
                    <div class="trace-field"><span class="label">Total Cost:</span> $${trace.total_cost_usd?.toFixed(6) || '0'}</div>
                </div>
            </div>
            ` : ''}

            <!-- Timing -->
            <div class="trace-section">
                <h4>⏱️ Timing</h4>
                <div class="trace-code-block">
                    <div class="trace-field"><span class="label">Started:</span> ${startTime}</div>
                    <div class="trace-field"><span class="label">Completed:</span> ${endTime}</div>
                    <div class="trace-field"><span class="label">Total Latency:</span> <strong>${trace.total_latency_ms?.toFixed(2) || 0}ms</strong></div>
                </div>
            </div>

            <!-- Pipeline Signals -->
            ${trace.signals?.length > 0 ? `
            <div class="trace-section">
                <h4>📊 Pipeline Signals (${trace.signals.length})</h4>
                <div class="trace-signals-list">
                    ${trace.signals.map((sig, idx) => renderSignalItem(sig, idx)).join('')}
                </div>
            </div>
            ` : ''}

            <!-- Raw Data (collapsible) -->
            <div class="trace-section">
                <h4 class="collapsible" onclick="toggleTraceRaw(this)">📋 Raw JSON Data <span class="toggle-icon">▶</span></h4>
                <div class="trace-raw-json" style="display: none;">
                    <pre>${escapeHtml(JSON.stringify(trace, null, 2))}</pre>
                </div>
            </div>

            <!-- Trace ID -->
            <div class="trace-section trace-id-section">
                <span class="label">Trace ID:</span>
                <code>${trace.trace_id}</code>
            </div>
        </div>
    `;

    return html;
}

function renderSignalItem(signal, index) {
    const typeIcons = {
        request_start: '▶️',
        request_complete: '✅',
        meta_classify: '🧠',
        agent_route: '🚦',
        llm_request: '📤',
        llm_response: '📥',
        ha_service_call: '🏠',
        ha_action: '🏠',
        memory_query: '🔍',
        memory_store: '💾',
        memory_retrieve: '📖',
        error: '❌',
        agent_instant: '⚡',
        agent_action: '🎯',
        agent_interaction: '💬',
        agent_memory: '📝'
    };

    const icon = typeIcons[signal.signal_type] || '📌';
    const time = signal.timestamp ? new Date(signal.timestamp).toLocaleTimeString() : '';
    const latency = signal.latency_ms ? `${signal.latency_ms.toFixed(2)}ms` : '';
    const successClass = signal.success ? '' : 'error';

    let details = [];
    if (signal.model_used) details.push(`Model: ${signal.model_used}`);
    if (signal.tokens_in) details.push(`In: ${signal.tokens_in} tokens`);
    if (signal.tokens_out) details.push(`Out: ${signal.tokens_out} tokens`);
    if (signal.cost_usd) details.push(`Cost: $${signal.cost_usd.toFixed(6)}`);
    if (signal.error) details.push(`Error: ${signal.error}`);

    return `
        <div class="trace-signal-item ${successClass}">
            <div class="signal-header">
                <span class="signal-index">#${index + 1}</span>
                <span class="signal-icon">${icon}</span>
                <span class="signal-type">${signal.signal_type}</span>
                <span class="signal-component">${signal.component}</span>
                <span class="signal-time">${time}</span>
                ${latency ? `<span class="signal-latency">${latency}</span>` : ''}
            </div>
            ${signal.summary ? `<div class="signal-summary">${escapeHtml(signal.summary)}</div>` : ''}
            ${details.length > 0 ? `<div class="signal-details">${details.join(' • ')}</div>` : ''}
            ${Object.keys(signal.input_data || {}).length > 0 ? `
                <div class="signal-data">
                    <strong>Input:</strong> <code>${escapeHtml(JSON.stringify(signal.input_data).substring(0, 200))}${JSON.stringify(signal.input_data).length > 200 ? '...' : ''}</code>
                </div>
            ` : ''}
            ${Object.keys(signal.output_data || {}).length > 0 ? `
                <div class="signal-data">
                    <strong>Output:</strong> <code>${escapeHtml(JSON.stringify(signal.output_data).substring(0, 200))}${JSON.stringify(signal.output_data).length > 200 ? '...' : ''}</code>
                </div>
            ` : ''}
        </div>
    `;
}

/**
 * Render a waterfall timeline visualization showing the timing of each pipeline step.
 * Each signal is shown as a horizontal bar with its start offset and duration.
 */
function renderWaterfallTimeline(trace) {
    if (!trace.signals || trace.signals.length === 0) {
        return '';
    }

    // Parse timestamps and calculate relative positions
    const traceStart = trace.started_at ? new Date(trace.started_at).getTime() : null;
    const totalDuration = trace.total_latency_ms || 1;

    if (!traceStart) return '';

    // Process signals to get timing information
    const timelineItems = [];

    trace.signals.forEach(signal => {
        const signalTime = signal.timestamp ? new Date(signal.timestamp).getTime() : null;
        if (signalTime === null) return;

        // Calculate start offset from trace start
        const startOffset = signalTime - traceStart;
        const duration = signal.latency_ms || 0;

        // Determine bar type for coloring based on component
        let barType = 'default';
        if (signal.component?.includes('meta')) barType = 'meta';
        else if (signal.component?.includes('instant')) barType = 'instant';
        else if (signal.component?.includes('action')) barType = 'action';
        else if (signal.component?.includes('interaction')) barType = 'interaction';
        else if (signal.component?.includes('memory')) barType = 'memory';
        else if (signal.signal_type?.includes('llm')) barType = 'llm';
        else if (signal.signal_type?.includes('tts')) barType = 'tts';
        else if (signal.signal_type?.includes('stt')) barType = 'stt';
        else if (signal.signal_type?.includes('ha')) barType = 'action';

        const typeIcons = {
            request_start: '▶️',
            request_complete: '✅',
            meta_classify: '🧠',
            agent_route: '🚦',
            llm_request: '📤',
            llm_response: '📥',
            ha_service_call: '🏠',
            ha_action: '🏠',
            memory_query: '🔍',
            memory_store: '💾',
            memory_retrieve: '📖',
            error: '❌',
            agent_instant: '⚡',
            agent_action: '🎯',
            agent_interaction: '💬',
            agent_memory: '📝'
        };
        const icon = typeIcons[signal.signal_type] || '📌';

        // Create a concise label
        let label = signal.signal_type || 'unknown';
        if (signal.model_used) {
            // Shorten model name for display
            const shortModel = signal.model_used.split('/').pop().split(':')[0];
            label = `${icon} ${shortModel}`;
        } else if (signal.component) {
            label = `${icon} ${signal.component}`;
        } else {
            label = `${icon} ${label}`;
        }

        timelineItems.push({
            label,
            startOffset,
            duration,
            barType,
            signal
        });
    });

    // Sort by start time
    timelineItems.sort((a, b) => a.startOffset - b.startOffset);

    // Build HTML
    let html = `
        <div class="trace-section waterfall-timeline">
            <h4>📊 Waterfall Timeline</h4>
            <div class="timeline-scale">
                <span>0ms</span>
                <span>${(totalDuration / 4).toFixed(0)}ms</span>
                <span>${(totalDuration / 2).toFixed(0)}ms</span>
                <span>${(totalDuration * 3 / 4).toFixed(0)}ms</span>
                <span>${totalDuration.toFixed(0)}ms</span>
            </div>
    `;

    timelineItems.forEach(item => {
        // Calculate percentage positions
        const leftPct = Math.max(0, (item.startOffset / totalDuration) * 100);
        const widthPct = Math.max(1, (item.duration / totalDuration) * 100);

        // Format duration for display
        const durationStr = item.duration > 0 ? `${item.duration.toFixed(1)}ms` : '';

        html += `
            <div class="timeline-row">
                <div class="step-label" title="${escapeHtml(item.signal?.summary || '')}">${item.label}</div>
                <div class="timeline-bar-container">
                    <div class="timeline-bar ${item.barType}" style="left: ${leftPct}%; width: ${widthPct}%;">
                        ${durationStr && widthPct > 15 ? `<span class="bar-duration">${durationStr}</span>` : ''}
                    </div>
                    ${durationStr && widthPct <= 15 ? `<span class="step-duration" style="left: ${leftPct + widthPct + 1}%">${durationStr}</span>` : ''}
                </div>
            </div>
        `;
    });

    html += '</div>';
    return html;
}

// Toggle raw JSON display - exposed globally for onclick handlers
window.toggleTraceRaw = function (element) {
    const rawDiv = element.nextElementSibling;
    const icon = element.querySelector('.toggle-icon');
    if (rawDiv.style.display === 'none') {
        rawDiv.style.display = 'block';
        icon.textContent = '▼';
    } else {
        rawDiv.style.display = 'none';
        icon.textContent = '▶';
    }
}

// Close trace modal - exposed globally
window.closeTraceModal = function () {
    const modal = document.getElementById('trace-modal');
    if (modal) modal.style.display = 'none';
}

// Initialize trace modal close handlers
document.addEventListener('DOMContentLoaded', () => {
    const traceModal = document.getElementById('trace-modal');
    if (traceModal) {
        traceModal.addEventListener('click', (e) => {
            if (e.target === traceModal) window.closeTraceModal();
        });
        traceModal.querySelectorAll('.modal-close-btn').forEach(btn => {
            btn.addEventListener('click', window.closeTraceModal);
        });
    }

    // Initialize correction modal close handlers
    const correctionModal = document.getElementById('correction-modal');
    if (correctionModal) {
        correctionModal.addEventListener('click', (e) => {
            if (e.target === correctionModal) window.closeCorrectionModal();
        });
    }
});

// =============================================================================
// AI Correction System
// =============================================================================

let currentCorrectionTrace = null;

// Open correction modal for a trace
window.openCorrectionModal = async function (traceId) {
    const modal = document.getElementById('correction-modal');
    const preview = document.getElementById('correction-request-preview');
    const step1 = document.getElementById('correction-step-1');
    const step2 = document.getElementById('correction-step-2');

    // Reset to step 1
    step1.style.display = 'block';
    step2.style.display = 'none';
    document.getElementById('correction-expected').value = '';
    document.querySelectorAll('input[name="issue-type"]').forEach(r => r.checked = false);

    // Load trace data
    try {
        const response = await fetch(`/api/v1/dashboard/traces/${traceId}`);
        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        currentCorrectionTrace = await response.json();

        // Show request preview
        preview.innerHTML = `
            <div class="correction-preview-item">
                <span class="label">Input:</span>
                <span class="value">"${escapeHtml(currentCorrectionTrace.input_text || '')}"</span>
            </div>
            <div class="correction-preview-item">
                <span class="label">Agent:</span>
                <span class="value">${currentCorrectionTrace.agent_used || 'unknown'}</span>
            </div>
            <div class="correction-preview-item">
                <span class="label">Response:</span>
                <span class="value">"${escapeHtml(currentCorrectionTrace.response_text || '')}"</span>
            </div>
            ${currentCorrectionTrace.ha_actions?.length > 0 ? `
            <div class="correction-preview-item">
                <span class="label">Actions:</span>
                <span class="value">${currentCorrectionTrace.ha_actions.map(a => `${a.service || a.action_type} → ${a.entity_id || ''}`).join(', ')}</span>
            </div>
            ` : ''}
        `;

        modal.style.display = 'flex';
    } catch (error) {
        console.error('Failed to load trace for correction:', error);
        showToast('Failed to load request details', 'error');
    }
}

// Close correction modal
window.closeCorrectionModal = function () {
    const modal = document.getElementById('correction-modal');
    if (modal) modal.style.display = 'none';
    currentCorrectionTrace = null;
}

// Analyze correction with AI
window.analyzeCorrection = async function () {
    if (!currentCorrectionTrace) {
        showToast('No trace selected', 'error');
        return;
    }

    const expectedResult = document.getElementById('correction-expected').value.trim();
    const issueTypeEl = document.querySelector('input[name="issue-type"]:checked');

    if (!expectedResult) {
        showToast('Please describe what should have happened', 'warning');
        return;
    }

    if (!issueTypeEl) {
        showToast('Please select an issue type', 'warning');
        return;
    }

    const issueType = issueTypeEl.value;
    const analyzeBtn = document.getElementById('analyze-correction-btn');
    const step1 = document.getElementById('correction-step-1');
    const step2 = document.getElementById('correction-step-2');
    const analysisDiv = document.getElementById('correction-analysis');

    // Show loading state
    analyzeBtn.disabled = true;
    analyzeBtn.innerHTML = '🔄 Analyzing...';

    try {
        const response = await fetch('/api/v1/logic/corrections/analyze', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                trace_id: currentCorrectionTrace.trace_id,
                expected_result: expectedResult,
                issue_type: issueType
            })
        });

        if (!response.ok) {
            const errorData = await response.json().catch(() => ({}));
            throw new Error(errorData.detail || `HTTP ${response.status}`);
        }

        const analysis = await response.json();

        // Store for use by fixWithSelfImprove
        window.currentCorrectionAnalysis = analysis;
        window.currentCorrectionExpected = expectedResult;

        // Show analysis results
        step1.style.display = 'none';
        step2.style.display = 'block';
        analysisDiv.innerHTML = renderCorrectionAnalysis(analysis);

    } catch (error) {
        console.error('Failed to analyze correction:', error);
        showToast(`Analysis failed: ${error.message}`, 'error');
    } finally {
        analyzeBtn.disabled = false;
        analyzeBtn.innerHTML = '🤖 Analyze with AI';
    }
}

// Render AI analysis results
function renderCorrectionAnalysis(analysis) {
    const issueTypeLabels = {
        wrong_entity: '🏠 Wrong device/entity',
        wrong_action: '⚡ Wrong action',
        wrong_routing: '🚦 Wrong routing',
        clarification_needed: '❓ Missing clarification',
        tone_content: '💬 Tone/content issue',
        other: '📝 Other'
    };

    let suggestionsHtml = '';
    if (analysis.suggestions && analysis.suggestions.length > 0) {
        suggestionsHtml = analysis.suggestions.map((sugg, idx) => `
            <div class="suggestion-card ${idx === 0 ? 'recommended' : ''}">
                <div class="suggestion-header">
                    <span class="suggestion-rank">${idx === 0 ? '🥇' : idx === 1 ? '🥈' : '🥉'}</span>
                    <span class="suggestion-title">${escapeHtml(sugg.title)}</span>
                    <span class="suggestion-confidence">${(sugg.confidence * 100).toFixed(0)}% confidence</span>
                    <span class="suggestion-impact impact-${sugg.impact_level}">${sugg.impact_level} impact</span>
                </div>
                <div class="suggestion-body">
                    <p>${escapeHtml(sugg.description)}</p>
                    ${sugg.reasoning ? `<p class="suggestion-reasoning"><strong>Why:</strong> ${escapeHtml(sugg.reasoning)}</p>` : ''}
                </div>
                <div class="suggestion-diff">
                    <div class="diff-section diff-before">
                        <span class="diff-label">Before:</span>
                        <pre>${escapeHtml(sugg.diff_before || 'N/A')}</pre>
                    </div>
                    <div class="diff-section diff-after">
                        <span class="diff-label">After:</span>
                        <pre>${escapeHtml(sugg.diff_after || sugg.proposed_value || 'N/A')}</pre>
                    </div>
                </div>
                <div class="suggestion-actions">
                    <button class="btn btn-secondary btn-sm" onclick="window.testSuggestion('${analysis.analysis_id}', '${sugg.suggestion_id}')">
                        🧪 Test
                    </button>
                    <button class="btn btn-primary btn-sm" onclick="window.applySuggestion('${analysis.analysis_id}', '${sugg.suggestion_id}')">
                        ✓ Apply Fix
                    </button>
                </div>
            </div>
        `).join('');
    } else {
        suggestionsHtml = '<div class="no-suggestions">No automatic fixes suggested. Manual adjustment may be required.</div>';
    }

    return `
        <div class="analysis-header">
            <h4>🤖 AI Analysis Complete</h4>
            <button class="btn btn-secondary btn-sm" onclick="window.backToCorrectionStep1()">← Back</button>
        </div>

        <div class="analysis-section root-cause">
            <h5>📍 Root Cause</h5>
            <p>${escapeHtml(analysis.root_cause)}</p>
            ${analysis.root_cause_logic_id ? `
            <div class="root-cause-details">
                <span class="label">Problem Area:</span>
                <code>${escapeHtml(analysis.root_cause_logic_id)}</code>
            </div>
            ` : ''}
        </div>

        <div class="analysis-section suggestions">
            <h5>💡 Suggested Fixes</h5>
            ${suggestionsHtml}
        </div>

        <div class="analysis-actions">
            <button class="btn btn-secondary" onclick="window.closeCorrectionModal()">Close</button>
            <button class="btn btn-warning" onclick="window.markAsWrongOnly('${analysis.trace_id}')">
                Mark as Wrong (No Fix)
            </button>
            <button class="btn btn-primary" onclick="window.fixWithSelfImprove('${analysis.trace_id}')">
                🔧 Fix with Self-Improve
            </button>
        </div>
    `;
}

// Fix with Self-Improve - launch self-improvement agent with correction context
window.fixWithSelfImprove = async function (traceId) {
    // Get the current correction analysis data
    const analysis = window.currentCorrectionAnalysis;
    if (!analysis) {
        showToast('No analysis data available', 'error');
        return;
    }

    // Build the improvement request from the correction context
    const request = `Fix incorrect response behavior:

**Trace ID:** ${traceId}
**Root Cause:** ${analysis.root_cause || 'Unknown'}
${analysis.root_cause_logic_id ? `**Problem Area:** ${analysis.root_cause_logic_id}` : ''}

**User's Expected Behavior:**
${window.currentCorrectionExpected || 'Not specified'}

**Suggested Fixes from Analysis:**
${analysis.suggestions?.map((s, i) => `${i + 1}. ${s.description}`).join('\n') || 'None'}

Please investigate this issue and propose a fix that ensures the system responds correctly in similar situations.`;

    // Close the correction modal
    window.closeCorrectionModal();

    // Navigate to self-improvement page
    showPage('self-improve');

    // Wait for page to load
    await new Promise(resolve => setTimeout(resolve, 100));

    // Submit the improvement request
    try {
        const response = await fetch(`${API_BASE}/api/v1/self-improve/improve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                request: request,
                model: 'opusplan',
                auto_approve: false,
                source: 'correction_modal',
                trace_id: traceId
            }),
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const result = await response.json();
        showToast('Self-improvement session started', 'success');

        if (result.session_id && SelfImprovement) {
            SelfImprovement.activeSessionId = result.session_id;
            SelfImprovement.startStreaming(result.session_id);
            await SelfImprovement.loadActiveSession();
        }
    } catch (error) {
        console.error('Failed to start self-improvement:', error);
        showToast('Failed to start self-improvement: ' + error.message, 'error');
    }
};

// Go back to step 1
window.backToCorrectionStep1 = function () {
    document.getElementById('correction-step-1').style.display = 'block';
    document.getElementById('correction-step-2').style.display = 'none';
}

// Test a suggestion before applying
window.testSuggestion = async function (analysisId, suggestionId) {
    showToast('Testing suggestion against historical data...', 'info');

    try {
        const response = await fetch(`/api/v1/logic/corrections/${analysisId}/suggestions/${suggestionId}/test`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const results = await response.json();

        // Show test results
        let message = `Test complete: ${results.improvement_count} improvements`;
        if (results.regression_count > 0) {
            message += `, ⚠️ ${results.regression_count} regressions`;
            showToast(message, 'warning');
        } else {
            showToast(message, 'success');
        }
    } catch (error) {
        console.error('Failed to test suggestion:', error);
        showToast('Test failed: ' + error.message, 'error');
    }
}

// Apply a suggestion
window.applySuggestion = async function (analysisId, suggestionId) {
    if (!confirm('Apply this fix? This will modify the system configuration.')) {
        return;
    }

    try {
        const response = await fetch(`/api/v1/logic/corrections/${analysisId}/suggestions/${suggestionId}/apply`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        showToast('Fix applied successfully!', 'success');
        window.closeCorrectionModal();

        // Refresh logic data
        if (typeof loadLogicData === 'function') {
            loadLogicData();
        }
    } catch (error) {
        console.error('Failed to apply suggestion:', error);
        showToast('Failed to apply fix: ' + error.message, 'error');
    }
}

// Mark trace as wrong without applying a fix
window.markAsWrongOnly = async function (traceId) {
    try {
        const response = await fetch(`/api/v1/dashboard/traces/${traceId}/mark-wrong`, {
            method: 'POST'
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        showToast('Marked as incorrect. This helps improve future analysis.', 'success');
        window.closeCorrectionModal();
    } catch (error) {
        console.error('Failed to mark as wrong:', error);
        showToast('Failed to mark as wrong: ' + error.message, 'error');
    }
}

function updateLogicStats() {
    // Count patterns from the nested structure
    let patternCount = 0;
    if (logicData.patterns) {
        Object.values(logicData.patterns).forEach(group => {
            if (group.patterns) {
                patternCount += Object.keys(group.patterns).length;
            }
        });
    }
    document.getElementById('logic-patterns-count').textContent = patternCount;

    // Count routing rules
    let routingCount = 0;
    if (logicData.routing) {
        routingCount = Object.keys(logicData.routing).length;
    }
    document.getElementById('logic-routing-count').textContent = routingCount;

    // Count overrides
    let overridesCount = 0;
    if (logicData.overrides) {
        overridesCount = Object.keys(logicData.overrides).length;
    }
    document.getElementById('logic-overrides-count').textContent = overridesCount;

    // Count aliases
    const aliasCount = logicData.aliases ? Object.keys(logicData.aliases).length : 0;
    document.getElementById('logic-aliases-count').textContent = aliasCount;
}

function renderPatternGroups() {
    const container = document.getElementById('pattern-groups');
    const filterValue = document.getElementById('pattern-group-filter')?.value || '';
    const showDisabled = document.getElementById('show-disabled-patterns')?.checked || false;

    if (!logicData.patterns || Object.keys(logicData.patterns).length === 0) {
        container.innerHTML = '<div class="text-muted">No patterns loaded</div>';
        return;
    }

    const groupIcons = {
        emergency: '🚨',
        instant: '⚡',
        action: '🎯',
        memory: '📝',
        query: '❓',
        gesture: '👋'
    };

    let html = '';

    // logicData.patterns is { groupName: { name, patterns: { patternName: {...} }, pattern_count } }
    Object.entries(logicData.patterns).forEach(([groupName, group]) => {
        // Filter by group if selected
        if (filterValue && groupName !== filterValue) return;

        // patterns is an object { patternName: patternData }
        const patternsObj = group.patterns || {};
        const patternsArray = Object.values(patternsObj);
        const visiblePatterns = showDisabled ? patternsArray : patternsArray.filter(p => p.enabled !== false);

        if (visiblePatterns.length === 0) return;

        const icon = groupIcons[groupName] || '📋';

        html += `
            <div class="pattern-group" data-group="${groupName}">
                <div class="pattern-group-header" onclick="togglePatternGroup('${groupName}')">
                    <div class="pattern-group-title">
                        <span>${icon}</span>
                        <h3>${capitalizeFirst(groupName)} Patterns</h3>
                        <span class="pattern-group-count">${visiblePatterns.length} patterns</span>
                    </div>
                    <span class="pattern-group-toggle">▼</span>
                </div>
                <div class="pattern-group-content">
                    <div class="pattern-list">
                        ${visiblePatterns.map(p => renderPatternCard(groupName, p)).join('')}
                    </div>
                </div>
            </div>
        `;
    });

    container.innerHTML = html || '<div class="text-muted">No patterns match the filter</div>';
}

function renderPatternCard(group, pattern) {
    const confidenceClass = pattern.confidence >= 0.9 ? 'confidence-high' :
        pattern.confidence >= 0.7 ? 'confidence-medium' : 'confidence-low';
    const disabledClass = pattern.enabled === false ? 'disabled' : '';

    const examples = pattern.examples || [];
    const examplesHtml = examples.slice(0, 3).map(ex =>
        `<span class="pattern-example">"${escapeHtml(ex)}"</span>`
    ).join('');

    return `
        <div class="pattern-card ${disabledClass}" data-pattern="${escapeHtml(pattern.name)}">
            <div class="pattern-card-header">
                <span class="pattern-name">${escapeHtml(pattern.name)}</span>
                <span class="pattern-badge ${confidenceClass}">${(pattern.confidence * 100).toFixed(0)}% confidence</span>
            </div>
            <div class="pattern-regex">${escapeHtml(pattern.pattern)}</div>
            ${pattern.description ? `<div class="pattern-description">${escapeHtml(pattern.description)}</div>` : ''}
            ${examples.length > 0 ? `<div class="pattern-examples">${examplesHtml}</div>` : ''}
            <div class="pattern-actions">
                <button class="btn btn-small btn-secondary" onclick="openPatternEditor('${group}', '${escapeHtml(pattern.name)}')">
                    ✏️ Edit
                </button>
                <button class="btn btn-small ${pattern.enabled === false ? 'btn-primary' : 'btn-secondary'}"
                        onclick="togglePattern('${group}', '${escapeHtml(pattern.name)}', ${pattern.enabled === false})">
                    ${pattern.enabled === false ? '✓ Enable' : '✕ Disable'}
                </button>
            </div>
        </div>
    `;
}

function togglePatternGroup(groupName) {
    const group = document.querySelector(`.pattern-group[data-group="${groupName}"]`);
    if (group) {
        group.classList.toggle('expanded');
    }
}

function capitalizeFirst(str) {
    return str.charAt(0).toUpperCase() + str.slice(1);
}

function openPatternEditor(group, patternName) {
    const groupData = logicData.patterns?.[group];
    if (!groupData) return;

    // patterns is an object { patternName: patternData }
    const pattern = groupData.patterns?.[patternName];
    if (!pattern) return;

    currentEditPattern = { group, name: patternName };

    document.getElementById('edit-pattern-name').value = pattern.name;
    document.getElementById('edit-pattern-regex').value = pattern.pattern;
    document.getElementById('edit-pattern-subcategory').value = pattern.sub_category || '';
    document.getElementById('edit-pattern-confidence').value = pattern.confidence || 0.9;
    document.getElementById('edit-pattern-description').value = pattern.description || '';
    document.getElementById('edit-pattern-enabled').checked = pattern.enabled !== false;
    document.getElementById('edit-pattern-reason').value = '';

    document.getElementById('pattern-modal').style.display = 'flex';
}

function closePatternModal() {
    document.getElementById('pattern-modal').style.display = 'none';
    currentEditPattern = null;
}

async function savePatternEdit() {
    if (!currentEditPattern) return;

    const updates = {
        pattern: document.getElementById('edit-pattern-regex').value,
        sub_category: document.getElementById('edit-pattern-subcategory').value,
        confidence: parseFloat(document.getElementById('edit-pattern-confidence').value),
        description: document.getElementById('edit-pattern-description').value,
        enabled: document.getElementById('edit-pattern-enabled').checked,
        reason: document.getElementById('edit-pattern-reason').value || 'Dashboard edit'
    };

    try {
        const response = await fetch(`/api/v1/logic/patterns/${currentEditPattern.group}/${currentEditPattern.name}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify(updates)
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || 'Failed to save pattern');
        }

        showToast('Pattern updated successfully', 'success');
        closePatternModal();
        await loadLogicData();
    } catch (error) {
        console.error('Failed to save pattern:', error);
        showToast(error.message, 'error');
    }
}

async function togglePattern(group, patternName, currentlyDisabled) {
    try {
        const response = await fetch(`/api/v1/logic/patterns/${group}/${patternName}`, {
            method: 'PUT',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                enabled: currentlyDisabled,
                reason: currentlyDisabled ? 'Enabled from dashboard' : 'Disabled from dashboard'
            })
        });

        if (!response.ok) throw new Error('Failed to toggle pattern');

        showToast(`Pattern ${currentlyDisabled ? 'enabled' : 'disabled'}`, 'success');
        await loadLogicData();
    } catch (error) {
        console.error('Failed to toggle pattern:', error);
        showToast('Failed to toggle pattern', 'error');
    }
}

function renderRoutingRules() {
    const container = document.getElementById('routing-rules');

    if (!logicData.routing || Object.keys(logicData.routing).length === 0) {
        container.innerHTML = '<div class="text-muted">No routing rules loaded</div>';
        return;
    }

    let html = '';
    // logicData.routing is { intent: { intent, agent, description, priority, ... } }
    Object.entries(logicData.routing).forEach(([intent, config]) => {
        const agent = config.agent || 'unknown';
        const priority = config.priority || 'normal';
        const description = config.description || '';

        html += `
            <div class="routing-rule-card">
                <div class="routing-rule-header">
                    <div>
                        <span class="routing-intent">${intent}</span>
                        <span class="routing-arrow">→</span>
                        <span class="routing-agent">${agent}</span>
                    </div>
                    <span class="routing-priority">Priority: ${priority}</span>
                </div>
                ${description ? `<div class="text-muted">${escapeHtml(description)}</div>` : ''}
            </div>
        `;
    });

    container.innerHTML = html || '<div class="text-muted">No routing rules configured</div>';
}

function renderOverrides() {
    const container = document.getElementById('overrides-list');
    let html = '';

    if (!logicData.overrides || Object.keys(logicData.overrides).length === 0) {
        container.innerHTML = '<div class="text-muted">No overrides configured</div>';
        return;
    }

    // logicData.overrides is { name: { name, description, enabled, condition_type, conditions, rules } }
    Object.entries(logicData.overrides).forEach(([name, config]) => {
        const typeIcon = {
            'user': '👤',
            'room': '🏠',
            'time': '🕐',
            'phrase': '💬'
        }[config.condition_type] || '⚙️';

        const typeClass = config.condition_type || 'default';
        const enabledBadge = config.enabled ? '✓ Enabled' : '✗ Disabled';

        html += `
            <div class="override-card">
                <div style="display: flex; justify-content: space-between; align-items: center; margin-bottom: 8px;">
                    <span class="override-type ${typeClass}">${typeIcon} ${capitalizeFirst(config.condition_type || 'unknown')}</span>
                    <span class="text-muted" style="font-size: 12px;">${enabledBadge}</span>
                </div>
                <h4 style="margin: 0 0 8px 0; font-size: 14px;">${escapeHtml(config.name)}</h4>
                <div class="override-condition">${escapeHtml(config.description || '')}</div>
            </div>
        `;
    });

    container.innerHTML = html || '<div class="text-muted">No overrides configured</div>';
}

function formatOverrideConfig(config) {
    const parts = [];
    if (config.voice_profile) parts.push(`Voice: ${config.voice_profile}`);
    if (config.response_style) parts.push(`Style: ${config.response_style}`);
    if (config.default_agent) parts.push(`Agent: ${config.default_agent}`);
    if (config.tts_volume) parts.push(`Volume: ${config.tts_volume}`);
    if (config.quiet_mode) parts.push('🔇 Quiet Mode');
    if (config.whisper_mode) parts.push('🤫 Whisper Mode');
    return parts.length > 0 ? parts.join(' • ') : 'No specific overrides';
}

function renderAliases() {
    const container = document.getElementById('aliases-list');

    if (!logicData.aliases || Object.keys(logicData.aliases).length === 0) {
        container.innerHTML = '<div class="text-muted">No entity aliases configured</div>';
        return;
    }

    let html = '';
    // logicData.aliases is { aliasName: { alias, entity_id, resolve_by, domain, priority } }
    Object.entries(logicData.aliases).forEach(([name, config]) => {
        const target = config.entity_id || (config.resolve_by ? `Resolve by: ${config.resolve_by}` : 'N/A');
        html += `
            <div class="alias-card">
                <div class="alias-names">
                    <span class="alias-name">${escapeHtml(config.alias || name)}</span>
                </div>
                <div class="alias-target">${escapeHtml(target)}</div>
            </div>
        `;
    });

    container.innerHTML = html;
}

async function runPatternTest() {
    const input = document.getElementById('pattern-test-input').value.trim();
    if (!input) {
        showToast('Please enter text to test', 'warning');
        return;
    }

    const resultsDiv = document.getElementById('pattern-test-results');
    const summaryDiv = document.getElementById('test-summary');
    const matchesDiv = document.getElementById('test-matches');

    resultsDiv.style.display = 'block';
    summaryDiv.innerHTML = '<div class="loading">Testing patterns...</div>';
    matchesDiv.innerHTML = '';

    try {
        const response = await fetch('/api/v1/logic/patterns/test', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ text: input })
        });

        if (!response.ok) throw new Error('Pattern test failed');

        const result = await response.json();

        if (result.matches && result.matches.length > 0) {
            const bestMatch = result.matches[0];
            summaryDiv.className = 'test-summary matched';
            summaryDiv.innerHTML = `
                <h4>✓ Best Match: ${escapeHtml(bestMatch.pattern_name)}</h4>
                <p>Group: <strong>${bestMatch.group}</strong> • Confidence: <strong>${(bestMatch.confidence * 100).toFixed(0)}%</strong></p>
            `;

            if (result.matches.length > 1) {
                matchesDiv.innerHTML = `
                    <div class="test-matches-title">All Matches (${result.matches.length})</div>
                    <div class="test-match-list">
                        ${result.matches.map(m => `
                            <div class="test-match-item">
                                <div>
                                    <span class="test-match-name">${escapeHtml(m.pattern_name)}</span>
                                    <span class="test-match-group">${m.group}</span>
                                </div>
                                <span class="test-match-confidence pattern-badge ${m.confidence >= 0.9 ? 'confidence-high' : m.confidence >= 0.7 ? 'confidence-medium' : 'confidence-low'}">
                                    ${(m.confidence * 100).toFixed(0)}%
                                </span>
                            </div>
                        `).join('')}
                    </div>
                `;
            }
        } else {
            summaryDiv.className = 'test-summary no-match';
            summaryDiv.innerHTML = `
                <h4>✗ No patterns matched</h4>
                <p>The input did not match any configured patterns. It would be routed to the Interaction agent for LLM processing.</p>
            `;
        }
    } catch (error) {
        console.error('Pattern test failed:', error);
        summaryDiv.className = 'test-summary no-match';
        summaryDiv.innerHTML = `<h4>Error</h4><p>${error.message}</p>`;
    }
}

// Logic page initialization is now handled in showPage() function

// =============================================================================
// Self-Improvement Page (Simplified)
// =============================================================================

/**
 * Simplified Self-Improvement UI
 *
 * Shows:
 * - Status bar at top
 * - Plan approval section (when plan proposed)
 * - CLI output (all Claude activity)
 * - Commit section (when changes ready)
 */

const SelfImprovement = {
    activeSessionId: null,
    eventSource: null,
    pollInterval: null,
    pollingSessionId: null,
    cliOutput: [],  // Store CLI output for copy function

    async init() {
        console.log('Initializing Self-Improvement page...');
        this.bindEvents();
        await this.checkAvailability();
        await this.loadActiveSession();
    },

    bindEvents() {
        // Modal controls
        document.getElementById('new-improvement-btn')?.addEventListener('click', () => {
            document.getElementById('si-modal').style.display = 'flex';
        });

        document.getElementById('si-modal-close')?.addEventListener('click', () => {
            document.getElementById('si-modal').style.display = 'none';
        });

        document.getElementById('si-cancel')?.addEventListener('click', () => {
            document.getElementById('si-modal').style.display = 'none';
        });

        document.getElementById('si-submit')?.addEventListener('click', () => {
            this.submitImprovement();
        });

        // Session controls
        document.getElementById('si-stop-btn')?.addEventListener('click', () => {
            this.stopSession();
        });

        // Plan approval
        document.getElementById('si-approve-plan')?.addEventListener('click', () => {
            this.approvePlan();
        });

        document.getElementById('si-reject-plan')?.addEventListener('click', () => {
            this.rejectPlan();
        });

        // Code approval
        document.getElementById('si-approve-changes')?.addEventListener('click', () => {
            this.approveSession();
        });

        document.getElementById('si-reject-changes')?.addEventListener('click', () => {
            this.rejectSession();
        });
    },

    async checkAvailability() {
        try {
            const response = await fetch(`${API_BASE}/api/v1/self-improve/status`);
            const data = await response.json();

            const statusDot = document.getElementById('si-status-dot');
            const statusText = document.getElementById('si-status-text');
            const newBtn = document.getElementById('new-improvement-btn');

            if (data.available) {
                statusDot?.classList.add('available');
                statusDot?.classList.remove('unavailable');
                statusText.textContent = 'Ready';
                newBtn.disabled = false;
            } else {
                statusDot?.classList.add('unavailable');
                statusDot?.classList.remove('available');
                statusText.textContent = data.error || 'Unavailable';
                newBtn.disabled = true;
            }
        } catch (error) {
            console.error('Failed to check availability:', error);
        }
    },

    async loadActiveSession() {
        try {
            const response = await fetch(`${API_BASE}/api/v1/self-improve/sessions`);
            const sessions = await response.json();

            // Find most recent active session
            const activeSession = sessions.find(s =>
                !['completed', 'failed', 'rejected', 'stopped'].includes(s.status)
            );

            if (activeSession) {
                this.activeSessionId = activeSession.session_id;
                this.renderSession(activeSession);
                // Start polling for updates
                this.startPolling(activeSession.session_id);
            } else if (sessions.length > 0) {
                // Show most recent session
                this.activeSessionId = sessions[0].session_id;
                this.renderSession(sessions[0]);
                // Stop polling for completed sessions
                this.stopPolling();
            } else {
                this.stopPolling();
            }
        } catch (error) {
            console.error('Failed to load sessions:', error);
        }
    },

    renderSession(session) {
        // Update timeline
        this.updateTimeline(session.status);

        // Handle action required banner
        this.handleStatusChange(session.status, session);

        // Update status bar
        const statusText = document.getElementById('si-status-text');
        const requestText = document.getElementById('si-request-text');
        const stopBtn = document.getElementById('si-stop-btn');

        const statusLabels = {
            'pending': '⏳ Pending',
            'diagnosing': '🔍 Diagnosing',
            'awaiting_plan_approval': '📋 Plan Ready',
            'implementing': '⚙️ Implementing',
            'testing': '🧪 Testing',
            'awaiting_approval': '📝 Changes Ready',
            'committing': '💾 Committing',
            'completed': '✅ Completed',
            'failed': '❌ Failed',
            'rejected': '🚫 Rejected',
            'stopped': '⏹️ Stopped',
        };

        statusText.textContent = statusLabels[session.status] || session.status;
        requestText.textContent = session.request || '';

        // Show/hide stop button
        const isActive = !['completed', 'failed', 'rejected', 'stopped'].includes(session.status);
        stopBtn?.classList.toggle('hidden', !isActive);

        // Plan modal - show when awaiting approval
        const planModal = document.getElementById('si-plan-modal');
        if (session.status === 'awaiting_plan_approval' && session.proposed_plan) {
            this.renderPlan(session.proposed_plan, session.safety_score);
            planModal.style.display = 'flex';
        } else {
            planModal.style.display = 'none';
        }

        // CLI output - always visible
        const cliOutput = document.getElementById('si-cli-output');
        const cliStatus = document.getElementById('si-cli-status');

        if (isActive) {
            cliStatus.textContent = '● live';

            if (session.current_thinking || session.messages?.length > 0 || session.operations?.length > 0) {
                this.renderCliOutput(session);
            } else {
                if (!cliOutput.textContent || cliOutput.textContent.includes('Waiting') || cliOutput.textContent.includes('No active')) {
                    cliOutput.innerHTML = '<span class="cli-waiting">Waiting for Claude to start...</span>';
                }
            }
        } else if (session.current_thinking || session.messages?.length > 0 || session.operations?.length > 0) {
            cliStatus.textContent = '';
            this.renderCliOutput(session);
        } else {
            cliStatus.textContent = '';
        }

        // Commit modal - show when awaiting approval
        const commitModal = document.getElementById('si-commit-modal');
        if (session.status === 'awaiting_approval') {
            document.getElementById('si-changes-summary').innerHTML = `
                <div class="changes-stats">
                    <strong>${session.files_modified?.length || 0}</strong> files changed
                    ${session.estimated_api_cost_usd ? ` · Est. API cost: $${session.estimated_api_cost_usd.toFixed(4)}` : ''}
                </div>
                <ul class="changes-files">
                    ${(session.files_modified || []).map(f => `<li>${this.escapeHtml(f)}</li>`).join('')}
                </ul>
            `;
            commitModal.style.display = 'flex';
        } else {
            commitModal.style.display = 'none';
        }
    },

    // Timeline management
    updateTimeline(status) {
        const statusToStep = {
            'pending': 'started',
            'diagnosing': 'diagnosing',
            'awaiting_plan_approval': 'plan_approval',
            'implementing': 'implementing',
            'testing': 'testing',
            'awaiting_approval': 'commit_approval',
            'committing': 'commit_approval',
            'completed': 'completed',
            'failed': 'completed',
            'rejected': 'plan_approval',
            'stopped': null
        };

        const stepOrder = ['started', 'diagnosing', 'plan_approval', 'implementing', 'testing', 'commit_approval', 'completed'];
        const currentStep = statusToStep[status];
        const currentIndex = stepOrder.indexOf(currentStep);

        // Update each step
        document.querySelectorAll('.timeline-step').forEach(el => {
            const step = el.dataset.step;
            const stepIndex = stepOrder.indexOf(step);

            el.classList.remove('completed', 'active', 'needs-attention', 'failed');

            if (status === 'failed') {
                if (stepIndex < currentIndex) el.classList.add('completed');
                else if (stepIndex === currentIndex) el.classList.add('failed');
            } else if (stepIndex < currentIndex) {
                el.classList.add('completed');
            } else if (stepIndex === currentIndex) {
                el.classList.add('active');
                if (status === 'awaiting_plan_approval' || status === 'awaiting_approval') {
                    el.classList.add('needs-attention');
                }
            }
        });

        // Update connectors
        document.querySelectorAll('.timeline-connector').forEach((el, idx) => {
            el.classList.toggle('completed', idx < currentIndex);
        });
    },

    // Action Required Banner
    showActionRequired(type, session) {
        const banner = document.getElementById('si-action-required');
        const title = document.getElementById('action-required-title');
        const desc = document.getElementById('action-required-description');
        const buttons = document.getElementById('action-required-buttons');

        banner?.classList.remove('hidden');

        switch (type) {
            case 'plan_approval':
                title.textContent = '📋 Plan Review Required';
                desc.textContent = 'Claude has proposed a plan. Review and approve or reject.';
                buttons.innerHTML = `
                    <button class="btn btn-success btn-sm" onclick="SelfImprovement.approvePlan()">✓ Approve Plan</button>
                    <button class="btn btn-danger btn-sm" onclick="SelfImprovement.rejectPlan()">✗ Reject</button>
                    <button class="btn btn-secondary btn-sm" onclick="document.getElementById('si-plan-modal').style.display='flex'">View Plan</button>
                `;
                break;

            case 'commit_approval':
                title.textContent = '✅ Ready to Commit';
                desc.textContent = `Changes ready: ${session?.files_modified?.length || 0} files modified`;
                buttons.innerHTML = `
                    <button class="btn btn-success btn-sm" onclick="SelfImprovement.approveSession()">✓ Commit Changes</button>
                    <button class="btn btn-danger btn-sm" onclick="SelfImprovement.rejectSession()">✗ Reject</button>
                    <button class="btn btn-secondary btn-sm" onclick="document.getElementById('si-commit-modal').style.display='flex'">View Changes</button>
                `;
                break;

            default:
                banner?.classList.add('hidden');
        }
    },

    hideActionRequired() {
        document.getElementById('si-action-required')?.classList.add('hidden');
    },

    handleStatusChange(status, session) {
        this.updateTimeline(status);

        if (status === 'awaiting_plan_approval') {
            this.showActionRequired('plan_approval', session);
        } else if (status === 'awaiting_approval') {
            this.showActionRequired('commit_approval', session);
        } else {
            this.hideActionRequired();
        }
    },

    renderPlan(plan, safetyScore) {
        const content = document.getElementById('si-plan-content');
        if (!content) return;

        // Update safety score badge
        const safetyEl = document.getElementById('si-safety-score');
        if (safetyEl && safetyScore) {
            const scoreClass = safetyScore.score >= 0.8 ? 'safe' : safetyScore.score >= 0.6 ? 'caution' : 'risky';
            safetyEl.className = `si-safety-score ${scoreClass}`;
            safetyEl.textContent = `Safety: ${Math.round(safetyScore.score * 100)}%`;
            safetyEl.title = safetyScore.reasons?.join(', ') || '';
        }

        content.innerHTML = `
            <div class="plan-field"><label>Issue:</label><div>${this.escapeHtml(plan.issue || 'N/A')}</div></div>
            <div class="plan-field"><label>Root Cause:</label><div>${this.escapeHtml(plan.root_cause || 'N/A')}</div></div>
            <div class="plan-field"><label>Proposed Fix:</label><div>${this.escapeHtml(plan.proposed_fix || 'N/A')}</div></div>
            <div class="plan-field"><label>Files:</label><div>${this.escapeHtml(Array.isArray(plan.files_affected) ? plan.files_affected.join(', ') : (plan.files_affected || 'N/A'))}</div></div>
            <div class="plan-field risks"><label>Risks:</label><div>${this.escapeHtml(plan.risks || 'None')}</div></div>
            <div class="plan-field"><label>Tests:</label><div>${this.escapeHtml(plan.tests || 'N/A')}</div></div>
        `;
    },

    renderCliOutput(session) {
        const output = document.getElementById('si-cli-output');
        if (!output) return;

        let html = '';

        // Add messages (Claude's explanations)
        if (session.messages?.length > 0) {
            for (const msg of session.messages) {
                html += `<span class="cli-line stdout">${this.escapeHtml(msg.content || '')}</span>\n`;
            }
        }

        // Add operations (tool uses)
        if (session.operations?.length > 0) {
            for (const op of session.operations) {
                html += `<span class="cli-line json-event">[${op.operation_type}] ${op.command ? this.escapeHtml(op.command) : ''} ${op.file_path ? this.escapeHtml(op.file_path) : ''}</span>\n`;
            }
        }

        // Add current thinking
        if (session.current_thinking) {
            html += `<span class="cli-thinking">${this.escapeHtml(session.current_thinking)}</span>`;
        }

        output.innerHTML = html || '<span class="cli-empty">No output yet</span>';

        // Auto-scroll if enabled
        if (document.getElementById('cli-auto-scroll')?.checked) {
            const terminal = document.getElementById('cli-terminal');
            if (terminal) terminal.scrollTop = terminal.scrollHeight;
        }
    },

    // CLI output helpers
    clearCLI() {
        const output = document.getElementById('si-cli-output');
        if (output) output.innerHTML = '';
        this.cliOutput = [];
    },

    copyCLI() {
        const text = this.cliOutput.map(d => d.line || d).join('\n');
        navigator.clipboard.writeText(text || document.getElementById('si-cli-output')?.textContent || '');
        showToast({ title: 'Copied', message: 'CLI output copied to clipboard', type: 'success' });
    },

    startStreaming(sessionId) {
        if (this.eventSource) {
            this.eventSource.close();
        }

        // Clear any existing poll interval
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
        }

        const streamUrl = `${API_BASE}/api/v1/self-improve/sessions/${sessionId}/stream`;
        console.log('Starting SSE stream:', streamUrl);

        this.eventSource = new EventSource(streamUrl);

        this.eventSource.onopen = () => {
            console.log('SSE connection opened');
        };

        this.eventSource.onmessage = (event) => {
            try {
                const data = JSON.parse(event.data);
                this.handleStreamEvent(data);
            } catch (e) {
                console.error('Failed to parse SSE:', e);
            }
        };

        this.eventSource.onerror = (e) => {
            console.error('SSE error, falling back to polling:', e);
            this.eventSource.close();
            this.eventSource = null;
            // Fall back to polling
            this.startPolling(sessionId);
        };
    },

    startPolling(sessionId) {
        // Don't start if already polling for this session
        if (this.pollInterval && this.pollingSessionId === sessionId) {
            return;
        }

        // Stop any existing polling
        this.stopPolling();

        this.pollingSessionId = sessionId;
        console.log('Starting polling for session:', sessionId);

        // Poll every 2 seconds
        this.pollInterval = setInterval(async () => {
            try {
                const response = await fetch(`${API_BASE}/api/v1/self-improve/sessions/${sessionId}`);
                if (response.ok) {
                    const session = await response.json();
                    this.renderSession(session);

                    // Stop polling if session is complete
                    if (['completed', 'failed', 'rejected', 'stopped'].includes(session.status)) {
                        this.stopPolling();
                    }
                }
            } catch (e) {
                console.error('Poll failed:', e);
            }
        }, 2000);
    },

    stopPolling() {
        if (this.pollInterval) {
            clearInterval(this.pollInterval);
            this.pollInterval = null;
            this.pollingSessionId = null;
        }
    },

    handleStreamEvent(event) {
        console.log('Stream event:', event.event_type, event);

        switch (event.event_type) {
            case 'init':
                if (event.session) {
                    this.renderSession(event.session);
                }
                break;
            case 'thinking':
                this.appendCliOutput(`<div class="cli-thinking-line">${this.escapeHtml(event.text)}</div>`);
                break;
            case 'diagnosing':
                // Status update during diagnosis
                this.appendCliOutput(`<div class="cli-status-line">📋 ${this.escapeHtml(event.message || 'Diagnosing...')}</div>`);
                break;
            case 'started':
                this.appendCliOutput(`<div class="cli-status-line">🚀 Started on branch: ${this.escapeHtml(event.branch || '')}</div>`);
                break;
            case 'tool_use':
                this.appendCliOutput(`<div class="cli-op"><span class="cli-op-type">[${event.tool}]</span> ${this.escapeHtml(event.input_preview || '')}</div>`);
                break;
            case 'plan_proposed':
                this.loadActiveSession();
                showToast({ title: 'Plan Ready', message: 'Review the proposed plan', type: 'info' });
                break;
            case 'awaiting_approval':
                this.loadActiveSession();
                showToast({ title: 'Changes Ready', message: 'Review and commit changes', type: 'info' });
                break;
            case 'completed':
                this.loadActiveSession();
                this.eventSource?.close();
                showToast({ title: 'Completed', message: 'Session completed', type: 'success' });
                break;
            case 'failed':
                this.loadActiveSession();
                this.eventSource?.close();
                showToast({ title: 'Failed', message: event.error || 'Session failed', type: 'error' });
                break;
            case 'stopped':
                this.loadActiveSession();
                this.eventSource?.close();
                showToast({ title: 'Stopped', message: 'Session stopped', type: 'info' });
                break;
        }
    },

    appendCliOutput(html) {
        const output = document.getElementById('si-cli-output');
        if (!output) return;

        // Remove "waiting" or "no active" message if present
        const waiting = output.querySelector('.cli-waiting, .cli-empty');
        if (waiting) waiting.remove();

        output.insertAdjacentHTML('beforeend', html);

        // Auto-scroll if enabled
        if (document.getElementById('cli-auto-scroll')?.checked) {
            const terminal = document.getElementById('cli-terminal');
            if (terminal) terminal.scrollTop = terminal.scrollHeight;
        }

        // Limit size
        while (output.children.length > 500) {
            output.removeChild(output.firstChild);
        }
    },

    async submitImprovement() {
        const request = document.getElementById('si-improvement-request')?.value;
        const model = document.querySelector('input[name="si-model"]:checked')?.value || 'sonnet';

        if (!request?.trim()) {
            showToast({ title: 'Error', message: 'Please describe the improvement', type: 'error' });
            return;
        }

        document.getElementById('si-modal').style.display = 'none';
        document.getElementById('si-improvement-request').value = '';

        try {
            const response = await fetch(`${API_BASE}/api/v1/self-improve/improve`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ request, model, auto_approve: false }),
            });

            if (!response.ok) throw new Error(`HTTP ${response.status}`);

            const result = await response.json();
            showToast({ title: 'Started', message: 'Investigation started', type: 'success' });

            if (result.session_id) {
                this.activeSessionId = result.session_id;
                this.startStreaming(result.session_id);
            }

            await this.loadActiveSession();

        } catch (error) {
            console.error('Failed to start:', error);
            showToast({ title: 'Error', message: error.message, type: 'error' });
        }
    },

    async stopSession() {
        if (!this.activeSessionId) return;
        if (!confirm('Stop this session?')) return;

        try {
            await fetch(`${API_BASE}/api/v1/self-improve/sessions/${this.activeSessionId}/stop`, {
                method: 'POST',
            });
            showToast({ title: 'Stopped', message: 'Session stopped', type: 'info' });
            this.loadActiveSession();
        } catch (error) {
            showToast({ title: 'Error', message: 'Failed to stop', type: 'error' });
        }
    },

    async approvePlan() {
        if (!this.activeSessionId) return;
        const feedback = document.getElementById('si-plan-feedback')?.value?.trim();

        try {
            await fetch(`${API_BASE}/api/v1/self-improve/sessions/${this.activeSessionId}/approve-plan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ feedback: feedback || null }),
            });

            document.getElementById('si-plan-feedback').value = '';
            showToast({ title: 'Approved', message: 'Proceeding with implementation', type: 'success' });
            this.loadActiveSession();
        } catch (error) {
            showToast({ title: 'Error', message: 'Failed to approve', type: 'error' });
        }
    },

    async rejectPlan() {
        if (!this.activeSessionId) return;
        const feedback = document.getElementById('si-plan-feedback')?.value?.trim();

        if (!feedback) {
            showToast({ title: 'Required', message: 'Please provide feedback', type: 'warning' });
            document.getElementById('si-plan-feedback')?.focus();
            return;
        }

        try {
            await fetch(`${API_BASE}/api/v1/self-improve/sessions/${this.activeSessionId}/reject-plan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ feedback }),
            });

            document.getElementById('si-plan-feedback').value = '';
            showToast({ title: 'Rejected', message: 'Plan rejected', type: 'info' });
            this.loadActiveSession();
        } catch (error) {
            showToast({ title: 'Error', message: 'Failed to reject', type: 'error' });
        }
    },

    async approveSession() {
        if (!this.activeSessionId) return;

        try {
            await fetch(`${API_BASE}/api/v1/self-improve/sessions/${this.activeSessionId}/approve`, {
                method: 'POST',
            });
            showToast({ title: 'Committed', message: 'Changes committed', type: 'success' });
            this.loadActiveSession();
        } catch (error) {
            showToast({ title: 'Error', message: 'Failed to commit', type: 'error' });
        }
    },

    async rejectSession() {
        if (!this.activeSessionId) return;
        if (!confirm('Discard all changes?')) return;

        try {
            await fetch(`${API_BASE}/api/v1/self-improve/sessions/${this.activeSessionId}/reject`, {
                method: 'POST',
            });
            showToast({ title: 'Discarded', message: 'Changes discarded', type: 'info' });
            this.loadActiveSession();
        } catch (error) {
            showToast({ title: 'Error', message: 'Failed to discard', type: 'error' });
        }
    },

    escapeHtml(text) {
        if (!text) return '';
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
};

