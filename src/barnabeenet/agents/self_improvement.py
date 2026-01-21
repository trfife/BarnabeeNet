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
- Logs all activities to ActivityLogger for dashboard visibility
- Can send HA notifications to user's phone
- Auto-approves low-risk changes above safety threshold
"""

from __future__ import annotations

import asyncio
import json
import re
import shutil
import subprocess
import uuid
from collections.abc import AsyncIterator, Callable
from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import TYPE_CHECKING, Any

import structlog

if TYPE_CHECKING:
    from redis.asyncio import Redis

logger = structlog.get_logger(__name__)


class ImprovementStatus(str, Enum):
    """Status of an improvement request."""

    PENDING = "pending"
    DIAGNOSING = "diagnosing"  # Checking logs, understanding issue
    AWAITING_PLAN_APPROVAL = "awaiting_plan_approval"  # User must approve plan
    IMPLEMENTING = "implementing"
    TESTING = "testing"
    AWAITING_APPROVAL = "awaiting_approval"  # User must approve code changes
    COMMITTING = "committing"
    COMPLETED = "completed"
    FAILED = "failed"
    REJECTED = "rejected"
    STOPPED = "stopped"  # User stopped the session


@dataclass
class TokenUsage:
    """Track token usage for cost calculation."""

    input_tokens: int = 0
    output_tokens: int = 0
    cache_read_tokens: int = 0
    cache_write_tokens: int = 0

    def add(self, other: TokenUsage) -> None:
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
            self.input_tokens * input_rate
            + self.output_tokens * output_rate
            + self.cache_read_tokens * cache_read_rate
            + self.cache_write_tokens * cache_write_rate
        )
        return round(cost, 6)

    def to_dict(self) -> dict[str, int]:
        """Convert to dictionary."""
        return {
            "input_tokens": self.input_tokens,
            "output_tokens": self.output_tokens,
            "cache_read_tokens": self.cache_read_tokens,
            "cache_write_tokens": self.cache_write_tokens,
        }


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

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "operation_id": self.operation_id,
            "timestamp": self.timestamp.isoformat(),
            "operation_type": self.operation_type,
            "command": self.command,
            "file_path": self.file_path,
            "content_preview": self.content_preview,
            "duration_ms": self.duration_ms,
            "success": self.success,
            "error": self.error,
        }


@dataclass
class SafetyScore:
    """Safety assessment for a proposed plan.

    Plans are scored from 0.0 (dangerous) to 1.0 (very safe).
    Plans above the auto_approve_threshold can be auto-approved.
    """

    score: float  # 0.0 to 1.0
    reasons: list[str]  # Why this score was given
    can_auto_approve: bool  # True if score >= threshold
    risk_factors: list[str]  # Specific risks identified

    # Default threshold for auto-approval
    AUTO_APPROVE_THRESHOLD: float = 0.85

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary."""
        return {
            "score": self.score,
            "reasons": self.reasons,
            "can_auto_approve": self.can_auto_approve,
            "risk_factors": self.risk_factors,
        }


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

    # Safety scoring
    safety_score: SafetyScore | None = None

    # Process handle for cancellation
    _process: asyncio.subprocess.Process | None = field(default=None, repr=False)

    def to_dict(self) -> dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "session_id": self.session_id,
            "request": self.request,
            "status": self.status.value,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat() if self.completed_at else None,
            "operations_count": len(self.operations),
            "operations": [op.to_dict() for op in self.operations[-20:]],  # Last 20
            "messages": self.messages[-50:],  # Last 50
            "token_usage": self.token_usage.to_dict(),
            "model_used": self.model_used,
            "files_modified": self.files_modified,
            "git_diff": self.git_diff,
            "commit_hash": self.commit_hash,
            "branch_name": self.branch_name,
            "success": self.success,
            "error": self.error,
            "summary": self.summary,
            "proposed_plan": self.proposed_plan,
            "stop_requested": self.stop_requested,
            "current_thinking": self.current_thinking[-2000:] if self.current_thinking else "",
            "estimated_api_cost_usd": self.token_usage.calculate_api_cost(self.model_used),
            "safety_score": self.safety_score.to_dict() if self.safety_score else None,
        }


# System prompt for Phase 1: Diagnosis and Planning ONLY
DIAGNOSIS_SYSTEM_PROMPT = """You are diagnosing an issue in the BarnabeeNet smart home AI system.

YOUR TASK: Analyze the issue and propose a plan. Do NOT make any code changes yet.

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

WORKFLOW:
1. Read relevant code files to understand the issue
2. Analyze the problem and identify root cause
3. Output a <PLAN> block with your proposed fix

FORMAT YOUR PLAN EXACTLY LIKE THIS:

<PLAN>
ISSUE: [Brief description of what you found]
ROOT_CAUSE: [Why this is happening]
PROPOSED_FIX: [What you plan to change]
FILES_AFFECTED: [List of files you'll modify]
RISKS: [Potential conflicts, breaking changes, or concerns]
TESTS: [What tests you'll add or run]
</PLAN>

IMPORTANT:
- DO NOT modify any files in this phase
- DO NOT run any tests yet
- ONLY read files and analyze the issue
- End your response after outputting the <PLAN> block"""


# System prompt for Phase 2: Implementation (after plan approval)
IMPLEMENTATION_SYSTEM_PROMPT = """You are implementing an approved plan for the BarnabeeNet smart home AI system.

SAFETY RULES (MUST FOLLOW):
- Do NOT modify files in: secrets/, .env, infrastructure/secrets/
- Do NOT run: rm -rf, sudo, chmod 777, or pipe curl/wget to shell
- Do NOT modify authentication, permissions, or security code
- Do NOT change privacy zone configurations

YOUR APPROVED PLAN:
{approved_plan}

{user_guidance}

WORKFLOW:
1. Make the minimal targeted changes described in the plan
2. Run tests: pytest
3. If tests fail, fix issues and re-test

IMPORTANT: The plan has been approved. Proceed with implementation.
Always explain what you're doing before each action."""


# Legacy combined prompt (kept for reference)
SYSTEM_PROMPT = """You are improving the BarnabeeNet smart home AI system.

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
4. Test - Add or update tests, run: pytest
5. Verify - If tests fail, fix issues and re-test

IMPORTANT: Always output the <PLAN> block and wait for user input before making
any code changes. The user may want to adjust your approach or provide additional
context. You will receive their feedback as a new message.

Always explain what you're doing before each action."""


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

    # HA notification target for user's phone
    NOTIFICATION_TARGET = "mobile_app_thomphone"

    # Auto-approve threshold - plans scoring above this can be auto-approved
    AUTO_APPROVE_THRESHOLD = 0.80

    # Safe file paths (changes here are low-risk)
    SAFE_PATHS = [
        "config/",
        "docs/",
        "prompts/",
        "tests/",
        "static/",  # UI files - cosmetic changes
        ".copilot/",
        "__init__.py",  # Version files and package markers
        "__version__",
        "README",
        "CONTEXT.md",
        "pyproject.toml",  # Metadata changes
        ".md",  # Markdown docs
        ".yaml",  # Config files
        ".yml",
        ".html",  # UI templates
        ".css",  # Stylesheets
    ]

    # Risky file paths (changes here need manual approval)
    RISKY_PATHS = [
        "main.py",
        "api/routes/",
        "services/homeassistant/",
        "agents/",
    ]

    def __init__(
        self,
        project_path: str | Path,
        redis_client: Redis | None = None,
        ha_client: Any | None = None,  # HomeAssistantClient for notifications
    ):
        self.project_path = Path(project_path)
        self.redis_client = redis_client
        self.ha_client = ha_client
        self.active_sessions: dict[str, ImprovementSession] = {}
        self._on_progress_callbacks: list[Callable] = []
        self._claude_code_available: bool | None = None
        self._claude_path: str | None = None
        self._activity_logger: Any | None = None

    def _get_activity_logger(self) -> Any:
        """Get the activity logger, lazy-loading to avoid import cycles."""
        if self._activity_logger is None:
            from barnabeenet.services.activity_log import get_activity_logger

            self._activity_logger = get_activity_logger()
        return self._activity_logger

    async def _log_activity(
        self,
        session: ImprovementSession,
        activity_type: str,
        title: str,
        detail: str | None = None,
        **data: Any,
    ) -> None:
        """Log a self-improvement activity to the dashboard with clickability."""
        try:
            from barnabeenet.services.activity_log import ActivityLevel, ActivityType

            # Map activity type string to enum
            type_map = {
                "start": ActivityType.SELF_IMPROVE_START,
                "diagnosing": ActivityType.SELF_IMPROVE_DIAGNOSING,
                "plan_proposed": ActivityType.SELF_IMPROVE_PLAN_PROPOSED,
                "plan_approved": ActivityType.SELF_IMPROVE_PLAN_APPROVED,
                "implementing": ActivityType.SELF_IMPROVE_IMPLEMENTING,
                "testing": ActivityType.SELF_IMPROVE_TESTING,
                "awaiting_approval": ActivityType.SELF_IMPROVE_AWAITING_APPROVAL,
                "committed": ActivityType.SELF_IMPROVE_COMMITTED,
                "failed": ActivityType.SELF_IMPROVE_FAILED,
                "stopped": ActivityType.SELF_IMPROVE_STOPPED,
            }

            activity_enum = type_map.get(activity_type, ActivityType.SELF_IMPROVE_START)
            level = ActivityLevel.ERROR if "fail" in activity_type else ActivityLevel.INFO

            # Determine if this needs attention
            needs_attention = activity_type in ("plan_proposed", "awaiting_approval")

            activity_logger = self._get_activity_logger()
            await activity_logger.log_quick(
                type=activity_enum,
                source="self_improvement",
                title=title,
                detail=detail,
                level=level,
                trace_id=session.session_id,
                session_id=session.session_id,
                status=session.status.value,
                # Dashboard clickability metadata
                request_preview=session.request[:80] if session.request else None,
                can_click=True,
                click_target=f"/self-improve?session={session.session_id}",
                needs_attention=needs_attention,
                **data,
            )
        except Exception as e:
            logger.warning("Failed to log activity", error=str(e))

    async def _send_notification(
        self,
        title: str,
        message: str,
        data: dict[str, Any] | None = None,
    ) -> bool:
        """Send a notification to the user's phone via Home Assistant.

        Args:
            title: Notification title
            message: Notification body
            data: Optional additional data (e.g., actions, URLs)

        Returns:
            True if notification was sent successfully
        """
        # Try to get HA client if not already set
        if self.ha_client is None:
            try:
                from barnabeenet.api.routes.homeassistant import get_ha_client

                self.ha_client = await get_ha_client()
                if self.ha_client:
                    logger.info("Loaded HA client for notifications")
            except Exception as e:
                logger.warning("Failed to load HA client", error=str(e))

        if self.ha_client is None:
            logger.warning(
                "No HA client available for notifications - check HA configuration",
                title=title,
            )
            return False

        try:
            service_data: dict[str, Any] = {
                "title": title,
                "message": message,
            }
            if data:
                service_data["data"] = data

            result = await self.ha_client.call_service(
                f"notify.{self.NOTIFICATION_TARGET}",
                **service_data,
            )

            success = result.success if hasattr(result, "success") else True
            if success:
                logger.info("Sent notification", title=title)
            return success
        except Exception as e:
            logger.warning("Failed to send notification", error=str(e))
            return False

    async def _notify_phase_change(
        self,
        session: ImprovementSession,
        phase: str,
        requires_attention: bool = False,
    ) -> None:
        """Send notification for phase changes.

        Args:
            session: The improvement session
            phase: Current phase name
            requires_attention: If True, notification is marked high priority
        """
        phase_messages = {
            "started": ("🚀 Self-Improvement Started", f"Working on: {session.request[:60]}..."),
            "diagnosing": ("🔍 Diagnosing Issue", "Analyzing logs and code..."),
            "plan_proposed": (
                "📋 Plan Ready for Review",
                f"Review required: {session.request[:40]}...",
            ),
            "plan_auto_approved": (
                "✅ Plan Auto-Approved",
                f"Safety score passed - implementing: {session.request[:40]}...",
            ),
            "implementing": ("⚙️ Implementing Changes", "Claude is writing code..."),
            "testing": ("🧪 Running Tests", "Verifying changes..."),
            "awaiting_commit": (
                "✅ Ready to Commit",
                f"Review {len(session.files_modified)} changed files",
            ),
            "committed": (
                "🎉 Changes Committed",
                f"Successfully improved: {session.request[:40]}...",
            ),
            "failed": ("❌ Improvement Failed", session.error or "Unknown error"),
            "stopped": ("⏹ Session Stopped", "User stopped the session"),
        }

        if phase not in phase_messages:
            return

        title, message = phase_messages[phase]

        # Add action URL for phases requiring attention
        data: dict[str, Any] = {}
        if requires_attention:
            title = f"⚠️ {title}"
            data["clickAction"] = (
                f"http://192.168.86.51:8000/?page=self-improve&session={session.session_id}"
            )
            data["priority"] = "high"
            data["ttl"] = 0  # Deliver immediately
            data["tag"] = f"si-{session.session_id}"  # Replace previous notifications

        await self._send_notification(title, message, data if data else None)

    def _calculate_safety_score(self, plan: dict[str, Any]) -> SafetyScore:
        """Calculate a safety score for a proposed plan.

        Scoring criteria:
        - Files in safe paths: +0.1 per file
        - Files in risky paths: -0.15 per file
        - Files in forbidden paths: -1.0 (immediate fail)
        - Only config/doc changes: +0.3 bonus
        - Tests included: +0.1 bonus
        - Risk factors mentioned: -0.05 per risk

        Returns:
            SafetyScore with score, reasons, and auto_approve eligibility
        """
        score = 0.7  # Base score
        reasons: list[str] = []
        risk_factors: list[str] = []

        files_affected = plan.get("files_affected", [])
        if not files_affected:
            files_affected = []
        elif isinstance(files_affected, str):
            files_affected = [f.strip() for f in files_affected.split(",")]

        # Check each affected file
        safe_count = 0
        risky_count = 0
        forbidden_count = 0

        for file_path in files_affected:
            # Check forbidden paths
            for forbidden in self.FORBIDDEN_PATHS:
                if forbidden in file_path:
                    forbidden_count += 1
                    risk_factors.append(f"Modifies forbidden path: {file_path}")

            # Check safe paths
            is_safe = any(safe in file_path for safe in self.SAFE_PATHS)
            is_risky = any(risky in file_path for risky in self.RISKY_PATHS)

            if is_safe:
                safe_count += 1
            elif is_risky:
                risky_count += 1

        # Apply scoring
        if forbidden_count > 0:
            score = 0.0
            reasons.append(f"Touches {forbidden_count} forbidden path(s)")
        else:
            score += safe_count * 0.1
            reasons.append(f"{safe_count} files in safe paths")

            score -= risky_count * 0.15
            if risky_count > 0:
                reasons.append(f"{risky_count} files in risky paths")
                risk_factors.append(f"Modifies {risky_count} core file(s)")

        # Single-file changes are safer
        if len(files_affected) == 1:
            score += 0.1
            reasons.append("Single file change")

        # Check if only config/doc changes
        only_config_docs = all(
            any(safe in f for safe in ["config/", "docs/", ".md", ".yaml", ".yml", "__init__.py"])
            for f in files_affected
        )
        if only_config_docs and files_affected:
            score += 0.3
            reasons.append("Only config/doc changes")

        # Check if tests are mentioned
        tests_mentioned = plan.get("tests", "")
        if tests_mentioned and "pytest" in tests_mentioned.lower():
            score += 0.1
            reasons.append("Includes test plan")

        # Check risks mentioned in plan
        plan_risks = plan.get("risks", "")
        if plan_risks:
            risk_count = len([r for r in plan_risks.split(",") if r.strip()])
            if risk_count > 0:
                score -= risk_count * 0.05
                risk_factors.append(f"{risk_count} risk(s) identified in plan")

        # Clamp score
        score = max(0.0, min(1.0, score))

        can_auto_approve = score >= self.AUTO_APPROVE_THRESHOLD and forbidden_count == 0

        if can_auto_approve:
            reasons.append(f"Score {score:.2f} >= threshold {self.AUTO_APPROVE_THRESHOLD}")
        else:
            reasons.append(f"Score {score:.2f} < threshold {self.AUTO_APPROVE_THRESHOLD}")

        return SafetyScore(
            score=score,
            reasons=reasons,
            can_auto_approve=can_auto_approve,
            risk_factors=risk_factors,
        )

    def _find_claude_path(self) -> str | None:
        """Find the Claude Code CLI executable.

        Checks standard PATH first, then common npm global locations.
        """
        # First check standard PATH
        claude_path = shutil.which("claude")
        if claude_path:
            return claude_path

        # Check common npm global install locations
        common_paths = [
            Path.home() / ".npm-global" / "bin" / "claude",
            Path.home() / ".local" / "bin" / "claude",
            Path("/usr/local/bin/claude"),
        ]

        for path in common_paths:
            if path.exists() and path.is_file():
                return str(path)

        return None

    def _verify_claude_code(self) -> bool:
        """Verify Claude Code CLI is installed and authenticated."""
        if self._claude_code_available is not None:
            return self._claude_code_available

        # Check if claude command exists
        claude_path = self._find_claude_path()
        if not claude_path:
            logger.warning("Claude Code CLI not found in PATH or common locations")
            self._claude_code_available = False
            return False

        # Store the path for later use
        self._claude_path = claude_path

        try:
            result = subprocess.run(
                [claude_path, "--version"],
                capture_output=True,
                text=True,
                timeout=10,
            )
            if result.returncode == 0:
                logger.info(
                    "Claude Code CLI verified",
                    version=result.stdout.strip(),
                    path=claude_path,
                )
                self._claude_code_available = True
                return True
            else:
                logger.warning("Claude Code CLI check failed", stderr=result.stderr)
                self._claude_code_available = False
                return False
        except Exception as e:
            logger.warning("Claude Code CLI verification failed", error=str(e))
            self._claude_code_available = False
            return False

    def is_available(self) -> bool:
        """Check if the self-improvement agent is available."""
        return self._verify_claude_code()

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
                "ssh",
                "-o",
                "ConnectTimeout=5",
                self.MANOFWAR_HOST,
                command,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
            )

            stdout, stderr = await asyncio.wait_for(
                process.communicate(),
                timeout=timeout,
            )

            output = stdout.decode() if stdout else stderr.decode()
            success = process.returncode == 0

            logger.info(
                "SSH to Man-of-war",
                command=command,
                success=success,
                output=output[:200],
            )

            return success, output

        except TimeoutError:
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
        success, output = await self.ssh_to_manofwar(f"sudo systemctl restart {service}")
        if success:
            logger.info("Restarted GPU service", service=service)
        return success

    async def _read_lines_safe(self, stream: asyncio.StreamReader) -> AsyncIterator[bytes]:
        """Read lines from stream, handling very long lines gracefully.

        The default asyncio readline() has a 64KB limit. When Claude CLI outputs
        large JSON events (e.g., file contents), this can fail. This method
        reads in chunks and yields complete lines.
        """
        buffer = b""
        while True:
            try:
                # Try normal readline first (faster for short lines)
                line = await stream.readline()
                if not line:
                    # EOF - yield any remaining buffer
                    if buffer:
                        yield buffer
                    break
                yield line
            except ValueError as e:
                if "Separator is not found" in str(e) or "limit" in str(e):
                    # Line too long - read in chunks until we find newline
                    chunk = await stream.read(1024 * 1024)  # 1MB chunks
                    if not chunk:
                        if buffer:
                            yield buffer
                        break
                    buffer += chunk
                    # Check for complete lines in buffer
                    while b"\n" in buffer:
                        line, buffer = buffer.split(b"\n", 1)
                        yield line + b"\n"
                else:
                    raise

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
                logger.warning("Progress callback failed", error=str(e))

        # Publish to Redis for dashboard
        if self.redis_client:
            try:
                await self.redis_client.xadd(
                    "barnabeenet:self_improvement:events",
                    {"data": json.dumps(event)},
                    maxlen=1000,
                )
            except Exception as e:
                logger.warning("Redis publish failed", error=str(e))

    def _parse_plan_block(self, text: str) -> dict[str, Any] | None:
        """Extract and parse a <PLAN> block from Claude's output."""
        plan_match = re.search(r"<PLAN>(.*?)</PLAN>", text, re.DOTALL)
        if not plan_match:
            return None

        plan_text = plan_match.group(1).strip()
        plan = {}

        # Parse each field
        for field_name in [
            "ISSUE",
            "ROOT_CAUSE",
            "PROPOSED_FIX",
            "FILES_AFFECTED",
            "RISKS",
            "TESTS",
        ]:
            pattern = rf"{field_name}:\s*(.+?)(?=\n[A-Z_]+:|$)"
            match = re.search(pattern, plan_text, re.DOTALL)
            if match:
                value = match.group(1).strip()
                # Convert FILES_AFFECTED to list
                if field_name == "FILES_AFFECTED":
                    plan[field_name.lower()] = [f.strip() for f in value.split(",")]
                else:
                    plan[field_name.lower()] = value

        return plan if plan else None

    async def improve(
        self,
        request: str,
        model: str = "opusplan",  # opusplan=Opus for planning/Sonnet for impl, opus, sonnet
        auto_approve: bool = False,
        max_turns: int = 50,
        source: str | None = None,  # "chat", "mark_as_wrong", "direct"
        trace_id: str | None = None,  # Link to original trace if from mark_as_wrong
    ) -> AsyncIterator[dict[str, Any]]:
        """Execute an improvement request.

        Args:
            request: Natural language description of what to improve
            model: Model to use ("sonnet" or "opus")
            auto_approve: Auto-commit without approval (dangerous!)
            max_turns: Maximum number of Claude Code turns

        Yields:
            Progress events as dictionaries
        """
        # Verify Claude Code is available
        if not self._verify_claude_code():
            yield {
                "event": "error",
                "error": "Claude Code CLI not available. Install with: npm install -g @anthropic-ai/claude-code",
            }
            return

        session_id = f"improve-{uuid.uuid4().hex[:8]}"
        session = ImprovementSession(
            session_id=session_id,
            request=request,
            model_used=f"claude-{model}-4-5",
        )
        self.active_sessions[session_id] = session

        try:
            # Phase 1: Create feature branch
            session.status = ImprovementStatus.DIAGNOSING
            branch_name = f"self-improve/{session_id}"
            session.branch_name = branch_name

            # Log session start to activity feed
            await self._log_activity(
                session,
                "start",
                f"🤖 Self-improvement started: {request[:50]}...",
                detail=f"Branch: {branch_name}\nModel: {model}",
                request=request,
                model=model,
            )

            await self._emit_progress(session, "started", {"branch": branch_name})
            yield {"event": "started", "session_id": session_id, "branch": branch_name}

            # Create branch
            try:
                await self._run_git_command(["checkout", "-b", branch_name])
            except RuntimeError:
                # Branch might already exist or we're already on it
                pass

            # Phase 2: Run Claude Code
            session.status = ImprovementStatus.DIAGNOSING

            await self._log_activity(
                session,
                "diagnosing",
                "🔍 Analyzing issue...",
            )

            await self._emit_progress(session, "diagnosing", {"message": "Analyzing issue..."})
            yield {"event": "diagnosing", "message": "Analyzing issue..."}

            # Get Claude CLI path
            claude_path = self._find_claude_path()
            if not claude_path:
                raise RuntimeError("Claude Code CLI not found")

            # Handle opusplan mode: use opus for diagnosis, sonnet for implementation
            diagnosis_model = model
            implementation_model = model
            if model == "opusplan":
                diagnosis_model = "opus"
                implementation_model = "sonnet"

            # Build Claude Code command
            # Using --print mode for non-interactive output with JSON streaming
            claude_cmd = [
                claude_path,
                "--print",
                "--model",
                diagnosis_model,
                "--output-format",
                "stream-json",
                "--verbose",  # Required for stream-json output format
                "--dangerously-skip-permissions",  # We're in a controlled environment
            ]

            # PHASE 2A: Run diagnosis/planning with DIAGNOSIS_SYSTEM_PROMPT
            claude_cmd.extend(["--append-system-prompt", DIAGNOSIS_SYSTEM_PROMPT])

            # Add the request as the prompt
            claude_cmd.append(request)

            logger.info(
                "Running Claude CLI (diagnosis phase)", command=" ".join(claude_cmd[:6]) + "..."
            )

            # Run Claude Code and stream output
            # Use larger buffer limit (10MB) to handle large JSON lines from Claude CLI
            # when it reads/outputs large file contents
            process = await asyncio.create_subprocess_exec(
                *claude_cmd,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE,
                cwd=self.project_path,
                limit=10 * 1024 * 1024,  # 10MB line buffer
            )
            session._process = process

            # Process output stream
            plan_detected = False
            if process.stdout is None:
                raise RuntimeError("Failed to capture Claude CLI stdout")
            async for line in self._read_lines_safe(process.stdout):
                if session.stop_requested:
                    process.terminate()
                    break

                try:
                    line_text = line.decode().strip()
                    if not line_text:
                        continue

                    # Try to parse as JSON event
                    try:
                        event_data = json.loads(line_text)
                        await self._process_claude_event(session, event_data)

                        # Check for plan in assistant messages
                        if event_data.get("type") == "assistant":
                            content = ""
                            for block in event_data.get("message", {}).get("content", []):
                                if block.get("type") == "text":
                                    content += block.get("text", "")

                            plan = self._parse_plan_block(content)
                            if plan and not plan_detected:
                                plan_detected = True
                                session.proposed_plan = plan

                                # Calculate safety score for the plan
                                safety_score = self._calculate_safety_score(plan)
                                session.safety_score = safety_score

                                session.status = ImprovementStatus.AWAITING_PLAN_APPROVAL

                                # Log to activity feed
                                await self._log_activity(
                                    session,
                                    "plan_proposed",
                                    f"📋 Plan proposed for: {request[:50]}...",
                                    detail=f"Safety score: {safety_score.score:.2f}",
                                    plan=plan,
                                    safety_score=safety_score.to_dict(),
                                )

                                # Send notification about plan (requires attention)
                                await self._notify_phase_change(
                                    session, "plan_proposed", requires_attention=True
                                )

                                await self._emit_progress(
                                    session,
                                    "plan_proposed",
                                    {"plan": plan, "safety_score": safety_score.to_dict()},
                                )
                                yield {
                                    "event": "plan_proposed",
                                    "plan": plan,
                                    "safety_score": safety_score.to_dict(),
                                }

                        yield {"event": "claude_event", "data": event_data}

                    except json.JSONDecodeError:
                        # Plain text output
                        session.current_thinking += line_text + "\n"
                        await self._emit_progress(session, "thinking", {"text": line_text})
                        yield {"event": "thinking", "text": line_text}

                except Exception as e:
                    logger.warning("Error processing Claude output", error=str(e))

            # Capture stderr for debugging
            stderr_output = ""
            if process.stderr:
                stderr_data = await process.stderr.read()
                stderr_output = stderr_data.decode() if stderr_data else ""
                if stderr_output:
                    logger.warning("Claude CLI stderr (diagnosis)", stderr=stderr_output[:500])
                    session.current_thinking += f"\n[STDERR]: {stderr_output}\n"

            await process.wait()

            # Check return code
            if process.returncode != 0:
                logger.error(
                    "Claude CLI exited with error (diagnosis)",
                    returncode=process.returncode,
                    stderr=stderr_output[:500],
                )
                session.error = (
                    f"Claude CLI error (code {process.returncode}): {stderr_output[:200]}"
                )

            if session.stop_requested:
                session.status = ImprovementStatus.STOPPED
                yield {"event": "stopped", "session_id": session_id}
                return

            # PHASE 2B: Wait for plan approval if a plan was proposed
            if plan_detected and session.proposed_plan:
                logger.info("Plan proposed, waiting for approval", session_id=session_id)

                # Check if plan can be auto-approved based on safety score
                if (
                    session.safety_score
                    and session.safety_score.can_auto_approve
                    and not auto_approve  # Don't double-auto-approve
                ):
                    logger.info(
                        "Plan auto-approved based on safety score",
                        session_id=session_id,
                        safety_score=session.safety_score.score,
                    )

                    # Log auto-approval
                    await self._log_activity(
                        session,
                        "plan_approved",
                        f"✅ Plan auto-approved (safety: {session.safety_score.score:.0%})",
                        detail="High safety score allowed automatic approval",
                    )

                    # Notify about auto-approval
                    await self._notify_phase_change(session, "plan_auto_approved")

                    # Skip waiting, go straight to implementation
                    approval_message = "AUTO_APPROVED based on high safety score."
                    session.status = ImprovementStatus.IMPLEMENTING
                else:
                    # Wait for user approval or rejection
                    # The status is already AWAITING_PLAN_APPROVAL
                    # User calls approve_plan() or reject_plan() which puts message in queue
                    try:
                        approval_message = await asyncio.wait_for(
                            session.user_input_queue.get(),
                            timeout=3600,  # 1 hour timeout
                        )
                        logger.info(
                            "Received plan approval/rejection",
                            session_id=session_id,
                            message=approval_message[:100],
                        )
                    except TimeoutError:
                        session.status = ImprovementStatus.FAILED
                        session.error = "Plan approval timed out after 1 hour"

                        await self._log_activity(
                            session,
                            "failed",
                            "⏰ Plan approval timed out",
                            detail="No response received within 1 hour",
                        )

                        yield {"event": "error", "error": session.error}
                        return

                if session.stop_requested:
                    session.status = ImprovementStatus.STOPPED

                    await self._log_activity(
                        session,
                        "stopped",
                        "🛑 Session stopped by user",
                    )

                    yield {"event": "stopped", "session_id": session_id}
                    return

                # Check if it was a rejection (plan rejected returns to DIAGNOSING)
                if session.status == ImprovementStatus.DIAGNOSING:
                    # Plan was rejected - loop back or handle as needed
                    # For now, mark as completed with feedback
                    session.status = ImprovementStatus.COMPLETED
                    session.success = False
                    session.summary = f"Plan rejected: {approval_message}"

                    await self._log_activity(
                        session,
                        "stopped",
                        f"❌ Plan rejected: {approval_message[:50]}...",
                    )

                    yield {"event": "completed", "message": session.summary}
                    return

                # Plan approved - run implementation phase
                session.status = ImprovementStatus.IMPLEMENTING

                await self._log_activity(
                    session,
                    "implementing",
                    "🔧 Implementing approved plan...",
                    detail=f"Request: {request[:100]}",
                )

                await self._emit_progress(
                    session, "implementing", {"message": "Implementing approved plan..."}
                )
                yield {"event": "implementing", "message": "Implementing approved plan..."}

                # Format the approved plan for the implementation prompt
                plan_text = "\n".join(f"{k}: {v}" for k, v in session.proposed_plan.items())
                user_guidance = ""
                if "Additional guidance:" in approval_message:
                    user_guidance = f"User guidance: {approval_message.split('Additional guidance:')[1].strip()}"

                impl_system_prompt = IMPLEMENTATION_SYSTEM_PROMPT.format(
                    approved_plan=plan_text,
                    user_guidance=user_guidance,
                )

                # Build implementation command (uses implementation_model for opusplan mode)
                impl_cmd = [
                    claude_path,
                    "--print",
                    "--model",
                    implementation_model,
                    "--output-format",
                    "stream-json",
                    "--verbose",
                    "--dangerously-skip-permissions",
                ]
                impl_cmd.extend(["--append-system-prompt", impl_system_prompt])
                impl_cmd.append(f"Implement this approved plan: {request}")

                logger.info(
                    "Running Claude CLI (implementation phase)",
                    command=" ".join(impl_cmd[:6]) + "...",
                )

                # Run implementation
                impl_process = await asyncio.create_subprocess_exec(
                    *impl_cmd,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE,
                    cwd=self.project_path,
                    limit=10 * 1024 * 1024,
                )
                session._process = impl_process

                if impl_process.stdout is None:
                    raise RuntimeError("Failed to capture Claude CLI stdout (implementation)")

                async for line in self._read_lines_safe(impl_process.stdout):
                    if session.stop_requested:
                        impl_process.terminate()
                        break

                    try:
                        line_text = line.decode().strip()
                        if not line_text:
                            continue

                        try:
                            event_data = json.loads(line_text)
                            await self._process_claude_event(session, event_data)
                            yield {"event": "claude_event", "data": event_data}
                        except json.JSONDecodeError:
                            session.current_thinking += line_text + "\n"
                            await self._emit_progress(session, "thinking", {"text": line_text})
                            yield {"event": "thinking", "text": line_text}

                    except Exception as e:
                        logger.warning("Error processing Claude output", error=str(e))

                # Capture implementation stderr
                if impl_process.stderr:
                    impl_stderr = await impl_process.stderr.read()
                    if impl_stderr:
                        stderr_text = impl_stderr.decode()
                        logger.warning("Claude CLI stderr (impl)", stderr=stderr_text[:500])
                        session.current_thinking += f"\n[IMPL STDERR]: {stderr_text}\n"

                await impl_process.wait()

            # Phase 3: Collect results
            session.status = ImprovementStatus.TESTING

            await self._log_activity(
                session,
                "testing",
                "🧪 Checking changes...",
            )

            await self._emit_progress(session, "testing", {"message": "Checking changes..."})

            # Get git diff
            diff_result = await self._run_git_command(["diff", "--stat"])
            session.git_diff = diff_result

            # Get modified files
            files_result = await self._run_git_command(["diff", "--name-only"])
            session.files_modified = (
                files_result.strip().split("\n") if files_result.strip() else []
            )

            await self._emit_progress(
                session,
                "changes_ready",
                {
                    "files_modified": session.files_modified,
                    "diff_stats": diff_result,
                    "estimated_api_cost_usd": session.token_usage.calculate_api_cost(
                        session.model_used
                    ),
                },
            )
            yield {
                "event": "changes_ready",
                "files": session.files_modified,
                "diff": diff_result,
                "estimated_cost": session.token_usage.calculate_api_cost(session.model_used),
            }

            # Phase 4: Await approval (unless auto_approve)
            if not auto_approve and session.files_modified:
                session.status = ImprovementStatus.AWAITING_APPROVAL

                files_summary = f"{len(session.files_modified)} file(s): {', '.join(session.files_modified[:3])}"
                if len(session.files_modified) > 3:
                    files_summary += f" +{len(session.files_modified) - 3} more"

                await self._log_activity(
                    session,
                    "awaiting_approval",
                    f"✅ Changes ready for review: {files_summary}",
                    detail=diff_result,
                    files_modified=session.files_modified,
                )

                # Send notification that changes are ready to commit (requires attention)
                await self._notify_phase_change(session, "awaiting_commit", requires_attention=True)

                await self._emit_progress(
                    session,
                    "awaiting_approval",
                    {"message": "Changes ready for review. Call approve_session() to commit."},
                )
                yield {"event": "awaiting_approval", "session_id": session_id}
            elif session.files_modified:
                # Auto-approve: commit directly
                await self.approve_session(session_id)
                yield {"event": "auto_approved", "commit": session.commit_hash}
            else:
                session.status = ImprovementStatus.COMPLETED
                session.success = True
                session.summary = "No changes needed"

                await self._log_activity(
                    session,
                    "committed",  # Use committed as closest match
                    "✓ Analysis complete - no changes needed",
                )

                yield {"event": "completed", "message": "No changes needed"}

        except Exception as e:
            session.status = ImprovementStatus.FAILED
            session.error = str(e)
            logger.error("Improvement failed", error=str(e), session_id=session_id)

            await self._log_activity(
                session,
                "failed",
                f"❌ Improvement failed: {str(e)[:50]}...",
                detail=str(e),
            )

            await self._emit_progress(session, "error", {"error": str(e)})
            yield {"event": "error", "error": str(e)}

            # Return to main branch on failure
            try:
                await self._run_git_command(["checkout", "main"])
            except Exception:
                pass

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
            message = event.get("message", {})
            content = message.get("content", [])
            for block in content:
                if block.get("type") == "text":
                    session.messages.append({"role": "assistant", "content": block.get("text", "")})

        elif event_type == "tool_use":
            # Tool usage (bash, read, write, etc.)
            tool = event.get("name", "unknown")
            tool_input = event.get("input", {})

            op = ClaudeCodeOperation(
                operation_id=str(uuid.uuid4())[:8],
                timestamp=datetime.now(),
                operation_type=tool,
                command=tool_input.get("command"),
                file_path=tool_input.get("file_path"),
            )
            session.operations.append(op)

        elif event_type == "result":
            # Final result with usage stats
            usage = event.get("usage", {})
            session.token_usage.add(
                TokenUsage(
                    input_tokens=usage.get("input_tokens", 0),
                    output_tokens=usage.get("output_tokens", 0),
                    cache_read_tokens=usage.get("cache_read_input_tokens", 0),
                    cache_write_tokens=usage.get("cache_creation_input_tokens", 0),
                )
            )
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

            # Commit
            commit_msg = f"self-improve: {session.request[:50]}..."
            await self._run_git_command(["commit", "-m", commit_msg])

            # Get commit hash
            hash_result = await self._run_git_command(["rev-parse", "HEAD"])
            session.commit_hash = hash_result.strip()

            # Merge to main
            await self._run_git_command(["checkout", "main"])
            if session.branch_name:
                await self._run_git_command(["merge", session.branch_name])

                # Delete feature branch
                await self._run_git_command(["branch", "-d", session.branch_name])

            session.status = ImprovementStatus.COMPLETED
            session.success = True
            session.completed_at = datetime.now()

            # Log to activity feed
            files_summary = f"{len(session.files_modified)} file(s)"
            await self._log_activity(
                session,
                "committed",
                f"🚀 Changes committed: {files_summary}",
                detail=f"Commit: {session.commit_hash}\nRequest: {session.request}",
                commit_hash=session.commit_hash,
                files_modified=session.files_modified,
            )

            # Send notification about successful commit
            await self._notify_phase_change(session, "committed")

            await self._emit_progress(
                session,
                "committed",
                {"commit_hash": session.commit_hash},
            )

            return {
                "status": "committed",
                "session_id": session_id,
                "commit_hash": session.commit_hash,
                "files_modified": session.files_modified,
            }

        except Exception as e:
            session.status = ImprovementStatus.FAILED
            session.error = str(e)

            await self._log_activity(
                session,
                "failed",
                f"❌ Commit failed: {str(e)[:50]}...",
                detail=str(e),
            )

            # Notify about failure
            await self._notify_phase_change(session, "failed")

            raise

    async def reject_session(self, session_id: str) -> dict[str, Any]:
        """Reject changes and return to main branch."""
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        # Discard changes and return to main
        try:
            await self._run_git_command(["checkout", "main"])
            if session.branch_name:
                await self._run_git_command(["branch", "-D", session.branch_name])
        except Exception as e:
            logger.warning("Git cleanup failed", error=str(e))

        session.status = ImprovementStatus.REJECTED
        session.completed_at = datetime.now()

        await self._emit_progress(
            session, "rejected", {"message": "Changes rejected and discarded"}
        )

        return {"status": "rejected", "session_id": session_id}

    async def stop_session(self, session_id: str) -> dict[str, Any]:
        """Stop an active session immediately."""
        session = self.active_sessions.get(session_id)
        if not session:
            raise ValueError(f"Session not found: {session_id}")

        session.stop_requested = True

        # Kill the process if running
        if session._process and session._process.returncode is None:
            session._process.terminate()

        session.status = ImprovementStatus.STOPPED
        session.completed_at = datetime.now()

        await self._emit_progress(session, "stopped", {"message": "Session stopped by user"})

        # Return to main branch if we created one
        if session.branch_name:
            try:
                await self._run_git_command(["checkout", "main"])
                await self._run_git_command(["branch", "-D", session.branch_name])
            except Exception as e:
                logger.warning("Git cleanup failed", error=str(e))

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

        await self._emit_progress(session, "user_input", {"message": message})

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

        await self._emit_progress(session, "plan_approved", {"feedback": feedback})

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

        await self._emit_progress(session, "plan_rejected", {"reason": reason})

        return {"status": "rejected", "session_id": session_id, "reason": reason}

    async def _run_git_command(self, args: list[str]) -> str:
        """Run a git command and return output."""
        process = await asyncio.create_subprocess_exec(
            "git",
            *args,
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
        total_cache_read = sum(
            s.token_usage.cache_read_tokens for s in self.active_sessions.values()
        )
        total_cache_write = sum(
            s.token_usage.cache_write_tokens for s in self.active_sessions.values()
        )

        total_usage = TokenUsage(
            input_tokens=total_input,
            output_tokens=total_output,
            cache_read_tokens=total_cache_read,
            cache_write_tokens=total_cache_write,
        )

        # Calculate costs for different models
        sonnet_cost = total_usage.calculate_api_cost("claude-sonnet-4-5")
        opus_cost = total_usage.calculate_api_cost("claude-opus-4-5")

        successful = sum(1 for s in self.active_sessions.values() if s.success)

        return {
            "total_sessions": len(self.active_sessions),
            "successful_sessions": successful,
            "total_tokens": {
                "input": total_input,
                "output": total_output,
                "cache_read": total_cache_read,
                "cache_write": total_cache_write,
                "total": total_input + total_output,
            },
            "estimated_api_costs": {
                "sonnet": f"${sonnet_cost:.4f}",
                "opus": f"${opus_cost:.4f}",
            },
            "subscription_cost": "$0.00 (included in Max subscription)",
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
        from barnabeenet.main import app_state

        # Get project path (parent of src)
        project_path = Path(__file__).parent.parent.parent.parent

        _agent_instance = SelfImprovementAgent(
            project_path=project_path,
            redis_client=app_state.redis_client,
        )
    return _agent_instance


def reset_agent() -> None:
    """Reset the agent singleton (for testing)."""
    global _agent_instance
    _agent_instance = None
