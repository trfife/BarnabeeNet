# CLAUDE.md - Persistent Context for Claude Code

This file provides persistent context for Claude Code sessions working on BarnabeeNet.

## Code Style Requirements

- **Python Version:** 3.12+ with strict typing (type hints required for all functions)
- **Formatting:** Use `ruff` for formatting (run `ruff format` before committing)
- **Async-First:** Use `async def` and `await` for all I/O operations
- **Models:** Pydantic v2 with `BaseModel` and `ConfigDict` (not class-based config)
- **Naming:**
  - `snake_case` for functions and variables
  - `PascalCase` for classes
  - `UPPER_CASE` for constants
- **Docstrings:** Google style for all public functions
- **Line Length:** 100 characters max
- **Import Order:** stdlib → third-party → local
- **Logging:** Use `structlog` for structured logging

## Testing Requirements

- **Test Runner:** `pytest` with `pytest-testmon` for incremental testing
- **Test Structure:**
  - Use pytest fixtures for setup
  - Mock external dependencies (Redis, HA, LLM)
  - Test both success and error paths
  - Use descriptive test names: `test_{function}_{scenario}_{expected_result}`
- **Coverage:** Aim for >80% on new code
- **Before Committing:** Run full suite with `pytest --no-testmon`
- **Test Files:** Place in `tests/test_{module}.py`

## Git Workflow

- **Branch Naming:** `self-improve/{session_id}` for self-improvement sessions
- **Commit Messages:** `{type}: {description}`
  - Types: `fix`, `feat`, `docs`, `refactor`, `test`, `chore`
  - Example: `fix: correct timezone calculation in interaction agent`
- **Never Commit:** Secrets, `.env` files, or sensitive data
- **Before Commit:** Run tests and ensure code passes linting
- **Commits:** Keep atomic (one logical change per commit)

## Environment Context

- **Python:** 3.12.3
- **Virtual Environment:** `.venv/` (activate with `source .venv/bin/activate`)
- **Key Dependencies:** FastAPI, Redis, Pydantic v2, structlog
- **Redis:** Running on localhost:6379 (local) or 192.168.86.51:6379 (VM)
- **Working Directory:** Project root (where `pyproject.toml` is)
- **Project Structure:** See architecture reference in system prompts

## Error Handling Patterns

- **Network Errors:** Retry with exponential backoff (max 3 attempts)
- **File Not Found:** Check alternative paths, log helpful error message
- **Permission Errors:** Suggest fix, don't fail silently
- **Import Errors:** Check virtual environment, verify dependencies in `requirements.txt`
- **Test Failures:** Show full traceback, suggest specific fixes
- **LLM API Errors:** Handle 401 (auth), 402 (payment), 403 (forbidden), 404 (model unavailable), 429 (rate limit), 5xx (server error) with user-friendly messages

## Technical Constraints

- **Python:** 3.12+ only (no older versions)
- **Async Operations:** No blocking I/O in async functions
- **File Size Limits:** Maximum 10MB for file operations
- **Test Timeout:** 30 seconds per test
- **Memory:** Be mindful of large data structures (use generators for large datasets)
- **Dependencies:** Check `requirements.txt` and `pyproject.toml` before adding new packages

## Common Bash Commands

- **Run Tests:** `pytest` (incremental) or `pytest --no-testmon` (full)
- **Format Code:** `ruff format .`
- **Lint Code:** `ruff check .`
- **Check Git Status:** `git status`
- **View Logs:** `./scripts/debug-logs.sh {type}` (traces, errors, activity, etc.)
- **Restart Service:** `bash scripts/restart.sh` (on VM)

## Repository Etiquette

- **Code Reviews:** Self-improvement agent commits go through approval workflow
- **Breaking Changes:** Document in commit message and update relevant docs
- **Documentation:** Update `CONTEXT.md` and relevant docs when making significant changes
- **Backwards Compatibility:** Maintain API compatibility when possible
- **Deprecation:** Mark deprecated code with `@deprecated` decorator and add migration notes
