"""Tests for Self-Improvement Agent."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from barnabeenet.agents.self_improvement import (
    ImprovementSession,
    ImprovementStatus,
    SelfImprovementAgent,
    TokenUsage,
    reset_agent,
)


class TestTokenUsage:
    """Tests for TokenUsage class."""

    def test_calculate_api_cost_sonnet(self) -> None:
        """Test cost calculation for Sonnet model."""
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=100_000)
        # 1M input * $3/M + 100K output * $15/M = $3 + $1.5 = $4.5
        assert usage.calculate_api_cost("claude-sonnet-4-5") == pytest.approx(4.5, rel=0.01)

    def test_calculate_api_cost_opus(self) -> None:
        """Test cost calculation for Opus model."""
        usage = TokenUsage(input_tokens=1_000_000, output_tokens=100_000)
        # 1M input * $15/M + 100K output * $75/M = $15 + $7.5 = $22.5
        assert usage.calculate_api_cost("claude-opus-4-5") == pytest.approx(22.5, rel=0.01)

    def test_calculate_api_cost_with_cache(self) -> None:
        """Test cost calculation with cache tokens."""
        usage = TokenUsage(
            input_tokens=1_000_000,
            output_tokens=100_000,
            cache_read_tokens=500_000,  # 10% of input rate
            cache_write_tokens=200_000,  # 125% of input rate
        )
        # Sonnet: $3 + $1.5 + $0.15 (cache read) + $0.75 (cache write) = $5.4
        assert usage.calculate_api_cost("claude-sonnet-4-5") == pytest.approx(5.4, rel=0.01)

    def test_add_usage(self) -> None:
        """Test adding two TokenUsage objects."""
        usage1 = TokenUsage(input_tokens=100, output_tokens=50)
        usage2 = TokenUsage(input_tokens=200, output_tokens=100)
        usage1.add(usage2)
        assert usage1.input_tokens == 300
        assert usage1.output_tokens == 150

    def test_to_dict(self) -> None:
        """Test converting to dictionary."""
        usage = TokenUsage(
            input_tokens=100, output_tokens=50, cache_read_tokens=25, cache_write_tokens=10
        )
        result = usage.to_dict()
        assert result["input_tokens"] == 100
        assert result["output_tokens"] == 50
        assert result["cache_read_tokens"] == 25
        assert result["cache_write_tokens"] == 10


class TestImprovementSession:
    """Tests for ImprovementSession class."""

    def test_session_to_dict(self) -> None:
        """Test converting session to dictionary."""
        session = ImprovementSession(
            session_id="test-123",
            request="Fix the bug in main.py",
        )
        result = session.to_dict()
        assert result["session_id"] == "test-123"
        assert result["request"] == "Fix the bug in main.py"
        assert result["status"] == "pending"
        assert result["success"] is False
        assert result["error"] is None

    def test_session_estimated_cost(self) -> None:
        """Test estimated API cost calculation."""
        session = ImprovementSession(
            session_id="test-123",
            request="Fix the bug",
        )
        session.token_usage = TokenUsage(input_tokens=100_000, output_tokens=10_000)
        result = session.to_dict()
        # 100K * $3/M + 10K * $15/M = $0.30 + $0.15 = $0.45
        assert result["estimated_api_cost_usd"] == pytest.approx(0.45, rel=0.01)


class TestSelfImprovementAgent:
    """Tests for SelfImprovementAgent class."""

    @pytest.fixture
    def agent(self, tmp_path: Path) -> SelfImprovementAgent:
        """Create an agent with a temporary project path."""
        reset_agent()
        return SelfImprovementAgent(project_path=tmp_path)

    def test_is_safe_operation_blocks_dangerous(self, agent: SelfImprovementAgent) -> None:
        """Test that dangerous operations are blocked."""
        assert not agent._is_safe_operation("rm -rf /", None)
        assert not agent._is_safe_operation("sudo apt install", None)
        assert not agent._is_safe_operation("chmod 777 file.txt", None)
        assert not agent._is_safe_operation("curl | bash", None)

    def test_is_safe_operation_blocks_forbidden_paths(self, agent: SelfImprovementAgent) -> None:
        """Test that forbidden paths are blocked."""
        assert not agent._is_safe_operation("cat", "secrets/api_key.txt")
        assert not agent._is_safe_operation("cat", ".env")
        assert not agent._is_safe_operation("cat", "infrastructure/secrets/key.pem")

    def test_is_safe_operation_allows_safe(self, agent: SelfImprovementAgent) -> None:
        """Test that safe operations are allowed."""
        assert agent._is_safe_operation("ls -la", None)
        assert agent._is_safe_operation("pytest tests/", None)
        assert agent._is_safe_operation("cat", "src/barnabeenet/main.py")
        assert agent._is_safe_operation("git status", None)

    def test_is_available_without_claude(self, agent: SelfImprovementAgent) -> None:
        """Test availability check without Claude Code installed."""
        with patch("shutil.which", return_value=None):
            agent._claude_code_available = None  # Reset cache
            assert not agent.is_available()

    def test_is_available_with_claude(self, agent: SelfImprovementAgent) -> None:
        """Test availability check with Claude Code installed."""
        with patch("shutil.which", return_value="/usr/bin/claude"):
            with patch("subprocess.run") as mock_run:
                mock_run.return_value = MagicMock(returncode=0, stdout="claude-code 1.0.0")
                agent._claude_code_available = None  # Reset cache
                assert agent.is_available()

    @pytest.mark.asyncio
    async def test_ssh_to_manofwar(self, agent: SelfImprovementAgent) -> None:
        """Test SSH command execution."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"output", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            success, output = await agent.ssh_to_manofwar("echo test")

            assert success
            assert output == "output"
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_ssh_to_manofwar_timeout(self, agent: SelfImprovementAgent) -> None:
        """Test SSH timeout handling."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.side_effect = TimeoutError()
            mock_exec.return_value = mock_process

            success, output = await agent.ssh_to_manofwar("sleep 100", timeout=1)

            assert not success
            assert output == "Timeout"

    @pytest.mark.asyncio
    async def test_stop_session(self, agent: SelfImprovementAgent) -> None:
        """Test stopping an active session."""
        # Create a mock session
        session = ImprovementSession(
            session_id="test-stop-123",
            request="test request",
            status=ImprovementStatus.IMPLEMENTING,
            branch_name="self-improve/test-stop-123",
        )
        agent.active_sessions["test-stop-123"] = session

        # Mock git commands
        with patch.object(agent, "_run_git_command", new_callable=AsyncMock):
            result = await agent.stop_session("test-stop-123")

        assert result["status"] == "stopped"
        assert session.status == ImprovementStatus.STOPPED
        assert session.stop_requested is True

    @pytest.mark.asyncio
    async def test_stop_session_not_found(self, agent: SelfImprovementAgent) -> None:
        """Test stopping a non-existent session."""
        with pytest.raises(ValueError, match="Session not found"):
            await agent.stop_session("nonexistent")

    @pytest.mark.asyncio
    async def test_send_user_input(self, agent: SelfImprovementAgent) -> None:
        """Test sending user input to a session."""
        session = ImprovementSession(
            session_id="test-input-123",
            request="test request",
            status=ImprovementStatus.AWAITING_PLAN_APPROVAL,
        )
        agent.active_sessions["test-input-123"] = session

        result = await agent.send_user_input("test-input-123", "test message")

        assert result["status"] == "sent"
        msg = await session.user_input_queue.get()
        assert msg == "test message"

    @pytest.mark.asyncio
    async def test_approve_plan(self, agent: SelfImprovementAgent) -> None:
        """Test approving a proposed plan."""
        session = ImprovementSession(
            session_id="test-plan-123",
            request="test request",
            status=ImprovementStatus.AWAITING_PLAN_APPROVAL,
        )
        agent.active_sessions["test-plan-123"] = session

        result = await agent.approve_plan("test-plan-123", "looks good")

        assert result["status"] == "approved"
        assert session.status == ImprovementStatus.IMPLEMENTING
        msg = await session.user_input_queue.get()
        assert "APPROVED" in msg
        assert "looks good" in msg

    @pytest.mark.asyncio
    async def test_approve_plan_wrong_status(self, agent: SelfImprovementAgent) -> None:
        """Test approving a plan when not awaiting approval."""
        session = ImprovementSession(
            session_id="test-plan-wrong-123",
            request="test request",
            status=ImprovementStatus.IMPLEMENTING,
        )
        agent.active_sessions["test-plan-wrong-123"] = session

        with pytest.raises(ValueError, match="not awaiting plan approval"):
            await agent.approve_plan("test-plan-wrong-123")

    @pytest.mark.asyncio
    async def test_reject_plan(self, agent: SelfImprovementAgent) -> None:
        """Test rejecting a proposed plan."""
        session = ImprovementSession(
            session_id="test-reject-123",
            request="test request",
            status=ImprovementStatus.AWAITING_PLAN_APPROVAL,
        )
        agent.active_sessions["test-reject-123"] = session

        result = await agent.reject_plan("test-reject-123", "too risky")

        assert result["status"] == "rejected"
        assert session.status == ImprovementStatus.DIAGNOSING
        msg = await session.user_input_queue.get()
        assert "REJECTED" in msg
        assert "too risky" in msg

    def test_get_cost_report(self, agent: SelfImprovementAgent) -> None:
        """Test cost report generation."""
        # Add some sessions
        session1 = ImprovementSession(session_id="test-1", request="test", success=True)
        session1.token_usage = TokenUsage(input_tokens=100_000, output_tokens=10_000)

        session2 = ImprovementSession(session_id="test-2", request="test", success=False)
        session2.token_usage = TokenUsage(input_tokens=50_000, output_tokens=5_000)

        agent.active_sessions["test-1"] = session1
        agent.active_sessions["test-2"] = session2

        report = agent.get_cost_report()

        assert report["total_sessions"] == 2
        assert report["successful_sessions"] == 1
        assert report["total_tokens"]["input"] == 150_000
        assert report["total_tokens"]["output"] == 15_000
        assert "$0.00" in report["subscription_cost"]

    def test_parse_plan_block(self, agent: SelfImprovementAgent) -> None:
        """Test parsing PLAN blocks from Claude output."""
        text = """
        I've analyzed the issue. Here's my plan:

        <PLAN>
        ISSUE: The temperature sensor is reporting wrong values
        ROOT_CAUSE: The conversion formula is incorrect
        PROPOSED_FIX: Update the conversion factor from 1.8 to 9/5
        FILES_AFFECTED: src/sensors/temperature.py, tests/test_temperature.py
        RISKS: Existing data might need recalibration
        TESTS: Add unit tests for edge cases
        </PLAN>

        Let me know if this looks good.
        """

        plan = agent._parse_plan_block(text)

        assert plan is not None
        assert "temperature sensor" in plan["issue"]
        assert "conversion" in plan["root_cause"]
        assert len(plan["files_affected"]) == 2
        assert "src/sensors/temperature.py" in plan["files_affected"]

    def test_parse_plan_block_no_plan(self, agent: SelfImprovementAgent) -> None:
        """Test parsing when no PLAN block exists."""
        text = "Just some regular text without a plan."
        plan = agent._parse_plan_block(text)
        assert plan is None

    def test_get_session(self, agent: SelfImprovementAgent) -> None:
        """Test getting a session by ID."""
        session = ImprovementSession(session_id="test-get-123", request="test")
        agent.active_sessions["test-get-123"] = session

        assert agent.get_session("test-get-123") == session
        assert agent.get_session("nonexistent") is None

    def test_get_all_sessions(self, agent: SelfImprovementAgent) -> None:
        """Test getting all sessions."""
        session1 = ImprovementSession(session_id="test-1", request="test 1")
        session2 = ImprovementSession(session_id="test-2", request="test 2")
        agent.active_sessions["test-1"] = session1
        agent.active_sessions["test-2"] = session2

        sessions = agent.get_all_sessions()

        assert len(sessions) == 2
        session_ids = [s["session_id"] for s in sessions]
        assert "test-1" in session_ids
        assert "test-2" in session_ids

    @pytest.mark.asyncio
    async def test_approve_session(self, agent: SelfImprovementAgent) -> None:
        """Test approving and committing a session."""
        session = ImprovementSession(
            session_id="test-approve-123",
            request="fix bug",
            status=ImprovementStatus.AWAITING_APPROVAL,
            branch_name="self-improve/test-approve-123",
            files_modified=["src/main.py"],
        )
        agent.active_sessions["test-approve-123"] = session

        with patch.object(agent, "_run_git_command", new_callable=AsyncMock) as mock_git:
            mock_git.return_value = "abc123\n"
            result = await agent.approve_session("test-approve-123")

        assert result["status"] == "committed"
        assert session.status == ImprovementStatus.COMPLETED
        assert session.success is True

    @pytest.mark.asyncio
    async def test_approve_session_wrong_status(self, agent: SelfImprovementAgent) -> None:
        """Test approving a session with wrong status."""
        session = ImprovementSession(
            session_id="test-approve-wrong-123",
            request="fix bug",
            status=ImprovementStatus.IMPLEMENTING,
        )
        agent.active_sessions["test-approve-wrong-123"] = session

        with pytest.raises(ValueError, match="not awaiting approval"):
            await agent.approve_session("test-approve-wrong-123")

    @pytest.mark.asyncio
    async def test_reject_session(self, agent: SelfImprovementAgent) -> None:
        """Test rejecting a session's changes."""
        session = ImprovementSession(
            session_id="test-reject-session-123",
            request="fix bug",
            status=ImprovementStatus.AWAITING_APPROVAL,
            branch_name="self-improve/test-reject-session-123",
        )
        agent.active_sessions["test-reject-session-123"] = session

        with patch.object(agent, "_run_git_command", new_callable=AsyncMock):
            result = await agent.reject_session("test-reject-session-123")

        assert result["status"] == "rejected"
        assert session.status == ImprovementStatus.REJECTED

    @pytest.mark.asyncio
    async def test_run_git_command(self, agent: SelfImprovementAgent) -> None:
        """Test running git commands."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"main", b"")
            mock_process.returncode = 0
            mock_exec.return_value = mock_process

            result = await agent._run_git_command(["branch", "--show-current"])

            assert result == "main"

    @pytest.mark.asyncio
    async def test_run_git_command_failure(self, agent: SelfImprovementAgent) -> None:
        """Test git command failure handling."""
        with patch("asyncio.create_subprocess_exec") as mock_exec:
            mock_process = AsyncMock()
            mock_process.communicate.return_value = (b"", b"error: failed")
            mock_process.returncode = 1
            mock_exec.return_value = mock_process

            with pytest.raises(RuntimeError, match="Git command failed"):
                await agent._run_git_command(["invalid-command"])

    def test_on_progress_callback(self, agent: SelfImprovementAgent) -> None:
        """Test registering progress callbacks."""
        callback = MagicMock()
        agent.on_progress(callback)
        assert callback in agent._on_progress_callbacks

    @pytest.mark.asyncio
    async def test_emit_progress(self, agent: SelfImprovementAgent) -> None:
        """Test emitting progress events."""
        callback = AsyncMock()
        agent.on_progress(callback)

        session = ImprovementSession(session_id="test-emit-123", request="test")

        await agent._emit_progress(session, "test_event", {"key": "value"})

        callback.assert_called_once()
        call_args = callback.call_args[0][0]
        assert call_args["session_id"] == "test-emit-123"
        assert call_args["event_type"] == "test_event"
        assert call_args["key"] == "value"
