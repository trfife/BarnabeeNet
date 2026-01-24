Self-Improvement Agent Enhancement Plan
Executive Summary
This plan addresses gaps between the current self-improvement implementation and your requirements. The core issues are:
IssueCurrent StateTarget StateHome Page VisibilitySelf-improve sessions don't appear in activity feedSessions show as cards in activity feed, clickable to detailsEntry PointsOnly via dedicated Self-Improve pageChat, "Mark as Wrong", dedicated page, voiceCLI DisplayPartial Claude output in thinking streamFull raw CLI output (stdout + stderr)TimelineNo visual timelineProgress timeline at page topAction Required UIPlan approval inlineSticky banner at page topNotificationsExists but inconsistent triggersEvery phase change + when attention neededModel SelectionManual Sonnet/Opus choiceDefault to opusplan (auto-switching)Mark as Wrong → Self-ImproveNot connected"Fix with Self-Improve" button in correction modal

Phase 1: Home Page Integration (3-4 hours)
1.1 Add Self-Improvement to Activity Feed
File: src/barnabeenet/agents/self_improvement.py
The activity logging exists but uses custom activity types. Need to ensure they render properly in the home page feed.
python# Add these activity types to the _log_activity method calls
# Current types: self_improve.start, .diagnosing, .plan_proposed, etc.

# Enhancement: Include session_id and request preview in all activity items
# so the dashboard can make them clickable

async def _log_activity(
    self,
    session: ImprovementSession,
    event_type: str,
    title: str,
    detail: str | None = None,
    **kwargs,
) -> None:
    """Log activity with session linkage for dashboard clicks."""
    activity_logger = self._get_activity_logger()
    if activity_logger:
        await activity_logger.log(
            activity_type=f"self_improve.{event_type}",
            title=title,
            detail=detail,
            source="self_improvement_agent",
            # ADD these for clickability:
            session_id=session.session_id,
            request_preview=session.request[:80] if session.request else None,
            status=session.status.value,
            can_click=True,  # Signal to dashboard this is clickable
            click_target=f"/self-improve?session={session.session_id}",
            **kwargs,
        )
File: src/barnabeenet/static/app.js
javascript// In addActivityItem function, add handling for self_improve activities:

function addActivityItem(data) {
    // ... existing code ...

    // Check if this is a self-improvement activity that can be clicked
    const isSelfImprove = data.type?.startsWith('self_improve.');
    let clickHandler = '';

    if (isSelfImprove && data.session_id) {
        clickHandler = `onclick="navigateToSelfImprove('${data.session_id}')" style="cursor: pointer;"`;
    }

    // Modify the item HTML to include click handler
    item.innerHTML = `
        <div class="activity-item-content" ${clickHandler}>
            <span class="activity-time">${time}</span>
            <span class="activity-badge ${data.type}">${formatActivityType(data.type)}</span>
            ${data.status ? `<span class="activity-status status-${data.status}">${data.status}</span>` : ''}
            <span class="activity-message">${escapeHtml(data.message)}</span>
            ${isSelfImprove ? '<span class="activity-action">→ Click to view</span>' : ''}
        </div>
    `;
    // ...
}

function navigateToSelfImprove(sessionId) {
    showPage('self-improve');
    SelfImprovement.selectSession(sessionId);
}
1.2 Add Self-Improvement Session Cards to Home Page
File: src/barnabeenet/static/index.html
Add a new section to the dashboard page after Recent Request Traces:
html<!-- Active Self-Improvement Sessions (on Dashboard page) -->
<div class="card" id="active-si-sessions-card">
    <div class="card-header">
        <h3>🔧 Self-Improvement Sessions</h3>
        <button class="btn btn-primary btn-sm" onclick="showPage('self-improve')">View All</button>
    </div>
    <div class="card-body" id="active-si-sessions">
        <p class="text-muted">No active sessions</p>
    </div>
</div>
File: src/barnabeenet/static/app.js
javascript// Add function to load and display active SI sessions on dashboard
async function loadActiveSISessions() {
    try {
        const response = await fetch(`${API_BASE}/api/v1/self-improve/sessions`);
        if (!response.ok) return;

        const data = await response.json();
        const container = document.getElementById('active-si-sessions');
        if (!container) return;

        // Filter to recent/active sessions
        const recentSessions = data.sessions
            .filter(s => s.status !== 'completed' && s.status !== 'failed' ||
                        (new Date() - new Date(s.started_at)) < 24 * 60 * 60 * 1000)
            .slice(0, 5);

        if (recentSessions.length === 0) {
            container.innerHTML = '<p class="text-muted">No recent sessions</p>';
            return;
        }

        container.innerHTML = recentSessions.map(session => `
            <div class="si-session-card ${session.status}" onclick="navigateToSelfImprove('${session.session_id}')">
                <div class="si-session-status">${getStatusIcon(session.status)} ${session.status}</div>
                <div class="si-session-request">${escapeHtml(session.request.substring(0, 60))}...</div>
                <div class="si-session-time">${formatRelativeTime(session.started_at)}</div>
                ${session.status === 'awaiting_plan_approval' || session.status === 'awaiting_approval'
                    ? '<div class="si-needs-attention">⚠️ Needs your attention</div>'
                    : ''}
            </div>
        `).join('');
    } catch (error) {
        console.error('Failed to load SI sessions:', error);
    }
}

// Call on dashboard load and periodically
setInterval(loadActiveSISessions, 10000);

Phase 2: Entry Point Integration (2-3 hours)
2.1 Chat Integration - Start Self-Improve from Chat
File: src/barnabeenet/static/index.html
Add to Chat page, below the chat input:
html<!-- Quick action buttons below chat -->
<div class="chat-quick-actions">
    <button class="btn btn-secondary btn-sm" id="chat-self-improve-btn"
            title="Send to Self-Improvement Agent">
        🔧 Fix This
    </button>
</div>
File: src/barnabeenet/static/app.js
javascript// Add handler for "Fix This" button in chat
document.getElementById('chat-self-improve-btn')?.addEventListener('click', async () => {
    const chatMessages = document.querySelectorAll('.chat-message.user');
    const lastUserMessage = chatMessages[chatMessages.length - 1]?.textContent;

    if (!lastUserMessage) {
        showToast('No recent message to improve', 'warning');
        return;
    }

    // Get context from chat history
    const chatHistory = Array.from(document.querySelectorAll('.chat-message'))
        .slice(-6)  // Last 6 messages for context
        .map(el => `${el.classList.contains('user') ? 'User' : 'Assistant'}: ${el.textContent}`)
        .join('\n');

    const improvementRequest = `Fix this issue from chat:\n\nContext:\n${chatHistory}\n\nUser's issue: ${lastUserMessage}`;

    // Navigate to self-improve and pre-fill
    showPage('self-improve');
    document.getElementById('si-improvement-request').value = improvementRequest;
    document.getElementById('si-modal').style.display = 'flex';
});
2.2 Mark as Wrong → Self-Improve Connection
File: src/barnabeenet/static/index.html
In the correction modal analysis results section, add a button:
html<!-- In correction-analysis div, add this button to analysis-actions -->
<button class="btn btn-primary" onclick="window.fixWithSelfImprove()">
    🔧 Fix with Self-Improve Agent
</button>
File: src/barnabeenet/static/app.js
javascript// Add function to convert correction analysis to self-improvement request
window.fixWithSelfImprove = async function() {
    if (!currentCorrectionTrace) {
        showToast('No trace selected', 'error');
        return;
    }

    // Get the analysis context
    const expectedResult = document.getElementById('correction-expected').value;
    const issueType = document.querySelector('input[name="issue-type"]:checked')?.value;
    const rootCauseEl = document.querySelector('.analysis-section.root-cause p');
    const rootCause = rootCauseEl?.textContent || '';

    // Build improvement request with full context
    const improvementRequest = `
Fix incorrect behavior identified via "Mark as Wrong":

**Original Input:** "${currentCorrectionTrace.input_text}"
**Agent Used:** ${currentCorrectionTrace.agent_used}
**Actual Response:** "${currentCorrectionTrace.response_text}"
**Expected Response:** "${expectedResult}"
**Issue Type:** ${issueType}
**Root Cause Analysis:** ${rootCause}
**Trace ID:** ${currentCorrectionTrace.trace_id}

Please investigate the trace, find the bug, and fix it. Use the debug-logs.sh script to examine the full trace: ./scripts/debug-logs.sh trace ${currentCorrectionTrace.trace_id}
`.trim();

    // Close correction modal
    window.closeCorrectionModal();

    // Navigate to self-improve and start the improvement
    showPage('self-improve');

    // Start improvement directly
    try {
        const response = await fetch(`${API_BASE}/api/v1/self-improve/improve`, {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({
                request: improvementRequest,
                model: 'opusplan',  // Use auto model choice
                auto_approve: false,
                source: 'mark_as_wrong',
                trace_id: currentCorrectionTrace.trace_id
            }),
        });

        if (!response.ok) throw new Error(`HTTP ${response.status}`);

        const result = await response.json();
        showToast('Self-improvement session started', 'success');

        if (result.session_id) {
            SelfImprovement.activeSessionId = result.session_id;
            SelfImprovement.startStreaming(result.session_id);
        }

        await SelfImprovement.loadActiveSession();

    } catch (error) {
        console.error('Failed to start self-improve from correction:', error);
        showToast(`Failed to start: ${error.message}`, 'error');
    }
};

Phase 3: Full CLI Output Display (2-3 hours)
3.1 Capture Complete CLI Output
File: src/barnabeenet/agents/self_improvement.py
Modify the streaming to capture raw stdout/stderr:
python# In the improve() method, where Claude CLI is spawned:

# Store raw CLI output separately from parsed events
session.raw_cli_output = []

# When reading from process
async def read_stream(stream, is_stderr=False):
    """Read stream and capture raw output."""
    async for line in stream:
        decoded = line.decode('utf-8', errors='replace')

        # Store raw output for display
        session.raw_cli_output.append({
            'timestamp': datetime.now().isoformat(),
            'stream': 'stderr' if is_stderr else 'stdout',
            'line': decoded.rstrip()
        })

        # Emit raw line event for dashboard
        await self._emit_progress(session, "cli_output", {
            "line": decoded.rstrip(),
            "stream": "stderr" if is_stderr else "stdout",
            "timestamp": datetime.now().isoformat()
        })

        # Also yield for API streaming
        yield {
            "event": "cli_output",
            "line": decoded.rstrip(),
            "stream": "stderr" if is_stderr else "stdout"
        }

        # Continue with existing JSON parsing for tool calls, etc.
        if decoded.strip():
            try:
                event_data = json.loads(decoded)
                # ... existing parsing logic ...
3.2 Dashboard Full CLI View
File: src/barnabeenet/static/index.html
Replace the current CLI output section with a full terminal view:
html<!-- CLI Output Section - Full Terminal -->
<div class="si-section si-cli-full">
    <div class="si-section-header">
        <h4>💻 Claude Code CLI Output</h4>
        <div class="cli-controls">
            <label class="toggle-label">
                <input type="checkbox" id="cli-auto-scroll" checked>
                Auto-scroll
            </label>
            <label class="toggle-label">
                <input type="checkbox" id="cli-show-stderr" checked>
                Show stderr
            </label>
            <button class="btn btn-sm" onclick="SelfImprovement.clearCLI()">Clear</button>
            <button class="btn btn-sm" onclick="SelfImprovement.copyCLI()">Copy All</button>
        </div>
    </div>
    <div class="cli-terminal" id="cli-terminal">
        <pre id="cli-output"></pre>
    </div>
</div>
File: src/barnabeenet/static/style.css
css/* Full CLI Terminal Styles */
.si-cli-full {
    flex: 1;
    display: flex;
    flex-direction: column;
    min-height: 400px;
}

.cli-terminal {
    flex: 1;
    background: #0d1117;
    border-radius: 6px;
    overflow: auto;
    font-family: 'JetBrains Mono', 'Fira Code', 'Consolas', monospace;
    font-size: 12px;
    line-height: 1.5;
}

#cli-output {
    padding: 1rem;
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
}

.cli-line {
    display: block;
}

.cli-line.stdout {
    color: #c9d1d9;
}

.cli-line.stderr {
    color: #f97583;
}

.cli-line.json-event {
    color: #79c0ff;
}

.cli-timestamp {
    color: #6e7681;
    margin-right: 0.5rem;
    font-size: 10px;
}

.cli-controls {
    display: flex;
    gap: 1rem;
    align-items: center;
}
File: src/barnabeenet/static/app.js
javascript// In SelfImprovement object, add CLI handling:

const SelfImprovement = {
    // ... existing properties ...
    cliOutput: [],

    handleCliOutput(data) {
        const output = document.getElementById('cli-output');
        if (!output) return;

        const showStderr = document.getElementById('cli-show-stderr')?.checked ?? true;

        if (data.stream === 'stderr' && !showStderr) return;

        // Store for copy function
        this.cliOutput.push(data);

        // Create line element
        const line = document.createElement('span');
        line.className = `cli-line ${data.stream}`;

        // Optional timestamp
        const timestamp = document.createElement('span');
        timestamp.className = 'cli-timestamp';
        timestamp.textContent = new Date(data.timestamp).toLocaleTimeString();

        line.appendChild(timestamp);
        line.appendChild(document.createTextNode(data.line));

        output.appendChild(line);
        output.appendChild(document.createTextNode('\n'));

        // Limit lines
        while (output.children.length > 2000) {
            output.removeChild(output.firstChild);
            output.removeChild(output.firstChild); // Remove the newline too
        }

        // Auto-scroll
        if (document.getElementById('cli-auto-scroll')?.checked) {
            const terminal = document.querySelector('.cli-terminal');
            terminal.scrollTop = terminal.scrollHeight;
        }
    },

    clearCLI() {
        document.getElementById('cli-output').innerHTML = '';
        this.cliOutput = [];
    },

    copyCLI() {
        const text = this.cliOutput.map(d => `[${d.stream}] ${d.line}`).join('\n');
        navigator.clipboard.writeText(text);
        showToast('CLI output copied to clipboard', 'success');
    },

    // Modify handleStreamEvent to route cli_output events:
    handleStreamEvent(event) {
        // ... existing handling ...

        if (event.event === 'cli_output') {
            this.handleCliOutput(event);
        }

        // ... rest of handling ...
    }
};

Phase 4: Timeline & Action Required Banner (3-4 hours)
4.1 Timeline Component
File: src/barnabeenet/static/index.html
Add timeline at top of self-improve page:
html<!-- Self-Improve Page -->
<div id="page-self-improve" class="page">
    <!-- Action Required Banner (sticky at top) -->
    <div id="si-action-required" class="si-action-required hidden">
        <div class="action-banner">
            <span class="action-icon">⚠️</span>
            <span class="action-title" id="action-required-title">Action Required</span>
            <span class="action-description" id="action-required-description"></span>
            <div class="action-buttons" id="action-required-buttons"></div>
        </div>
    </div>

    <!-- Progress Timeline -->
    <div class="si-timeline-container">
        <div class="si-timeline" id="si-timeline">
            <div class="timeline-step" data-step="started">
                <div class="step-dot"></div>
                <div class="step-label">Started</div>
            </div>
            <div class="timeline-connector"></div>
            <div class="timeline-step" data-step="diagnosing">
                <div class="step-dot"></div>
                <div class="step-label">Diagnosing</div>
            </div>
            <div class="timeline-connector"></div>
            <div class="timeline-step" data-step="plan_approval">
                <div class="step-dot"></div>
                <div class="step-label">Plan Review</div>
            </div>
            <div class="timeline-connector"></div>
            <div class="timeline-step" data-step="implementing">
                <div class="step-dot"></div>
                <div class="step-label">Implementing</div>
            </div>
            <div class="timeline-connector"></div>
            <div class="timeline-step" data-step="testing">
                <div class="step-dot"></div>
                <div class="step-label">Testing</div>
            </div>
            <div class="timeline-connector"></div>
            <div class="timeline-step" data-step="commit_approval">
                <div class="step-dot"></div>
                <div class="step-label">Commit</div>
            </div>
            <div class="timeline-connector"></div>
            <div class="timeline-step" data-step="completed">
                <div class="step-dot"></div>
                <div class="step-label">Done</div>
            </div>
        </div>
    </div>

    <!-- Rest of page content -->
    <div class="page-header">
        <h1>🔧 Self-Improvement Agent</h1>
        <!-- ... -->
    </div>
File: src/barnabeenet/static/style.css
css/* Action Required Banner */
.si-action-required {
    position: sticky;
    top: 60px; /* Below navbar */
    z-index: 100;
    padding: 0.75rem 1rem;
    background: linear-gradient(135deg, #f59e0b 0%, #d97706 100%);
    border-radius: 8px;
    margin-bottom: 1rem;
    animation: pulse-attention 2s infinite;
}

.si-action-required.hidden {
    display: none;
}

.action-banner {
    display: flex;
    align-items: center;
    gap: 1rem;
    flex-wrap: wrap;
}

.action-icon {
    font-size: 1.5rem;
}

.action-title {
    font-weight: 600;
    color: #1f2937;
}

.action-description {
    flex: 1;
    color: #374151;
}

.action-buttons {
    display: flex;
    gap: 0.5rem;
}

@keyframes pulse-attention {
    0%, 100% { opacity: 1; }
    50% { opacity: 0.85; }
}

/* Timeline */
.si-timeline-container {
    padding: 1rem;
    background: var(--bg-card);
    border-radius: 8px;
    margin-bottom: 1rem;
    overflow-x: auto;
}

.si-timeline {
    display: flex;
    align-items: center;
    justify-content: space-between;
    min-width: 600px;
}

.timeline-step {
    display: flex;
    flex-direction: column;
    align-items: center;
    gap: 0.5rem;
}

.step-dot {
    width: 24px;
    height: 24px;
    border-radius: 50%;
    background: var(--bg-secondary);
    border: 3px solid var(--border-color);
    transition: all 0.3s;
}

.timeline-step.completed .step-dot {
    background: var(--accent-success);
    border-color: var(--accent-success);
}

.timeline-step.active .step-dot {
    background: var(--accent-primary);
    border-color: var(--accent-primary);
    animation: pulse-dot 1.5s infinite;
}

.timeline-step.needs-attention .step-dot {
    background: var(--accent-warning);
    border-color: var(--accent-warning);
    animation: pulse-dot 1s infinite;
}

.timeline-step.failed .step-dot {
    background: var(--accent-error);
    border-color: var(--accent-error);
}

.step-label {
    font-size: 0.75rem;
    color: var(--text-secondary);
    white-space: nowrap;
}

.timeline-step.active .step-label,
.timeline-step.completed .step-label {
    color: var(--text-primary);
    font-weight: 500;
}

.timeline-connector {
    flex: 1;
    height: 3px;
    background: var(--border-color);
    min-width: 20px;
}

.timeline-connector.completed {
    background: var(--accent-success);
}

@keyframes pulse-dot {
    0%, 100% { transform: scale(1); }
    50% { transform: scale(1.2); }
}
File: src/barnabeenet/static/app.js
javascript// Add timeline management to SelfImprovement:

const SelfImprovement = {
    // ... existing code ...

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

    showActionRequired(type, session) {
        const banner = document.getElementById('si-action-required');
        const title = document.getElementById('action-required-title');
        const desc = document.getElementById('action-required-description');
        const buttons = document.getElementById('action-required-buttons');

        banner.classList.remove('hidden');

        switch(type) {
            case 'plan_approval':
                title.textContent = '📋 Plan Review Required';
                desc.textContent = 'Claude has proposed a plan. Review and approve or reject.';
                buttons.innerHTML = `
                    <button class="btn btn-success" onclick="SelfImprovement.approvePlan()">✓ Approve Plan</button>
                    <button class="btn btn-danger" onclick="SelfImprovement.rejectPlan()">✗ Reject</button>
                    <button class="btn btn-secondary" onclick="SelfImprovement.scrollToPlan()">View Plan ↓</button>
                `;
                break;

            case 'details_needed':
                title.textContent = '❓ Additional Details Needed';
                desc.textContent = 'Claude needs more information to proceed.';
                buttons.innerHTML = `
                    <button class="btn btn-primary" onclick="SelfImprovement.scrollToInput()">Provide Details ↓</button>
                `;
                break;

            case 'commit_approval':
                title.textContent = '✅ Ready to Commit';
                desc.textContent = `Changes ready: ${session.files_modified?.length || 0} files modified`;
                buttons.innerHTML = `
                    <button class="btn btn-success" onclick="SelfImprovement.approveCommit()">✓ Commit Changes</button>
                    <button class="btn btn-danger" onclick="SelfImprovement.rejectCommit()">✗ Reject</button>
                    <button class="btn btn-secondary" onclick="SelfImprovement.viewDiff()">View Diff ↓</button>
                `;
                break;

            default:
                banner.classList.add('hidden');
        }
    },

    hideActionRequired() {
        document.getElementById('si-action-required')?.classList.add('hidden');
    },

    // Update existing status handler:
    handleStatusChange(status, session) {
        this.updateTimeline(status);

        if (status === 'awaiting_plan_approval') {
            this.showActionRequired('plan_approval', session);
        } else if (status === 'awaiting_approval') {
            this.showActionRequired('commit_approval', session);
        } else {
            this.hideActionRequired();
        }
    }
};

Phase 5: Enhanced Notifications (1-2 hours)
5.1 Comprehensive Notification Triggers
File: src/barnabeenet/agents/self_improvement.py
Enhance the notification triggers:
python# Add notification method for each phase transition

async def _notify_phase_change(
    self,
    session: ImprovementSession,
    phase: str,
    requires_attention: bool = False
) -> None:
    """Send notification for phase changes."""

    phase_messages = {
        "started": ("🚀 Self-Improvement Started", f"Working on: {session.request[:60]}..."),
        "diagnosing": ("🔍 Diagnosing Issue", "Analyzing logs and code..."),
        "plan_proposed": ("📋 Plan Ready for Review", f"Review required: {session.request[:40]}..."),
        "plan_auto_approved": ("✅ Plan Auto-Approved", f"Safety score passed - implementing: {session.request[:40]}..."),
        "implementing": ("⚙️ Implementing Changes", "Claude is writing code..."),
        "testing": ("🧪 Running Tests", "Verifying changes..."),
        "awaiting_commit": ("✅ Ready to Commit", f"Review {len(session.files_modified)} changed files"),
        "committed": ("🎉 Changes Committed", f"Successfully improved: {session.request[:40]}..."),
        "failed": ("❌ Improvement Failed", session.error or "Unknown error"),
        "stopped": ("⏹ Session Stopped", "User stopped the session"),
    }

    if phase not in phase_messages:
        return

    title, message = phase_messages[phase]

    # Add action URL for phases requiring attention
    data = {}
    if requires_attention:
        title = f"⚠️ {title}"
        data["clickAction"] = f"http://192.168.86.51:8000/?page=self-improve&session={session.session_id}"
        data["priority"] = "high"
        data["ttl"] = 0  # Deliver immediately
        data["tag"] = f"si-{session.session_id}"  # Replace previous notifications for same session

    await self._send_notification(title, message, data)
Update all phase transitions to call _notify_phase_change:
python# In the improve() method, at each phase transition:

# When plan is proposed:
await self._notify_phase_change(session, "plan_proposed", requires_attention=True)

# When awaiting commit:
await self._notify_phase_change(session, "awaiting_commit", requires_attention=True)

# When completed:
await self._notify_phase_change(session, "committed", requires_attention=False)

# Etc for all phases...

Phase 6: Model Configuration - opusplan Default (30 min)
6.1 Default to opusplan
File: src/barnabeenet/agents/self_improvement.py
pythonasync def improve(
    self,
    request: str,
    model: str = "opusplan",  # CHANGED: Default to opusplan
    auto_approve: bool = False,
    max_turns: int = 50,
) -> AsyncIterator[dict[str, Any]]:
File: src/barnabeenet/static/index.html
Update the modal radio buttons:
html<div class="si-model-selection">
    <label class="radio-option">
        <input type="radio" name="si-model" value="opusplan" checked>
        <span>🔄 Auto (opusplan) - Opus for planning, Sonnet for implementation</span>
    </label>
    <label class="radio-option">
        <input type="radio" name="si-model" value="opus">
        <span>🧠 Opus 4.5 - Best reasoning (slower, uses more quota)</span>
    </label>
    <label class="radio-option">
        <input type="radio" name="si-model" value="sonnet">
        <span>⚡ Sonnet 4.5 - Fast and capable</span>
    </label>
</div>
File: src/barnabeenet/api/routes/self_improve.py
pythonclass ImproveRequest(BaseModel):
    """Request to start an improvement."""
    request: str
    model: str = "opusplan"  # CHANGED: Default to opusplan
    auto_approve: bool = False
    source: str | None = None  # "chat", "mark_as_wrong", "direct"
    trace_id: str | None = None  # If from mark_as_wrong

Phase 7: API Enhancements (1-2 hours)
7.1 Add Source Tracking
File: src/barnabeenet/api/routes/self_improve.py
python@router.post("/improve")
async def start_improvement(request: ImproveRequest):
    """Start a new self-improvement session."""
    agent = get_self_improvement_agent()

    if not agent.is_available():
        raise HTTPException(status_code=503, detail="Claude Code CLI not available")

    # Start the improvement with source tracking
    session_id = None

    async def run_improvement():
        nonlocal session_id
        async for event in agent.improve(
            request=request.request,
            model=request.model,
            auto_approve=request.auto_approve,
            source=request.source,  # Track where request came from
            trace_id=request.trace_id,  # Link to original trace if from mark_as_wrong
        ):
            if event.get("event") == "started":
                session_id = event.get("session_id")
            # Events broadcast via Redis

    asyncio.create_task(run_improvement())

    # Wait briefly for session to initialize
    await asyncio.sleep(0.5)

    return {
        "status": "started",
        "session_id": session_id,
        "source": request.source,
    }
7.2 Add CLI Output Endpoint
File: src/barnabeenet/api/routes/self_improve.py
python@router.get("/sessions/{session_id}/cli-output")
async def get_cli_output(session_id: str, limit: int = 500):
    """Get raw CLI output for a session."""
    agent = get_self_improvement_agent()
    session = agent.active_sessions.get(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    output = getattr(session, 'raw_cli_output', [])

    return {
        "session_id": session_id,
        "output": output[-limit:] if len(output) > limit else output,
        "total_lines": len(output),
        "truncated": len(output) > limit,
    }
```

---

## Implementation Order for GitHub Copilot

Execute phases in this order for optimal incremental progress:
```
1. Phase 6: Model Configuration (opusplan default) - 30 min
   - Quick win, low risk
   - Changes: self_improvement.py, index.html, self_improve.py route

2. Phase 5: Enhanced Notifications - 1-2 hours
   - Builds on existing notification infrastructure
   - Immediate user value (phone notifications work)
   - Changes: self_improvement.py only

3. Phase 1: Home Page Integration - 3-4 hours
   - Improves visibility
   - Changes: self_improvement.py, app.js, index.html, style.css

4. Phase 4: Timeline & Action Banner - 3-4 hours
   - Visual improvements to dedicated page
   - Changes: index.html, style.css, app.js

5. Phase 3: Full CLI Output - 2-3 hours
   - Improves debugging capability
   - Changes: self_improvement.py, index.html, style.css, app.js

6. Phase 2: Entry Point Integration - 2-3 hours
   - Last because it connects multiple systems
   - Changes: index.html, app.js

7. Phase 7: API Enhancements - 1-2 hours
   - Cleanup and polish
   - Changes: self_improve.py routes

Files Modified Summary
FilePhasesChangessrc/barnabeenet/agents/self_improvement.py1,3,5,6Activity logging, CLI capture, notifications, opusplan defaultsrc/barnabeenet/api/routes/self_improve.py6,7Model default, source tracking, CLI endpointsrc/barnabeenet/static/index.html1,2,3,4,6Dashboard cards, timeline, action banner, CLI terminal, model optionssrc/barnabeenet/static/style.css3,4Timeline styles, CLI terminal styles, action bannersrc/barnabeenet/static/app.js1,2,3,4Activity click handling, timeline management, CLI rendering, entry points

Testing Checklist
After implementation, verify:

 Self-improve sessions appear in home page activity feed
 Clicking activity item navigates to session
 "Fix This" button in chat starts self-improve with context
 "Fix with Self-Improve" button in correction modal works
 Timeline shows correct progress state
 Action Required banner appears for plan approval
 Action Required banner appears for commit approval
 Full CLI output displays in terminal view
 Phone notifications arrive at each phase
 Phone notifications arrive when attention needed
 opusplan is default model selection
 Auto-approve works for high safety score plans
