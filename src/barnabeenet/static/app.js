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

// =============================================================================
// Initialization
// =============================================================================

document.addEventListener('DOMContentLoaded', () => {
    initNavigation();
    initClock();
    initActivityControls();
    initConfigNav();
    initTestButtons();
    
    // Load initial data
    loadSystemStatus();
    loadStats();
    
    // Connect WebSocket
    connectWebSocket();
    
    // Refresh data periodically
    setInterval(loadSystemStatus, 30000);
    setInterval(loadStats, 60000);
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
