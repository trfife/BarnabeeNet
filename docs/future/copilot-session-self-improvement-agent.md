# Copilot Session: Self-Improvement Agent Implementation

**Session ID:** self-improvement-agent-001
**Date:** 2026-01-20
**Priority:** High
**Estimated Time:** 4-6 hours (can be split across sessions)

---

## Overview

Implement a **Self-Improvement Agent** for BarnabeeNet that uses **Claude Code** (via subscription authentication) to autonomously improve its own codebase. The agent must:

1. Accept improvement requests via voice or API
2. Execute code changes using Claude Code CLI
3. Track all operations for dashboard visualization
4. Calculate equivalent API costs for comparison reporting
5. Manage git operations with approval workflow

---

## Architecture Decision: Where This Runs

### Primary Host: BarnabeeNet Server (NixOS VM)

The Self-Improvement Agent runs on the BarnabeeNet server, **not** Man-of-war WSL. Rationale:

| Factor | BarnabeeNet Server | Man-of-war WSL |
|--------|-------------------|----------------|
| **Code location** | ✅ Native - code lives here | ❌ Would need SSH/mount |
| **Git operations** | ✅ Local, instant | ❌ Network latency |
| **File I/O** | ✅ Direct filesystem | ❌ Remote/mounted |
| **GPU needed?** | ❌ No - Claude Code is remote inference | ✅ Only for STT/TTS |
| **Service restarts** | ✅ Can restart itself | ❌ Would need SSH |
| **Part of BarnabeeNet** | ✅ Uses Redis, FastAPI, dashboard | ❌ Would fragment system |

**Claude Code is a remote tool** - when you run `claude` commands, inference happens on Anthropic's servers. Your RTX 4070 Ti on Man-of-war is irrelevant for Claude Code operations.

### When Man-of-war Is Involved

SSH to Man-of-war only when genuinely needed:
- **GPU service management** - restarting Parakeet TDT, Kokoro, or ECAPA-TDNN
- **GPU config verification** - testing changes that affect CUDA workloads
- **Performance testing** - validating STT/TTS latency after code changes

```
┌─────────────────────────────────────────────────────────────────┐
│ BarnabeeNet Server (192.168.86.51 - NixOS VM)                   │
│                                                                 │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ Self-Improvement Agent                                   │   │
│  │  • Claude Code CLI (Max subscription auth)               │   │
│  │  • Direct git operations (local repo)                    │   │
│  │  • Direct file read/write                                │   │
│  │  • Redis event streaming → Dashboard                     │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                           ▼                                     │
│  ┌─────────────────────────────────────────────────────────┐   │
│  │ FastAPI + Dashboard + Redis                              │   │
│  └─────────────────────────────────────────────────────────┘   │
│                           │                                     │
│                    SSH (when needed)                            │
│                           ▼                                     │
└───────────────────────────┼─────────────────────────────────────┘
                            │
                            ▼
┌─────────────────────────────────────────────────────────────────┐
│ Man-of-war (Windows 11 / WSL2)                                  │
│                                                                 │
│  • RTX 4070 Ti GPU inference (Parakeet TDT, Kokoro, ECAPA)     │
│  • VS Code + GitHub Copilot (interactive development)           │
│  • CUDA acceleration endpoint                                   │
└─────────────────────────────────────────────────────────────────┘
```

---

## Log Access for Debugging

Claude Code needs access to runtime logs and traces to debug issues like "that chat didn't work." BarnabeeNet has comprehensive observability infrastructure that should be exposed to the Self-Improvement Agent.

### Available Log Sources

| Source | Location/Access | Contains |
|--------|-----------------|----------|
| **Activity Stream** | Redis: `barnabeenet:activity:stream` | All system activities (user input, agent decisions, HA events, LLM calls) |
| **Conversation Traces** | API: `/api/v1/activity/traces` | Linked reasoning chains (input → classify → route → response) |
| **LLM Signal Logs** | Redis: `barnabeenet:signals:*` | Every LLM request/response with tokens, latency, cost |
| **Application Logs** | `journalctl -u barnabeenet` | Python logging output, errors, warnings |
| **HA Error Log** | API: HAClient.get_error_log() | Home Assistant errors and warnings |
| **Metrics History** | Prometheus / API | Latency percentiles, request counts, error rates |

### Helper Script for Claude Code

Create a helper script that Claude Code can use to query logs without needing to know the internals:

**File:** `scripts/debug-logs.sh`

```bash
#!/usr/bin/env bash
# Debug log helper for Self-Improvement Agent
# Usage: ./scripts/debug-logs.sh <command> [args]

set -euo pipefail

API_BASE="${BARNABEENET_API:-http://localhost:8000}"
REDIS_URL="${REDIS_URL:-redis://localhost:6379}"

case "${1:-help}" in
    # Get recent activity feed
    activity)
        limit="${2:-50}"
        curl -s "$API_BASE/api/v1/activity/feed?limit=$limit" | jq '.activities[] | {timestamp, type, source, title, level}'
        ;;

    # Get recent conversation traces
    traces)
        limit="${2:-10}"
        curl -s "$API_BASE/api/v1/activity/traces?limit=$limit" | jq '.traces[] | {trace_id, started_at, input: .input[:80], final_response: .final_response[:80], total_latency_ms}'
        ;;

    # Get specific trace with full reasoning chain
    trace)
        trace_id="$2"
        curl -s "$API_BASE/api/v1/activity/traces/$trace_id" | jq '.'
        ;;

    # Get recent errors from activity log
    errors)
        limit="${2:-20}"
        curl -s "$API_BASE/api/v1/activity/feed?limit=500&level=error" | jq ".activities[:$limit]"
        ;;

    # Get LLM call history (recent signals)
    llm-calls)
        limit="${2:-20}"
        redis-cli -u "$REDIS_URL" XREVRANGE barnabeenet:signals:llm + - COUNT "$limit" | head -100
        ;;

    # Get activity stream (raw Redis)
    stream)
        limit="${2:-50}"
        redis-cli -u "$REDIS_URL" XREVRANGE barnabeenet:activity:stream + - COUNT "$limit"
        ;;

    # Search activity by type (e.g., "agent.decision", "llm.error")
    search)
        activity_type="$2"
        limit="${3:-50}"
        curl -s "$API_BASE/api/v1/activity/feed?limit=$limit&types=$activity_type" | jq '.activities'
        ;;

    # Get HA error log
    ha-errors)
        curl -s "$API_BASE/api/v1/ha/error-log" | jq '.'
        ;;

    # Get system journal logs
    journal)
        lines="${2:-100}"
        journalctl -u barnabeenet --no-pager -n "$lines"
        ;;

    # Get journal errors only
    journal-errors)
        lines="${2:-50}"
        journalctl -u barnabeenet --no-pager -n 500 -p err | head -n "$lines"
        ;;

    # Get pipeline stats
    stats)
        curl -s "$API_BASE/api/v1/dashboard/stats" | jq '.'
        ;;

    # Get latency history for component
    latency)
        component="${2:-stt}"
        minutes="${3:-60}"
        curl -s "$API_BASE/api/v1/dashboard/latency/$component?window_minutes=$minutes" | jq '.'
        ;;

    # Tail activity stream in real-time (requires wscat or websocat)
    tail)
        echo "Connecting to activity WebSocket..."
        websocat "ws://${API_BASE#http://}/ws/activity" || \
        wscat -c "ws://${API_BASE#http://}/ws/activity"
        ;;

    help|*)
        cat <<EOF
BarnabeeNet Debug Log Helper

Usage: ./scripts/debug-logs.sh <command> [args]

Commands:
  activity [limit]           Get recent activity feed (default: 50)
  traces [limit]             Get recent conversation traces (default: 10)
  trace <trace_id>           Get specific trace with full reasoning chain
  errors [limit]             Get recent errors (default: 20)
  llm-calls [limit]          Get recent LLM calls from Redis (default: 20)
  stream [limit]             Get raw activity stream from Redis (default: 50)
  search <type> [limit]      Search by activity type (e.g., "agent.decision")
  ha-errors                  Get Home Assistant error log
  journal [lines]            Get systemd journal logs (default: 100)
  journal-errors [lines]     Get journal errors only (default: 50)
  stats                      Get pipeline statistics
  latency <component> [min]  Get latency history (stt|tts|llm, default: 60 min)
  tail                       Tail activity stream in real-time (WebSocket)

Activity Types:
  user.input, user.voice, agent.thinking, agent.decision, agent.response,
  meta.classify, meta.route, instant.match, action.parse, action.execute,
  interaction.respond, memory.search, memory.store, llm.request, llm.response,
  llm.error, ha.state_change, ha.service_call, system.error

Examples:
  ./scripts/debug-logs.sh traces 5                    # Last 5 conversations
  ./scripts/debug-logs.sh trace abc123                # Full trace details
  ./scripts/debug-logs.sh search llm.error 10        # Recent LLM errors
  ./scripts/debug-logs.sh errors                      # Recent system errors
EOF
        ;;
esac
```

### Updated System Prompt for Claude Code

The system prompt should tell Claude Code about these debugging resources:

```python
system_prompt = """You are improving the BarnabeeNet smart home AI system.

SAFETY RULES (MUST FOLLOW):
- Do NOT modify files in: secrets/, .env, infrastructure/secrets/
- Do NOT run: rm -rf, sudo, chmod 777, or pipe curl/wget to shell
- Do NOT modify authentication, permissions, or security code
- Do NOT change privacy zone configurations

DEBUGGING RESOURCES:
When investigating issues, use these tools to understand what happened:

1. **Conversation Traces** - See the full reasoning chain for any interaction:
   ./scripts/debug-logs.sh traces 10        # Recent conversations
   ./scripts/debug-logs.sh trace <trace_id> # Specific conversation

2. **Activity Feed** - All system events (agent decisions, LLM calls, HA events):
   ./scripts/debug-logs.sh activity 50      # Recent activities
   ./scripts/debug-logs.sh search llm.error # Search by type

3. **Error Logs** - Find what went wrong:
   ./scripts/debug-logs.sh errors           # Activity log errors
   ./scripts/debug-logs.sh journal-errors   # System journal errors
   ./scripts/debug-logs.sh ha-errors        # Home Assistant errors

4. **LLM Call History** - Token usage, latency, responses:
   ./scripts/debug-logs.sh llm-calls 20

5. **Pipeline Stats** - Latency percentiles, request counts:
   ./scripts/debug-logs.sh stats
   ./scripts/debug-logs.sh latency stt 60

6. **Direct API Access**:
   curl http://localhost:8000/api/v1/activity/feed?limit=50
   curl http://localhost:8000/api/v1/activity/traces
   curl http://localhost:8000/api/v1/dashboard/stats

KEY LOG LOCATIONS:
- Activity stream: Redis key 'barnabeenet:activity:stream'
- LLM signals: Redis keys 'barnabeenet:signals:*'
- App logs: journalctl -u barnabeenet
- Source code: /home/thom/barnabeenet/

ACTIVITY TYPES (for searching):
- user.input, user.voice - User interactions
- meta.classify, meta.route - Intent classification
- agent.decision, agent.response - Agent reasoning
- action.parse, action.execute - Device control
- llm.request, llm.response, llm.error - LLM calls
- ha.state_change, ha.service_call - Home Assistant
- system.error - System errors

WORKFLOW:
1. First, understand the issue by checking logs
2. Find the relevant code
3. Make minimal, targeted changes
4. Add or update tests for your changes
5. Run tests to verify: pytest tests/ -v
6. If tests fail, fix the issues

Always explain what you're doing before each action."""
```

### Log Access in Agent Code

Update the agent to include the debug script path:

```python
class SelfImprovementAgent:
    """Agent that uses Claude Code to improve BarnabeeNet's codebase."""

    # ... existing code ...

    # Debug resources
    DEBUG_SCRIPT = "scripts/debug-logs.sh"

    ALLOWED_DEBUG_COMMANDS = [
        "activity", "traces", "trace", "errors", "llm-calls",
        "stream", "search", "ha-errors", "journal", "journal-errors",
        "stats", "latency",
    ]
```

### Example Debugging Flow

When a user says "that last chat didn't work, look into it":

1. **Claude Code runs:** `./scripts/debug-logs.sh traces 5`
2. **Sees the failed trace** with trace_id `abc123`
3. **Gets full details:** `./scripts/debug-logs.sh trace abc123`
4. **Sees the error** in the reasoning chain (e.g., LLM timeout, action parsing failure)
5. **Searches for related errors:** `./scripts/debug-logs.sh search llm.error 10`
6. **Finds the root cause** (e.g., malformed prompt, missing context)
7. **Locates the relevant code** and implements a fix
8. **Adds a test** to prevent regression
9. **Runs tests** to verify the fix

---

## Prerequisites

**All setup happens on the BarnabeeNet server:**

```bash
# SSH to BarnabeeNet server
ssh thom@192.168.86.51

# Verify Node.js is available (required for Claude Code)
node --version  # Should be 18+

# If Node.js not available, add to NixOS configuration:
# environment.systemPackages = with pkgs; [ nodejs_20 ];
# Then: sudo nixos-rebuild switch

# Install Claude Code CLI
npm install -g @anthropic-ai/claude-code

# Verify installation
which claude  # Should show path like /home/thom/.npm-global/bin/claude
claude --version

# Login with Max subscription (NOT API key)
claude login
# Select your Max subscription account in browser
# Complete OAuth flow

# Verify subscription auth (NOT API credits)
claude
/status
# Should show "Subscription: Max" or similar, NOT API credit balance
```

**CRITICAL:** Do NOT set `ANTHROPIC_API_KEY` environment variable on the BarnabeeNet server. This would cause API billing instead of using the subscription.

### Optional: SSH Key Setup for Man-of-war

If the agent needs to manage GPU services:

```bash
# On BarnabeeNet server, generate key if not exists
ssh-keygen -t ed25519 -C "barnabeenet-agent"

# Copy to Man-of-war (do this once)
ssh-copy-id thom@man-of-war

# Test connection
ssh thom@man-of-war "echo 'Connection successful'"
```

---

## Phase 1: Core Agent Infrastructure

### 1.1 Create the Self-Improvement Agent Module

**File:** `src/barnabeenet/agents/self_improvement.py`

```python
"""Self-Improvement Agent using Claude Code.

This agent can modify BarnabeeNet's own codebase through voice commands
or API requests. Uses Claude Code CLI with Max subscription authentication.

Architecture:
- Runs on BarnabeeNet server (where the code lives)
- Receives improvement requests from Meta Agent or direct API
- Spawns Claude Code sessions in headless mode
- Streams progress to dashboard via Redis
- Tracks costs for comparison reporting
- Manages git operations with approval workflow
- SSHs to Man-of-war only when GPU management is needed
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import re
import subprocess
import time
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Any, AsyncIterator, Callable

import structlog

from barnabeenet.services.message_bus import MessageBus, get_message_bus

logger = structlog.get_logger(__name__)


class ImprovementStatus(str, Enum):
    """Status of an improvement request."""
    PENDING = "pending"
    DIAGNOSING = "diagnosing"          # Checking logs, understanding issue
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"  # User must approve plan
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    AWAITING_APPROVAL = "awaiting_approval"  # User must approve code changes
    COMMITTING = "committing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    STOPPED = "stopped"                 # User stopped the session


@dataclass
class TokenUsage:
    """Track token usage for cost calculation."""
    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def add(self, other: "TokenUsage") -> None:
        """Add another TokenUsage to this one."""
        self.input_tokens += other.input_tokens
        self.output_tokens += other.output_tokens
        self.cache_read_tokens += other.cache_read_tokens
        self.cache_write_tokens += other.cache_write_tokens

    def calculate_api_cost(self, model: str = "claude-sonnet-4-5") -> float:
        """Calculate what this would cost via API.

        Pricing (per 1M tokens):
        - Sonnet 4.5: $3 input, $15 output
        - Opus 4.5: $15 input, $75 output
        - Cache read: 10% of input cost
        - Cache write: 125% of input cost
        """
        if "opus" in model.lower():
            input_rate = 15.0 / 1_000_000
            output_rate = 75.0 / 1_000_000
        else:  # sonnet
            input_rate = 3.0 / 1_000_000
            output_rate = 15.0 / 1_000_000

        cache_read_rate = input_rate * 0.1
        cache_write_rate = input_rate * 1.25

        cost = (
            self.input_tokens * input_rate +
            self.output_tokens * output_rate +
            self.cache_read_tokens * cache_read_rate +
            self.cache_write_tokens * cache_write_rate
        )
        return round(cost, 6)


@dataclass
class ClaudeCodeOperation:
    """Record of a single Claude Code operation."""
    operation_id: str
    timestamp: datetime
    operation_type: str  # "bash", "read", "write", "edit", "grep", "glob"
    command: str | None = None
    file_path: str | None = None
    content_preview: str | None = None
    duration_ms: float = 0
    success: bool = True
    error: str | None = None


@dataclass
class ImprovementSession:
    """A complete improvement session."""
    session_id: str
    request: str
    status: ImprovementStatus = ImprovementStatus.PENDING
    started_at: datetime = field(default_factory=datetime.now)
    completed_at: datetime | None = None

    # Progress tracking
    operations: list[ClaudeCodeOperation] = field(default_factory=list)
    messages: list[dict[str, Any]] = field(default_factory=list)

    # Cost tracking
    token_usage: TokenUsage = field(default_factory=TokenUsage)
    model_used: str = "claude-sonnet-4-5"

    # Git tracking
    files_modified: list[str] = field(default_factory=list)
    git_diff: str | None = None
    commit_hash: str | None = None
    branch_name: str | None = None

    # Results
    success: bool = False
    error: str | None = None
    summary: str | None = None

    # Interactive session control
    proposed_plan: dict[str, Any] | None = None  # Parsed <PLAN> block
    user_input_queue: asyncio.Queue = field(default_factory=asyncio.Queue)
    stop_requested: bool = False
    current_thinking: str = ""  # Live thinking/reasoning text

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "request": self.request,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "operations_count": len(self.operations),
            "messages_count": len(self.messages),
            "token_usage": {
                "input": self.token_usage.input_tokens,
                "output": self.token_usage.output_tokens,
                "cache_read": self.token_usage.cache_read_tokens,
                "cache_write": self.token_usage.cache_write_tokens,
            },
            "estimated_api_cost_usd": self.token_usage.calculate_api_cost(self.model_used),
            "model_used": self.model_used,
            "files_modified": self.files_modified,
            "git_diff_lines": len(self.git_diff.splitlines()) if self.git_diff else 0,
            "commit_hash": self.commit_hash,
            "branch_name": self.branch_name,
            "success": self.success,
            "error": self.error,
            "summary": self.summary,
            "proposed_plan": self.proposed_plan,
            "current_thinking": self.current_thinking,
            "stop_requested": self.stop_requested,
        }


class SelfImprovementAgent:
    """Agent that uses Claude Code to improve BarnabeeNet's codebase.

    This agent:
    1. Receives improvement requests
    2. Creates a feature branch
    3. Runs Claude Code in headless mode
    4. Streams progress to dashboard
    5. Waits for approval before committing
    6. Tracks costs for comparison

    Safety boundaries (from Evolver Agent design):
    - ALLOWED: prompt optimization, routing rules, configuration tuning
    - FORBIDDEN: external API changes, security modifications, privacy zones
    - REQUIRES_APPROVAL: code changes, new automations
    """

    # Safety boundaries
    FORBIDDEN_PATHS = [
        "secrets",
        ".env",
        "infrastructure/secrets",
        "ha-integration/secrets",
    ]

    FORBIDDEN_OPERATIONS = [
        "rm -rf",
        "sudo",
        "chmod 777",
        "curl | bash",
        "wget | sh",
    ]

    # Man-of-war connection for GPU management
    MANOFWAR_HOST = "thom@man-of-war"

    def __init__(
        self,
        project_path: str | Path,
        message_bus: MessageBus | None = None,
    ):
        self.project_path = Path(project_path)
        self.message_bus = message_bus
        self.active_sessions: dict[str, ImprovementSession] = {}
        self._on_progress_callbacks: list[Callable] = []

        # Verify Claude Code is available
        self._verify_claude_code()

    def _verify_claude_code(self) -> None:
        """Verify Claude Code CLI is installed and authenticated."""
        try:
            result = subprocess.run(
                ["claude", "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode != 0:
                raise RuntimeError("Claude Code CLI not found")
            logger.info("Claude Code CLI verified", version=result.stdout.strip())
        except FileNotFoundError:
            raise RuntimeError(
                "Claude Code CLI not installed. "
                "Run: npm install -g @anthropic-ai/claude-code"
            )

    def _is_safe_operation(self, command: str, file_path: str | None = None) -> bool:
        """Check if an operation is within safety boundaries."""
        # Check forbidden operations
        for forbidden in self.FORBIDDEN_OPERATIONS:
            if forbidden in command.lower():
                logger.warning("Blocked forbidden operation", command=command)
                return False

        # Check forbidden paths
        if file_path:
            for forbidden_path in self.FORBIDDEN_PATHS:
                if forbidden_path in file_path:
                    logger.warning("Blocked forbidden path", path=file_path)
                    return False

        return True

    async def ssh_to_manofwar(self, command: str, timeout: int = 30) -> tuple[bool, str]:
        """Execute a command on Man-of-war via SSH.

        Use this for GPU-related operations like:
        - Restarting Parakeet TDT service
        - Checking GPU memory usage
        - Validating CUDA acceleration

        Args:
            command: Command to execute on Man-of-war
            timeout: Timeout in seconds

        Returns:
            Tuple of (success, output)
        """
        try:
            process = await asyncio.create_subprocess_exec(
                "ssh", self.MANOFWAR_HOST, command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )
            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            success = process.returncode == 0
            output = stdout.decode() if success else stderr.decode()

            logger.info(
                "SSH to Man-of-war",
                command=command,
                success=success,
                output_preview=output[:200],
            )

            return success, output

        except asyncio.TimeoutError:
            logger.error("SSH to Man-of-war timed out", command=command)
            return False, "Timeout"
        except Exception as e:
            logger.error("SSH to Man-of-war failed", command=command, error=str(e))
            return False, str(e)

    async def restart_gpu_service(self, service: str) -> bool:
        """Restart a GPU service on Man-of-war.

        Args:
            service: Service name (e.g., "parakeet-tdt", "kokoro-tts")

        Returns:
            True if successful
        """
        success, output = await self.ssh_to_manofwar(
            f"sudo systemctl restart {service}"
        )
        if success:
            logger.info("Restarted GPU service", service=service)
        return success

    def on_progress(self, callback: Callable) -> None:
        """Register a callback for progress updates."""
        self._on_progress_callbacks.append(callback)

    async def _emit_progress(
        self,
        session: ImprovementSession,
        event_type: str,
        data: dict[str, Any],
    ) -> None:
        """Emit progress update to all listeners."""
        event = {
            "session_id": session.session_id,
            "event_type": event_type,
            "timestamp": datetime.now().isoformat(),
            "status": session.status.value,
            **data,
        }

        # Call registered callbacks
        for callback in self._on_progress_callbacks:
            try:
                if asyncio.iscoroutinefunction(callback):
                    await callback(event)
                else:
                    callback(event)
            except Exception as e:
                logger.error("Progress callback error", error=str(e))

        # Publish to Redis for dashboard
        if self.message_bus:
            await self.message_bus.publish(
                "self_improvement:progress",
                json.dumps(event),
            )

    async def improve(
        self,
        request: str,
        model: str = "sonnet",  # or "opus" for complex tasks
        auto_approve: bool = False,
        max_turns: int = 50,
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute an improvement request.

        Args:
            request: Natural language description of what to improve
            model: Model to use ("sonnet" or "opus")
            auto_approve: If True, commit without approval (dangerous!)
            max_turns: Maximum number of Claude Code turns

        Yields:
            Progress events as dictionaries
        """
        import uuid

        session_id = f"improve-{uuid.uuid4().hex[:8]}"
        session = ImprovementSession(
            session_id=session_id,
            request=request,
            model_used=f"claude-{model}-4-5",
        )
        self.active_sessions[session_id] = session

        try:
            # Phase 1: Create feature branch
            session.status = ImprovementStatus.ANALYZING
            branch_name = f"improve/{session_id}"
            session.branch_name = branch_name

            await self._emit_progress(session, "branch_created", {
                "branch": branch_name,
            })
            yield {"event": "branch_created", "branch": branch_name}

            # Create branch
            await self._run_git_command(["checkout", "-b", branch_name])

            # Phase 2: Run Claude Code
            session.status = ImprovementStatus.IMPLEMENTING

            # Build the command
            claude_cmd = [
                "claude", "-p", request,
                "--output-format", "stream-json",
                "--allowedTools", "Read,Write,Edit,Bash,Grep,Glob",
                "--model", model,
                "--max-turns", str(max_turns),
            ]

            # Add system prompt for safety and debugging access
            system_prompt = """You are improving the BarnabeeNet smart home AI system.

SAFETY RULES (MUST FOLLOW):
- Do NOT modify files in: secrets/, .env, infrastructure/secrets/
- Do NOT run: rm -rf, sudo, chmod 777, or pipe curl/wget to shell
- Do NOT modify authentication, permissions, or security code
- Do NOT change privacy zone configurations

DEBUGGING RESOURCES - Use these to understand issues:
1. Conversation traces: ./scripts/debug-logs.sh traces 10
2. Specific trace: ./scripts/debug-logs.sh trace <trace_id>
3. Activity feed: ./scripts/debug-logs.sh activity 50
4. Errors: ./scripts/debug-logs.sh errors
5. LLM calls: ./scripts/debug-logs.sh llm-calls 20
6. Journal: ./scripts/debug-logs.sh journal 100
7. HA errors: ./scripts/debug-logs.sh ha-errors
8. Search by type: ./scripts/debug-logs.sh search <type>
   Types: user.input, meta.classify, agent.decision, llm.error, etc.

WORKFLOW (MUST FOLLOW THIS ORDER):
1. Diagnose - Check logs and code to understand the issue
2. Propose - Output a PLAN block for user approval:

   <PLAN>
   ISSUE: [Brief description of what you found]
   ROOT_CAUSE: [Why this is happening]
   PROPOSED_FIX: [What you plan to change]
   FILES_AFFECTED: [List of files you'll modify]
   RISKS: [Potential conflicts, breaking changes, or concerns]
   TESTS: [What tests you'll add or run]
   </PLAN>

   Then STOP and wait for user approval before proceeding.

3. Implement - Only after approval, make minimal targeted changes
4. Test - Add or update tests, run: pytest tests/ -v
5. Verify - If tests fail, fix issues and re-test

IMPORTANT: Always output the <PLAN> block and wait for user input before making
any code changes. The user may want to adjust your approach or provide additional
context. You will receive their feedback as a new message.

Always explain what you're doing before each action."""

            claude_cmd.extend(["--append-system-prompt", system_prompt])

            # Run Claude Code and stream output
            process = await asyncio.create_subprocess_exec(
                *claude_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_path,
            )

            async for line in process.stdout:
                try:
                    event_data = json.loads(line.decode())
                    await self._process_claude_event(session, event_data)
                    yield {"event": "claude_event", "data": event_data}
                except json.JSONDecodeError:
                    continue

            await process.wait()

            # Phase 3: Collect results
            session.status = ImprovementStatus.TESTING

            # Get git diff
            diff_result = await self._run_git_command(["diff", "--stat"])
            session.git_diff = diff_result

            # Get modified files
            files_result = await self._run_git_command(
                ["diff", "--name-only"]
            )
            session.files_modified = files_result.strip().split("\n") if files_result.strip() else []

            await self._emit_progress(session, "changes_ready", {
                "files_modified": session.files_modified,
                "diff_stats": diff_result,
                "estimated_api_cost_usd": session.token_usage.calculate_api_cost(session.model_used),
            })
            yield {
                "event": "changes_ready",
                "files": session.files_modified,
                "estimated_cost": session.token_usage.calculate_api_cost(session.model_used),
            }

            # Phase 4: Await approval (unless auto_approve)
            if not auto_approve and session.files_modified:
                session.status = ImprovementStatus.AWAITING_APPROVAL
                await self._emit_progress(session, "awaiting_approval", {
                    "message": "Changes ready for review. Call approve_session() to commit.",
                })
                yield {"event": "awaiting_approval", "session_id": session_id}
            elif session.files_modified:
                # Auto-approve: commit directly
                await self.approve_session(session_id)
                yield {"event": "auto_approved", "commit": session.commit_hash}
            else:
                session.status = ImprovementStatus.COMPLETED
                session.success = True
                session.summary = "No changes needed"
                yield {"event": "completed", "message": "No changes needed"}

        except Exception as e:
            session.status = ImprovementStatus.FAILED
            session.error = str(e)
            logger.error("Improvement failed", error=str(e), session_id=session_id)
            await self._emit_progress(session, "error", {"error": str(e)})
            yield {"event": "error", "error": str(e)}

            # Return to main branch on failure
            await self._run_git_command(["checkout", "main"])

        finally:
            session.completed_at = datetime.now()

    async def _process_claude_event(
        self,
        session: ImprovementSession,
        event: dict[str, Any],
    ) -> None:
        """Process a streaming event from Claude Code."""
        event_type = event.get("type")

        if event_type == "assistant":
            # Assistant message with content
            content = event.get("message", {}).get("content", [])
            for block in content:
                if block.get("type") == "text":
                    session.messages.append({
                        "role": "assistant",
                        "text": block.get("text", ""),
                        "timestamp": datetime.now().isoformat(),
                    })
                elif block.get("type") == "tool_use":
                    # Record the tool operation
                    tool_name = block.get("name", "unknown")
                    tool_input = block.get("input", {})

                    operation = ClaudeCodeOperation(
                        operation_id=block.get("id", ""),
                        timestamp=datetime.now(),
                        operation_type=tool_name.lower(),
                        command=tool_input.get("command"),
                        file_path=tool_input.get("file_path") or tool_input.get("path"),
                        content_preview=str(tool_input)[:200],
                    )
                    session.operations.append(operation)

                    await self._emit_progress(session, "tool_use", {
                        "tool": tool_name,
                        "input_preview": str(tool_input)[:200],
                    })

        elif event_type == "result":
            # Final result with usage stats
            session.success = event.get("subtype") == "success"

            # Extract token usage for cost calculation
            usage = event.get("usage", {})
            session.token_usage.input_tokens = usage.get("input_tokens", 0)
            session.token_usage.output_tokens = usage.get("output_tokens", 0)
            session.token_usage.cache_read_tokens = usage.get("cache_read_input_tokens", 0)
            session.token_usage.cache_write_tokens = usage.get("cache_creation_input_tokens", 0)

            session.summary = event.get("result", "")

    async def approve_session(self, session_id: str) -> dict[str, Any]:
        """Approve and commit changes from a session."""
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if session.status != ImprovementStatus.AWAITING_APPROVAL:
            raise ValueError(f"Session not awaiting approval: {session.status}")

        session.status = ImprovementStatus.COMMITTING

        try:
            # Stage all changes
            await self._run_git_command(["add", "-A"])

            # Create commit
            commit_msg = f"[self-improve] {session.request[:50]}...\n\nSession: {session_id}\nEstimated API cost: ${session.token_usage.calculate_api_cost(session.model_used):.4f}"
            await self._run_git_command(["commit", "-m", commit_msg])

            # Get commit hash
            hash_result = await self._run_git_command(["rev-parse", "HEAD"])
            session.commit_hash = hash_result.strip()

            session.status = ImprovementStatus.COMPLETED
            session.success = True

            await self._emit_progress(session, "committed", {
                "commit_hash": session.commit_hash,
                "branch": session.branch_name,
            })

            return {
                "status": "committed",
                "commit_hash": session.commit_hash,
                "branch": session.branch_name,
                "files": session.files_modified,
            }

        except Exception as e:
            session.status = ImprovementStatus.FAILED
            session.error = str(e)
            raise

    async def reject_session(self, session_id: str) -> dict[str, Any]:
        """Reject changes and return to main branch."""
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Discard changes and return to main
        await self._run_git_command(["checkout", "main"])
        await self._run_git_command(["branch", "-D", session.branch_name])

        session.status = ImprovementStatus.REJECTED
        session.completed_at = datetime.now()

        await self._emit_progress(session, "rejected", {
            "message": "Changes rejected and discarded",
        })

        return {"status": "rejected", "session_id": session_id}

    async def stop_session(self, session_id: str) -> dict[str, Any]:
        """Stop an active session immediately."""
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        session.stop_requested = True
        session.status = ImprovementStatus.STOPPED
        session.completed_at = datetime.now()

        await self._emit_progress(session, "stopped", {
            "message": "Session stopped by user",
        })

        # Return to main branch if we created one
        if session.branch_name:
            try:
                await self._run_git_command(["checkout", "main"])
                await self._run_git_command(["branch", "-D", session.branch_name])
            except Exception:
                pass  # Best effort cleanup

        return {"status": "stopped", "session_id": session_id}

    async def send_user_input(self, session_id: str, message: str) -> dict[str, Any]:
        """Send user input to an active session.

        Used for:
        - Approving a proposed plan: "approved" or "proceed"
        - Rejecting a plan: "reject" or providing alternative direction
        - Course correction: Any guidance during execution
        """
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Add to the session's input queue
        await session.user_input_queue.put(message)

        await self._emit_progress(session, "user_input", {
            "message": message,
        })

        return {"status": "sent", "session_id": session_id, "message": message}

    async def approve_plan(self, session_id: str, feedback: str | None = None) -> dict[str, Any]:
        """Approve the proposed plan and continue execution."""
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if session.status != ImprovementStatus.AWAITING_PLAN_APPROVAL:
            raise ValueError(f"Session not awaiting plan approval: {session.status}")

        message = "APPROVED. Proceed with the implementation."
        if feedback:
            message += f" Additional guidance: {feedback}"

        await session.user_input_queue.put(message)
        session.status = ImprovementStatus.IMPLEMENTING

        await self._emit_progress(session, "plan_approved", {
            "feedback": feedback,
        })

        return {"status": "approved", "session_id": session_id}

    async def reject_plan(self, session_id: str, reason: str) -> dict[str, Any]:
        """Reject the proposed plan with feedback."""
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        if session.status != ImprovementStatus.AWAITING_PLAN_APPROVAL:
            raise ValueError(f"Session not awaiting plan approval: {session.status}")

        message = f"PLAN REJECTED. {reason} Please revise your approach."
        await session.user_input_queue.put(message)
        session.status = ImprovementStatus.DIAGNOSING  # Back to diagnosis

        await self._emit_progress(session, "plan_rejected", {
            "reason": reason,
        })

        return {"status": "rejected", "session_id": session_id, "reason": reason}

    async def _run_git_command(self, args: list[str]) -> str:
        """Run a git command and return output."""
        process = await asyncio.create_subprocess_exec(
            "git", *args,
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
            cwd=self.project_path,
        )
        stdout, stderr = await process.communicate()

        if process.returncode != 0:
            raise RuntimeError(f"Git command failed: {stderr.decode()}")

        return stdout.decode()

    def get_session(self, session_id: str) -> ImprovementSession | None:
        """Get a session by ID."""
        return self.active_sessions.get(session_id)

    def get_all_sessions(self) -> list[dict[str, Any]]:
        """Get all sessions as dictionaries."""
        return [s.to_dict() for s in self.active_sessions.values()]

    def get_cost_report(self) -> dict[str, Any]:
        """Generate a cost comparison report."""
        total_input = sum(s.token_usage.input_tokens for s in self.active_sessions.values())
        total_output = sum(s.token_usage.output_tokens for s in self.active_sessions.values())
        total_cache_read = sum(s.token_usage.cache_read_tokens for s in self.active_sessions.values())
        total_cache_write = sum(s.token_usage.cache_write_tokens for s in self.active_sessions.values())

        total_usage = TokenUsage(
            input_tokens=total_input,
            output_tokens=total_output,
            cache_read_tokens=total_cache_read,
            cache_write_tokens=total_cache_write,
        )

        # Calculate costs for different models
        sonnet_cost = total_usage.calculate_api_cost("claude-sonnet-4-5")
        opus_cost = total_usage.calculate_api_cost("claude-opus-4-5")

        return {
            "total_sessions": len(self.active_sessions),
            "successful_sessions": sum(1 for s in self.active_sessions.values() if s.success),
            "total_tokens": {
                "input": total_input,
                "output": total_output,
                "cache_read": total_cache_read,
                "cache_write": total_cache_write,
                "total": total_input + total_output,
            },
            "estimated_api_costs": {
                "if_sonnet_4_5": f"${sonnet_cost:.4f}",
                "if_opus_4_5": f"${opus_cost:.4f}",
            },
            "subscription_cost": "$0.00 (included in Max)",
            "savings_vs_api": f"${sonnet_cost:.4f} saved",
        }


# =============================================================================
# Singleton Instance
# =============================================================================

_agent_instance: SelfImprovementAgent | None = None


async def get_self_improvement_agent() -> SelfImprovementAgent:
    """Get or create the self-improvement agent singleton."""
    global _agent_instance
    if _agent_instance is None:
        from barnabeenet.core.config import get_settings
        settings = get_settings()

        # Get project path (parent of src)
        project_path = Path(__file__).parent.parent.parent.parent

        message_bus = await get_message_bus()
        _agent_instance = SelfImprovementAgent(
            project_path=project_path,
            message_bus=message_bus,
        )
    return _agent_instance
```

---

### 1.2 Create API Routes

**File:** `src/barnabeenet/api/routes/self_improvement.py`

```python
"""API routes for Self-Improvement Agent.

Provides endpoints for:
- Submitting improvement requests
- Checking session status
- Approving/rejecting changes
- Viewing cost reports
"""

from __future__ import annotations

import json
import logging
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field

from barnabeenet.agents.self_improvement import (
    ImprovementStatus,
    get_self_improvement_agent,
)

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/v1/self-improve", tags=["Self-Improvement"])


# =============================================================================
# Request/Response Models
# =============================================================================


class ImprovementRequest(BaseModel):
    """Request to improve the codebase."""
    request: str = Field(..., description="Natural language description of what to improve")
    model: str = Field("sonnet", description="Model to use: 'sonnet' or 'opus'")
    auto_approve: bool = Field(False, description="Auto-commit without approval (dangerous!)")
    max_turns: int = Field(50, description="Maximum Claude Code turns")


class SessionResponse(BaseModel):
    """Response with session details."""
    session_id: str
    status: str
    request: str
    started_at: str
    files_modified: list[str]
    estimated_api_cost_usd: float
    success: bool | None
    error: str | None


class CostReport(BaseModel):
    """Cost comparison report."""
    total_sessions: int
    successful_sessions: int
    total_tokens: dict[str, int]
    estimated_api_costs: dict[str, str]
    subscription_cost: str
    savings_vs_api: str


# =============================================================================
# Endpoints
# =============================================================================


@router.post("/improve")
async def start_improvement(req: ImprovementRequest):
    """Start an improvement session.

    Returns a session ID. Use /sessions/{session_id} to check status,
    or connect to WebSocket for real-time updates.
    """
    agent = await get_self_improvement_agent()

    # Start the improvement in background and return immediately
    import asyncio

    async def run_improvement():
        async for event in agent.improve(
            request=req.request,
            model=req.model,
            auto_approve=req.auto_approve,
            max_turns=req.max_turns,
        ):
            pass  # Events are broadcast via Redis

    asyncio.create_task(run_improvement())

    # Wait briefly for session to be created
    await asyncio.sleep(0.5)

    # Get the session
    sessions = agent.get_all_sessions()
    if sessions:
        latest = sessions[-1]
        return {
            "session_id": latest["session_id"],
            "status": "started",
            "message": "Improvement session started. Check status or connect to WebSocket for updates.",
        }

    return {"status": "error", "message": "Failed to start session"}


@router.post("/improve/stream")
async def start_improvement_stream(req: ImprovementRequest):
    """Start an improvement session with streaming response.

    Returns a stream of JSON events as the improvement progresses.
    """
    agent = await get_self_improvement_agent()

    async def event_generator():
        async for event in agent.improve(
            request=req.request,
            model=req.model,
            auto_approve=req.auto_approve,
            max_turns=req.max_turns,
        ):
            yield f"data: {json.dumps(event)}\n\n"

    return StreamingResponse(
        event_generator(),
        media_type="text/event-stream",
    )


@router.get("/sessions")
async def list_sessions():
    """List all improvement sessions."""
    agent = await get_self_improvement_agent()
    return agent.get_all_sessions()


@router.get("/sessions/{session_id}")
async def get_session(session_id: str):
    """Get details of a specific session."""
    agent = await get_self_improvement_agent()
    session = agent.get_session(session_id)

    if not session:
        raise HTTPException(status_code=404, detail="Session not found")

    return session.to_dict()


@router.post("/sessions/{session_id}/approve")
async def approve_session(session_id: str):
    """Approve and commit changes from a session."""
    agent = await get_self_improvement_agent()

    try:
        result = await agent.approve_session(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/reject")
async def reject_session(session_id: str):
    """Reject changes and discard the session branch."""
    agent = await get_self_improvement_agent()

    try:
        result = await agent.reject_session(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/stop")
async def stop_session(session_id: str):
    """Stop an active session immediately."""
    agent = await get_self_improvement_agent()

    try:
        result = await agent.stop_session(session_id)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class UserInputRequest(BaseModel):
    """User input to send to an active session."""
    message: str = Field(..., description="Message to send to Claude Code")


@router.post("/sessions/{session_id}/input")
async def send_user_input(session_id: str, req: UserInputRequest):
    """Send user input to an active session.

    Use this to provide guidance, answer questions, or course-correct
    Claude Code during execution.
    """
    agent = await get_self_improvement_agent()

    try:
        result = await agent.send_user_input(session_id, req.message)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


class PlanFeedbackRequest(BaseModel):
    """Feedback when approving or rejecting a plan."""
    feedback: str | None = Field(None, description="Additional guidance or reason")


@router.post("/sessions/{session_id}/approve-plan")
async def approve_plan(session_id: str, req: PlanFeedbackRequest | None = None):
    """Approve the proposed plan and continue execution."""
    agent = await get_self_improvement_agent()

    try:
        feedback = req.feedback if req else None
        result = await agent.approve_plan(session_id, feedback)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.post("/sessions/{session_id}/reject-plan")
async def reject_plan(session_id: str, req: PlanFeedbackRequest):
    """Reject the proposed plan with feedback."""
    agent = await get_self_improvement_agent()

    if not req.feedback:
        raise HTTPException(status_code=400, detail="Feedback required when rejecting plan")

    try:
        result = await agent.reject_plan(session_id, req.feedback)
        return result
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/cost-report", response_model=CostReport)
async def get_cost_report():
    """Get a cost comparison report.

    Shows total usage and what it would cost via API vs subscription.
    """
    agent = await get_self_improvement_agent()
    return agent.get_cost_report()


@router.post("/gpu/restart/{service}")
async def restart_gpu_service(service: str):
    """Restart a GPU service on Man-of-war.

    Available services: parakeet-tdt, kokoro-tts, ecapa-tdnn
    """
    allowed_services = ["parakeet-tdt", "kokoro-tts", "ecapa-tdnn"]
    if service not in allowed_services:
        raise HTTPException(
            status_code=400,
            detail=f"Unknown service. Allowed: {allowed_services}"
        )

    agent = await get_self_improvement_agent()
    success = await agent.restart_gpu_service(service)

    if success:
        return {"status": "restarted", "service": service}
    raise HTTPException(status_code=500, detail=f"Failed to restart {service}")
```

---

### 1.3 Register Routes in Main App

**File:** `src/barnabeenet/main.py`

Add to the `_register_routes` function:

```python
from barnabeenet.api.routes import (
    # ... existing imports ...
    self_improvement,  # ADD THIS
)

def _register_routes(app: FastAPI) -> None:
    # ... existing route registrations ...

    # Self-Improvement Agent
    app.include_router(self_improvement.router)
```

---

## Phase 2: Dashboard Integration

### 2.1 Add WebSocket Events for Self-Improvement

**File:** `src/barnabeenet/api/routes/websocket.py`

Add these new message types to the dashboard WebSocket handler (in the `dashboard_ws` function):

```python
elif msg_type == "subscribe_self_improvement":
    # Subscribe to self-improvement events
    await dashboard_manager.send_to(
        websocket,
        "subscribed",
        {"channel": "self_improvement"},
    )

elif msg_type == "get_improvement_sessions":
    from barnabeenet.agents.self_improvement import get_self_improvement_agent
    agent = await get_self_improvement_agent()
    sessions = agent.get_all_sessions()
    await dashboard_manager.send_to(
        websocket,
        "improvement_sessions",
        {"sessions": sessions},
    )

elif msg_type == "get_cost_report":
    from barnabeenet.agents.self_improvement import get_self_improvement_agent
    agent = await get_self_improvement_agent()
    report = agent.get_cost_report()
    await dashboard_manager.send_to(
        websocket,
        "cost_report",
        report,
    )
```

### 2.2 Create Dashboard Component

**File:** `static/dashboard/components/self-improvement-panel.js`

```javascript
/**
 * Self-Improvement Panel Component
 *
 * Interactive dashboard for Self-Improvement Agent showing:
 * - Live thinking/reasoning stream
 * - Command execution with results
 * - Plan approval workflow
 * - User input for course correction
 * - Stop button for immediate halt
 * - Cost tracking
 */

class SelfImprovementPanel {
    constructor(containerId, websocket) {
        this.container = document.getElementById(containerId);
        this.ws = websocket;
        this.sessions = [];
        this.activeSessionId = null;

        this.init();
    }

    init() {
        this.render();
        this.subscribeToEvents();
    }

    subscribeToEvents() {
        this.ws.send(JSON.stringify({ type: 'get_improvement_sessions' }));
        this.ws.send(JSON.stringify({ type: 'subscribe_self_improvement' }));

        this.ws.addEventListener('message', (event) => {
            const data = JSON.parse(event.data);
            this.handleEvent(data);
        });
    }

    handleEvent(data) {
        switch (data.type) {
            case 'improvement_sessions':
                this.sessions = data.sessions;
                this.renderSessionList();
                break;

            case 'self_improvement:progress':
                this.handleProgressEvent(data);
                break;

            case 'cost_report':
                this.renderCostReport(data);
                break;
        }
    }

    handleProgressEvent(event) {
        const sessionId = event.session_id;

        // Update session in list
        const existingIdx = this.sessions.findIndex(s => s.session_id === sessionId);
        if (existingIdx >= 0) {
            this.sessions[existingIdx] = { ...this.sessions[existingIdx], ...event };
        }

        this.renderSessionList();

        // If this is the active session, update the detail view
        if (sessionId === this.activeSessionId) {
            this.updateActiveSessionView(event);
        }

        // Handle specific events
        switch (event.event_type) {
            case 'tool_use':
                this.addOperationToLog(event);
                break;
            case 'thinking':
                this.updateThinkingDisplay(event.text);
                break;
            case 'plan_proposed':
                this.showPlanApproval(event);
                break;
        }
    }

    render() {
        this.container.innerHTML = `
            <div class="self-improvement-panel">
                <div class="panel-header">
                    <h3>🔧 Self-Improvement Agent</h3>
                    <button class="btn btn-primary" id="new-improvement">
                        + New Request
                    </button>
                </div>

                <div class="panel-layout">
                    <!-- Left: Session List -->
                    <div class="sessions-sidebar">
                        <h4>Sessions</h4>
                        <div id="session-list"></div>
                    </div>

                    <!-- Center: Active Session View -->
                    <div class="active-session-view">
                        <div id="no-session-selected" class="empty-state">
                            Select a session or start a new improvement request
                        </div>

                        <div id="active-session" class="hidden">
                            <!-- Session Header with Stop Button -->
                            <div class="session-header">
                                <div class="session-title">
                                    <span id="session-status-badge" class="status-badge"></span>
                                    <span id="session-request-text"></span>
                                </div>
                                <button id="stop-session" class="btn btn-danger">
                                    ⏹ Stop
                                </button>
                            </div>

                            <!-- Plan Approval Section (shown when awaiting approval) -->
                            <div id="plan-approval" class="plan-approval hidden">
                                <h4>📋 Proposed Plan</h4>
                                <div id="plan-content" class="plan-content"></div>
                                <div class="plan-actions">
                                    <button id="reject-plan" class="btn btn-secondary">
                                        ✗ Reject & Revise
                                    </button>
                                    <button id="approve-plan" class="btn btn-success">
                                        ✓ Approve & Proceed
                                    </button>
                                </div>
                                <div class="plan-feedback">
                                    <input type="text" id="plan-feedback-input"
                                           placeholder="Optional: Add guidance or conditions...">
                                </div>
                            </div>

                            <!-- Live Thinking/Reasoning Stream -->
                            <div class="thinking-section">
                                <h4>💭 Thinking</h4>
                                <div id="thinking-stream" class="thinking-stream"></div>
                            </div>

                            <!-- Command/Operation Log -->
                            <div class="operations-section">
                                <h4>⚡ Operations</h4>
                                <div id="operation-log" class="operation-log"></div>
                            </div>

                            <!-- User Input Section -->
                            <div class="user-input-section">
                                <h4>💬 Send Guidance</h4>
                                <div class="input-row">
                                    <input type="text" id="user-input"
                                           placeholder="Course correct, ask questions, or provide context...">
                                    <button id="send-input" class="btn btn-primary">Send</button>
                                </div>
                            </div>

                            <!-- Final Approval Section (shown when code changes ready) -->
                            <div id="code-approval" class="code-approval hidden">
                                <h4>📝 Changes Ready for Review</h4>
                                <div id="diff-preview" class="diff-preview"></div>
                                <div class="code-approval-actions">
                                    <button id="reject-changes" class="btn btn-danger">
                                        ✗ Reject Changes
                                    </button>
                                    <button id="approve-changes" class="btn btn-success">
                                        ✓ Commit Changes
                                    </button>
                                </div>
                            </div>
                        </div>
                    </div>

                    <!-- Right: Cost Tracking -->
                    <div class="cost-sidebar">
                        <h4>💰 Cost Tracking</h4>
                        <div id="cost-tracking"></div>
                        <button class="btn btn-sm" id="refresh-costs">Refresh</button>
                    </div>
                </div>

                <!-- New Improvement Modal -->
                <div id="improvement-modal" class="modal hidden">
                    <div class="modal-content">
                        <h3>Request Improvement</h3>
                        <textarea id="improvement-request"
                                  placeholder="Describe the issue or improvement...&#10;&#10;Examples:&#10;- 'The last voice command didn't work, look into it'&#10;- 'Add better error messages to action agent'&#10;- 'Optimize the STT pipeline latency'"
                                  rows="6"></textarea>
                        <div class="model-select">
                            <label>
                                <input type="radio" name="model" value="sonnet" checked>
                                Sonnet (faster, $3/$15 per 1M tokens)
                            </label>
                            <label>
                                <input type="radio" name="model" value="opus">
                                Opus (more capable, $15/$75 per 1M tokens)
                            </label>
                        </div>
                        <div class="modal-actions">
                            <button id="cancel-improvement" class="btn">Cancel</button>
                            <button id="submit-improvement" class="btn btn-primary">
                                Start Investigation
                            </button>
                        </div>
                    </div>
                </div>
            </div>
        `;

        this.attachEventListeners();
        this.requestCostReport();
    }

    attachEventListeners() {
        // Modal controls
        document.getElementById('new-improvement').addEventListener('click', () => {
            document.getElementById('improvement-modal').classList.remove('hidden');
        });
        document.getElementById('cancel-improvement').addEventListener('click', () => {
            document.getElementById('improvement-modal').classList.add('hidden');
        });
        document.getElementById('submit-improvement').addEventListener('click', () => {
            this.submitImprovement();
        });

        // Session controls
        document.getElementById('stop-session').addEventListener('click', () => {
            this.stopSession();
        });
        document.getElementById('send-input').addEventListener('click', () => {
            this.sendUserInput();
        });
        document.getElementById('user-input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') this.sendUserInput();
        });

        // Plan approval controls
        document.getElementById('approve-plan').addEventListener('click', () => {
            this.approvePlan();
        });
        document.getElementById('reject-plan').addEventListener('click', () => {
            this.rejectPlan();
        });

        // Code approval controls
        document.getElementById('approve-changes').addEventListener('click', () => {
            this.approveSession();
        });
        document.getElementById('reject-changes').addEventListener('click', () => {
            this.rejectSession();
        });

        // Cost refresh
        document.getElementById('refresh-costs').addEventListener('click', () => {
            this.requestCostReport();
        });
    }

    async submitImprovement() {
        const request = document.getElementById('improvement-request').value;
        const model = document.querySelector('input[name="model"]:checked').value;

        if (!request.trim()) return;

        document.getElementById('improvement-modal').classList.add('hidden');
        document.getElementById('improvement-request').value = '';

        try {
            const response = await fetch('/api/v1/self-improve/improve', {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ request, model, auto_approve: false }),
            });

            const result = await response.json();
            console.log('Improvement started:', result);

            // Select the new session
            if (result.session_id) {
                this.selectSession(result.session_id);
            }

            this.ws.send(JSON.stringify({ type: 'get_improvement_sessions' }));

        } catch (error) {
            console.error('Failed to start improvement:', error);
        }
    }

    selectSession(sessionId) {
        this.activeSessionId = sessionId;

        // Show active session view
        document.getElementById('no-session-selected').classList.add('hidden');
        document.getElementById('active-session').classList.remove('hidden');

        // Update session list selection
        document.querySelectorAll('.session-item').forEach(el => {
            el.classList.toggle('selected', el.dataset.sessionId === sessionId);
        });

        // Load session details
        const session = this.sessions.find(s => s.session_id === sessionId);
        if (session) {
            this.renderActiveSession(session);
        }
    }

    renderActiveSession(session) {
        document.getElementById('session-status-badge').textContent =
            this.getStatusIcon(session.status) + ' ' + session.status;
        document.getElementById('session-status-badge').className =
            'status-badge status-' + session.status;
        document.getElementById('session-request-text').textContent = session.request;

        // Show/hide plan approval section
        const planApproval = document.getElementById('plan-approval');
        if (session.status === 'awaiting_plan_approval' && session.proposed_plan) {
            planApproval.classList.remove('hidden');
            this.renderPlan(session.proposed_plan);
        } else {
            planApproval.classList.add('hidden');
        }

        // Show/hide code approval section
        const codeApproval = document.getElementById('code-approval');
        if (session.status === 'awaiting_approval') {
            codeApproval.classList.remove('hidden');
            document.getElementById('diff-preview').innerHTML = `
                <div class="diff-stats">
                    <strong>${session.files_modified?.length || 0}</strong> files changed |
                    <strong>${session.git_diff_lines || 0}</strong> lines |
                    Est. API cost: <strong>$${session.estimated_api_cost_usd?.toFixed(4) || '0.0000'}</strong>
                </div>
                <ul class="files-list">
                    ${(session.files_modified || []).map(f => `<li>${f}</li>`).join('')}
                </ul>
            `;
        } else {
            codeApproval.classList.add('hidden');
        }

        // Update thinking display
        if (session.current_thinking) {
            this.updateThinkingDisplay(session.current_thinking);
        }
    }

    renderPlan(plan) {
        const content = document.getElementById('plan-content');
        content.innerHTML = `
            <div class="plan-field">
                <label>Issue:</label>
                <div>${plan.issue || 'Not specified'}</div>
            </div>
            <div class="plan-field">
                <label>Root Cause:</label>
                <div>${plan.root_cause || 'Not specified'}</div>
            </div>
            <div class="plan-field">
                <label>Proposed Fix:</label>
                <div>${plan.proposed_fix || 'Not specified'}</div>
            </div>
            <div class="plan-field">
                <label>Files Affected:</label>
                <div>${plan.files_affected || 'Not specified'}</div>
            </div>
            <div class="plan-field ${plan.risks ? 'has-risks' : ''}">
                <label>⚠️ Risks:</label>
                <div>${plan.risks || 'None identified'}</div>
            </div>
            <div class="plan-field">
                <label>Tests:</label>
                <div>${plan.tests || 'Not specified'}</div>
            </div>
        `;
    }

    updateThinkingDisplay(text) {
        const stream = document.getElementById('thinking-stream');
        if (!stream) return;

        stream.innerHTML = `<pre>${this.escapeHtml(text)}</pre>`;
        stream.scrollTop = stream.scrollHeight;
    }

    updateActiveSessionView(event) {
        // Update status badge
        if (event.status) {
            document.getElementById('session-status-badge').textContent =
                this.getStatusIcon(event.status) + ' ' + event.status;
            document.getElementById('session-status-badge').className =
                'status-badge status-' + event.status;
        }
    }

    addOperationToLog(event) {
        const log = document.getElementById('operation-log');
        if (!log) return;

        const entry = document.createElement('div');
        entry.className = `operation-entry op-${event.tool?.toLowerCase() || 'unknown'}`;
        entry.innerHTML = `
            <div class="op-header">
                <span class="op-time">${new Date(event.timestamp).toLocaleTimeString()}</span>
                <span class="op-tool">${event.tool || 'unknown'}</span>
            </div>
            <div class="op-content">
                <pre>${this.escapeHtml(event.input_preview || '')}</pre>
            </div>
            ${event.output_preview ? `
                <div class="op-result">
                    <pre>${this.escapeHtml(event.output_preview)}</pre>
                </div>
            ` : ''}
        `;

        log.appendChild(entry);
        log.scrollTop = log.scrollHeight;

        // Limit log size
        while (log.children.length > 100) {
            log.removeChild(log.firstChild);
        }
    }

    async stopSession() {
        if (!this.activeSessionId) return;

        if (!confirm('Stop this session? Any uncommitted changes will be discarded.')) {
            return;
        }

        try {
            await fetch(`/api/v1/self-improve/sessions/${this.activeSessionId}/stop`, {
                method: 'POST',
            });
            this.ws.send(JSON.stringify({ type: 'get_improvement_sessions' }));
        } catch (error) {
            console.error('Failed to stop session:', error);
        }
    }

    async sendUserInput() {
        if (!this.activeSessionId) return;

        const input = document.getElementById('user-input');
        const message = input.value.trim();
        if (!message) return;

        input.value = '';

        try {
            await fetch(`/api/v1/self-improve/sessions/${this.activeSessionId}/input`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ message }),
            });

            // Add to thinking stream as user message
            const stream = document.getElementById('thinking-stream');
            const userMsg = document.createElement('div');
            userMsg.className = 'user-message';
            userMsg.innerHTML = `<strong>You:</strong> ${this.escapeHtml(message)}`;
            stream.appendChild(userMsg);
            stream.scrollTop = stream.scrollHeight;

        } catch (error) {
            console.error('Failed to send input:', error);
        }
    }

    async approvePlan() {
        if (!this.activeSessionId) return;

        const feedback = document.getElementById('plan-feedback-input').value.trim();

        try {
            await fetch(`/api/v1/self-improve/sessions/${this.activeSessionId}/approve-plan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ feedback: feedback || null }),
            });

            document.getElementById('plan-feedback-input').value = '';
            document.getElementById('plan-approval').classList.add('hidden');
            this.ws.send(JSON.stringify({ type: 'get_improvement_sessions' }));

        } catch (error) {
            console.error('Failed to approve plan:', error);
        }
    }

    async rejectPlan() {
        if (!this.activeSessionId) return;

        const feedback = document.getElementById('plan-feedback-input').value.trim();
        if (!feedback) {
            alert('Please provide feedback on why the plan should be revised.');
            document.getElementById('plan-feedback-input').focus();
            return;
        }

        try {
            await fetch(`/api/v1/self-improve/sessions/${this.activeSessionId}/reject-plan`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ feedback }),
            });

            document.getElementById('plan-feedback-input').value = '';
            this.ws.send(JSON.stringify({ type: 'get_improvement_sessions' }));

        } catch (error) {
            console.error('Failed to reject plan:', error);
        }
    }

    async approveSession() {
        if (!this.activeSessionId) return;

        try {
            await fetch(`/api/v1/self-improve/sessions/${this.activeSessionId}/approve`, {
                method: 'POST',
            });
            this.ws.send(JSON.stringify({ type: 'get_improvement_sessions' }));
        } catch (error) {
            console.error('Failed to approve session:', error);
        }
    }

    async rejectSession() {
        if (!this.activeSessionId) return;

        if (!confirm('Reject and discard all changes?')) return;

        try {
            await fetch(`/api/v1/self-improve/sessions/${this.activeSessionId}/reject`, {
                method: 'POST',
            });
            this.ws.send(JSON.stringify({ type: 'get_improvement_sessions' }));
        } catch (error) {
            console.error('Failed to reject session:', error);
        }
    }

    renderSessionList() {
        const container = document.getElementById('session-list');
        if (!container) return;

        container.innerHTML = this.sessions.map(session => `
            <div class="session-item ${session.status} ${session.session_id === this.activeSessionId ? 'selected' : ''}"
                 data-session-id="${session.session_id}"
                 onclick="selfImprovementPanel.selectSession('${session.session_id}')">
                <div class="session-status-icon">${this.getStatusIcon(session.status)}</div>
                <div class="session-info">
                    <div class="session-request-preview">${session.request.substring(0, 40)}...</div>
                    <div class="session-meta">
                        ${session.files_modified?.length || 0} files |
                        $${session.estimated_api_cost_usd?.toFixed(4) || '0.0000'}
                    </div>
                </div>
            </div>
        `).join('') || '<div class="empty-state">No sessions</div>';
    }

    getStatusIcon(status) {
        const icons = {
            'pending': '⏳',
            'diagnosing': '🔍',
            'awaiting_plan_approval': '📋',
            'implementing': '⚙️',
            'testing': '🧪',
            'awaiting_approval': '⏸️',
            'committing': '💾',
            'completed': '✅',
            'failed': '❌',
            'rejected': '🚫',
            'stopped': '⏹️',
        };
        return icons[status] || '❓';
    }

    requestCostReport() {
        this.ws.send(JSON.stringify({ type: 'get_cost_report' }));
    }

    renderCostReport(report) {
        const container = document.getElementById('cost-tracking');
        if (!container) return;

        container.innerHTML = `
            <div class="cost-report">
                <div class="cost-stat">
                    <label>Sessions</label>
                    <value>${report.total_sessions} (${report.successful_sessions} ✓)</value>
                </div>
                <div class="cost-stat">
                    <label>Tokens</label>
                    <value>${(report.total_tokens?.total || 0).toLocaleString()}</value>
                </div>
                <div class="cost-stat api-cost">
                    <label>If Sonnet API</label>
                    <value>${report.estimated_api_costs?.if_sonnet_4_5 || '$0.00'}</value>
                </div>
                <div class="cost-stat api-cost">
                    <label>If Opus API</label>
                    <value>${report.estimated_api_costs?.if_opus_4_5 || '$0.00'}</value>
                </div>
                <div class="cost-stat subscription">
                    <label>Actual Cost</label>
                    <value>${report.subscription_cost}</value>
                </div>
                <div class="cost-stat savings">
                    <label>Savings</label>
                    <value>${report.savings_vs_api}</value>
                </div>
            </div>
        `;
    }

    escapeHtml(text) {
        const div = document.createElement('div');
        div.textContent = text;
        return div.innerHTML;
    }
}

let selfImprovementPanel;
```

### 2.3 Dashboard Styles

**File:** `static/dashboard/css/self-improvement.css`

```css
/* Self-Improvement Panel Styles */

.self-improvement-panel {
    display: flex;
    flex-direction: column;
    height: 100%;
    gap: 1rem;
}

.panel-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.5rem 0;
    border-bottom: 1px solid var(--border-color, #333);
}

.panel-layout {
    display: grid;
    grid-template-columns: 250px 1fr 200px;
    gap: 1rem;
    flex: 1;
    min-height: 0;
}

/* Sessions Sidebar */
.sessions-sidebar {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    overflow-y: auto;
}

.session-item {
    display: flex;
    align-items: center;
    gap: 0.5rem;
    padding: 0.75rem;
    background: var(--card-bg, #1a1a2e);
    border-radius: 4px;
    cursor: pointer;
    transition: background 0.2s;
}

.session-item:hover {
    background: var(--card-hover, #252545);
}

.session-item.selected {
    background: var(--accent-color, #4a4a8a);
    border: 1px solid var(--accent-border, #6a6aaa);
}

.session-status-icon {
    font-size: 1.2rem;
}

.session-info {
    flex: 1;
    min-width: 0;
}

.session-request-preview {
    font-size: 0.85rem;
    white-space: nowrap;
    overflow: hidden;
    text-overflow: ellipsis;
}

.session-meta {
    font-size: 0.75rem;
    color: var(--text-muted, #888);
}

/* Active Session View */
.active-session-view {
    display: flex;
    flex-direction: column;
    gap: 1rem;
    overflow-y: auto;
}

.session-header {
    display: flex;
    justify-content: space-between;
    align-items: center;
    padding: 0.75rem;
    background: var(--card-bg, #1a1a2e);
    border-radius: 4px;
}

.session-title {
    display: flex;
    align-items: center;
    gap: 0.75rem;
}

.status-badge {
    padding: 0.25rem 0.5rem;
    border-radius: 4px;
    font-size: 0.8rem;
    font-weight: 500;
}

.status-diagnosing { background: #2a4a6a; }
.status-awaiting_plan_approval { background: #6a4a2a; }
.status-implementing { background: #2a6a4a; }
.status-testing { background: #4a2a6a; }
.status-awaiting_approval { background: #6a6a2a; }
.status-completed { background: #2a6a2a; }
.status-failed { background: #6a2a2a; }
.status-stopped { background: #4a4a4a; }

/* Plan Approval Section */
.plan-approval {
    background: var(--warning-bg, #3a3520);
    border: 1px solid var(--warning-border, #6a6530);
    border-radius: 4px;
    padding: 1rem;
}

.plan-content {
    display: flex;
    flex-direction: column;
    gap: 0.75rem;
    margin-bottom: 1rem;
}

.plan-field {
    display: grid;
    grid-template-columns: 120px 1fr;
    gap: 0.5rem;
}

.plan-field label {
    font-weight: 500;
    color: var(--text-muted, #aaa);
}

.plan-field.has-risks {
    background: rgba(255, 100, 100, 0.1);
    padding: 0.5rem;
    border-radius: 4px;
}

.plan-actions {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.75rem;
}

.plan-feedback input {
    width: 100%;
    padding: 0.5rem;
    background: var(--input-bg, #1a1a2e);
    border: 1px solid var(--border-color, #333);
    border-radius: 4px;
    color: inherit;
}

/* Thinking Stream */
.thinking-section,
.operations-section {
    background: var(--card-bg, #1a1a2e);
    border-radius: 4px;
    padding: 0.75rem;
}

.thinking-stream {
    max-height: 200px;
    overflow-y: auto;
    font-family: monospace;
    font-size: 0.85rem;
    line-height: 1.4;
}

.thinking-stream pre {
    margin: 0;
    white-space: pre-wrap;
    word-break: break-word;
}

.user-message {
    background: var(--accent-color, #4a4a8a);
    padding: 0.5rem;
    border-radius: 4px;
    margin: 0.5rem 0;
}

/* Operation Log */
.operation-log {
    max-height: 300px;
    overflow-y: auto;
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.operation-entry {
    background: var(--card-hover, #252545);
    border-radius: 4px;
    padding: 0.5rem;
    font-size: 0.85rem;
}

.op-header {
    display: flex;
    gap: 0.5rem;
    margin-bottom: 0.25rem;
}

.op-time {
    color: var(--text-muted, #888);
}

.op-tool {
    font-weight: 500;
    color: var(--accent-text, #8a8aff);
}

.op-content pre,
.op-result pre {
    margin: 0;
    font-size: 0.8rem;
    white-space: pre-wrap;
    word-break: break-word;
}

.op-result {
    margin-top: 0.25rem;
    padding-top: 0.25rem;
    border-top: 1px solid var(--border-color, #333);
    color: var(--text-muted, #aaa);
}

.op-bash { border-left: 3px solid #4a8a4a; }
.op-read { border-left: 3px solid #4a4a8a; }
.op-write { border-left: 3px solid #8a4a4a; }
.op-edit { border-left: 3px solid #8a8a4a; }

/* User Input Section */
.user-input-section {
    background: var(--card-bg, #1a1a2e);
    border-radius: 4px;
    padding: 0.75rem;
}

.input-row {
    display: flex;
    gap: 0.5rem;
}

.input-row input {
    flex: 1;
    padding: 0.5rem;
    background: var(--input-bg, #0a0a1e);
    border: 1px solid var(--border-color, #333);
    border-radius: 4px;
    color: inherit;
}

/* Code Approval Section */
.code-approval {
    background: var(--success-bg, #203520);
    border: 1px solid var(--success-border, #306530);
    border-radius: 4px;
    padding: 1rem;
}

.diff-preview {
    margin-bottom: 1rem;
}

.diff-stats {
    margin-bottom: 0.5rem;
}

.files-list {
    margin: 0;
    padding-left: 1.5rem;
    font-family: monospace;
    font-size: 0.85rem;
}

.code-approval-actions {
    display: flex;
    gap: 0.5rem;
}

/* Cost Sidebar */
.cost-sidebar {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.cost-report {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
}

.cost-stat {
    display: flex;
    justify-content: space-between;
    padding: 0.5rem;
    background: var(--card-bg, #1a1a2e);
    border-radius: 4px;
    font-size: 0.85rem;
}

.cost-stat.api-cost {
    color: var(--text-muted, #888);
}

.cost-stat.subscription {
    background: var(--success-bg, #203520);
}

.cost-stat.savings {
    background: var(--success-bg, #203520);
    font-weight: 500;
}

/* Empty States */
.empty-state {
    display: flex;
    align-items: center;
    justify-content: center;
    padding: 2rem;
    color: var(--text-muted, #888);
    font-style: italic;
}

/* Modal */
.modal {
    position: fixed;
    inset: 0;
    background: rgba(0, 0, 0, 0.8);
    display: flex;
    align-items: center;
    justify-content: center;
    z-index: 1000;
}

.modal.hidden {
    display: none;
}

.modal-content {
    background: var(--card-bg, #1a1a2e);
    padding: 1.5rem;
    border-radius: 8px;
    width: 90%;
    max-width: 500px;
}

.modal-content h3 {
    margin-top: 0;
}

.modal-content textarea {
    width: 100%;
    padding: 0.75rem;
    background: var(--input-bg, #0a0a1e);
    border: 1px solid var(--border-color, #333);
    border-radius: 4px;
    color: inherit;
    resize: vertical;
    font-family: inherit;
}

.model-select {
    display: flex;
    flex-direction: column;
    gap: 0.5rem;
    margin: 1rem 0;
}

.modal-actions {
    display: flex;
    justify-content: flex-end;
    gap: 0.5rem;
}

/* Buttons */
.btn {
    padding: 0.5rem 1rem;
    border: none;
    border-radius: 4px;
    cursor: pointer;
    font-size: 0.9rem;
    transition: background 0.2s;
}

.btn-primary {
    background: var(--primary-color, #4a6aa0);
    color: white;
}

.btn-primary:hover {
    background: var(--primary-hover, #5a7ab0);
}

.btn-success {
    background: var(--success-color, #4a8a4a);
    color: white;
}

.btn-danger {
    background: var(--danger-color, #8a4a4a);
    color: white;
}

.btn-secondary {
    background: var(--secondary-color, #4a4a6a);
    color: white;
}

.btn-sm {
    padding: 0.25rem 0.5rem;
    font-size: 0.8rem;
}
```

---

## Phase 3: Tests

**File:** `tests/test_self_improvement.py`

```python
"""Tests for Self-Improvement Agent."""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from barnabeenet.agents.self_improvement import (
    SelfImprovementAgent,
    ImprovementSession,
    ImprovementStatus,
    TokenUsage,
)


class TestTokenUsage:
    def test_calculate_api_cost_sonnet(self):
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=100_000)
        # Sonnet: $3/1M input, $15/1M output = $3 + $1.50 = $4.50
        assert usage.calculate_api_cost("claude-sonnet-4-5") == pytest.approx(4.5, rel=0.01)

    def test_calculate_api_cost_opus(self):
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=100_000)
        # Opus: $15/1M input, $75/1M output = $15 + $7.50 = $22.50
        assert usage.calculate_api_cost("claude-opus-4-5") == pytest.approx(22.5, rel=0.01)


class TestSelfImprovementAgent:
    @pytest.fixture
    def agent(self, tmp_path):
        with patch("subprocess.run") as mock_run:
            mock_run.return_value = MagicMock(returncode=0, stdout="1.0.0")
            return SelfImprovementAgent(project_path=tmp_path)

    def test_is_safe_operation_blocks_dangerous(self, agent):
        assert not agent._is_safe_operation("rm -rf /", None)
        assert not agent._is_safe_operation("sudo apt install", None)

    def test_is_safe_operation_blocks_forbidden_paths(self, agent):
        assert not agent._is_safe_operation("cat", "secrets/api_key.txt")
        assert not agent._is_safe_operation("cat", ".env")

    def test_is_safe_operation_allows_safe(self, agent):
        assert agent._is_safe_operation("ls -la", None)
        assert agent._is_safe_operation("pytest tests/", None)

    @pytest.mark.asyncio
    async def test_ssh_to_manofwar(self, agent):
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.returncode = 0
            mock_process.communicate.return_value = (b"success", b"")
            mock_exec.return_value = mock_process

            success, output = await agent.ssh_to_manofwar("echo test")

            assert success
            assert output == "success"
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_stop_session(self, agent):
        # Create a mock session
        session = ImprovementSession(
            session_id="test-123",
            request="Test request",
            status=ImprovementStatus.IMPLEMENTING,
            branch_name="improve/test-123",
        )
        agent.active_sessions["test-123"] = session

        with patch.object(agent, "_run_git_command", new_callable=AsyncMock):
            with patch.object(agent, "_emit_progress", new_callable=AsyncMock):
                result = await agent.stop_session("test-123")

        assert result["status"] == "stopped"
        assert session.status == ImprovementStatus.STOPPED
        assert session.stop_requested is True

    @pytest.mark.asyncio
    async def test_send_user_input(self, agent):
        session = ImprovementSession(
            session_id="test-123",
            request="Test request",
            status=ImprovementStatus.AWAITING_PLAN_APPROVAL,
        )
        agent.active_sessions["test-123"] = session

        with patch.object(agent, "_emit_progress", new_callable=AsyncMock):
            result = await agent.send_user_input("test-123", "test message")

        assert result["status"] == "sent"
        assert not session.user_input_queue.empty()
        msg = await session.user_input_queue.get()
        assert msg == "test message"

    @pytest.mark.asyncio
    async def test_approve_plan(self, agent):
        session = ImprovementSession(
            session_id="test-123",
            request="Test request",
            status=ImprovementStatus.AWAITING_PLAN_APPROVAL,
        )
        agent.active_sessions["test-123"] = session

        with patch.object(agent, "_emit_progress", new_callable=AsyncMock):
            result = await agent.approve_plan("test-123", "looks good")

        assert result["status"] == "approved"
        assert session.status == ImprovementStatus.IMPLEMENTING

    @pytest.mark.asyncio
    async def test_reject_plan(self, agent):
        session = ImprovementSession(
            session_id="test-123",
            request="Test request",
            status=ImprovementStatus.AWAITING_PLAN_APPROVAL,
        )
        agent.active_sessions["test-123"] = session

        with patch.object(agent, "_emit_progress", new_callable=AsyncMock):
            result = await agent.reject_plan("test-123", "try different approach")

        assert result["status"] == "rejected"
        assert session.status == ImprovementStatus.DIAGNOSING
```

---

## Validation Checklist

```bash
# Make debug script executable
chmod +x scripts/debug-logs.sh

# Test debug script
./scripts/debug-logs.sh help
./scripts/debug-logs.sh activity 5
./scripts/debug-logs.sh traces 3

# Run tests
pytest tests/test_self_improvement.py -v

# Type check
mypy src/barnabeenet/agents/self_improvement.py

# Lint
ruff check src/barnabeenet/agents/

# Test API
curl http://localhost:8000/api/v1/self-improve/cost-report

# Test SSH to Man-of-war (run on BarnabeeNet server)
ssh thom@man-of-war "echo 'Connection OK'"

# Full validation
./scripts/validate.sh
```

---

## Files Summary

**Create:**
- `src/barnabeenet/agents/self_improvement.py`
- `src/barnabeenet/api/routes/self_improvement.py`
- `static/dashboard/components/self-improvement-panel.js`
- `static/dashboard/css/self-improvement.css`
- `scripts/debug-logs.sh` - Log query helper for Claude Code
- `tests/test_self_improvement.py`

**Modify:**
- `src/barnabeenet/main.py` - Register routes
- `src/barnabeenet/api/routes/websocket.py` - Add WebSocket handlers

---

## NixOS Configuration (if needed)

If Node.js or other dependencies are missing, add to `/etc/nixos/configuration.nix`:

```nix
{ config, pkgs, ... }:

{
  environment.systemPackages = with pkgs; [
    # Claude Code requirements
    nodejs_20
    git
    openssh

    # Debug script requirements
    jq              # JSON parsing for log queries
    redis           # redis-cli for direct stream access
    websocat        # WebSocket client for real-time log tailing
    curl            # API access
  ];

  # Enable nix-ld for npm global packages
  programs.nix-ld.enable = true;
}
```

Then rebuild: `sudo nixos-rebuild switch`

---
