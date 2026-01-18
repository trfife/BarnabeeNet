"""Prompts API - View and manage agent system prompts.

Provides endpoints for:
- Listing all agent prompts
- Viewing specific prompts
- Updating prompts with version history
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from fastapi import APIRouter, HTTPException
from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/prompts", tags=["Prompts"])

# Prompts directory
PROMPTS_DIR = Path(__file__).parent.parent.parent / "prompts"

# In-memory version history (could be persisted to Redis)
_prompt_history: dict[str, list[dict[str, Any]]] = {}


# =============================================================================
# Models
# =============================================================================


class PromptInfo(BaseModel):
    """Information about an agent's prompt."""

    agent_name: str
    file_name: str
    content: str
    last_modified: datetime | None = None
    version: int = 1
    history_count: int = 0


class PromptListItem(BaseModel):
    """Summary of a prompt for listing."""

    agent_name: str
    file_name: str
    preview: str = Field(description="First 200 chars of content")
    last_modified: datetime | None = None
    version: int = 1


class PromptUpdate(BaseModel):
    """Request to update a prompt."""

    content: str = Field(..., min_length=10)


class PromptHistoryItem(BaseModel):
    """A historical version of a prompt."""

    version: int
    content: str
    updated_at: datetime
    updated_by: str = "dashboard"


# =============================================================================
# Agent Info
# =============================================================================

AGENT_INFO = {
    "meta_agent": {
        "display_name": "MetaAgent",
        "description": "Intent classification and routing",
        "icon": "🎯",
    },
    "instant_agent": {
        "display_name": "InstantAgent",
        "description": "Zero-latency pattern responses (no LLM)",
        "icon": "⚡",
    },
    "action_agent": {
        "display_name": "ActionAgent",
        "description": "Device control and action parsing",
        "icon": "🎮",
    },
    "interaction_agent": {
        "display_name": "InteractionAgent",
        "description": "Complex conversations with Barnabee persona",
        "icon": "💬",
    },
    "memory_agent": {
        "display_name": "MemoryAgent",
        "description": "Memory storage and retrieval",
        "icon": "🧠",
    },
}


# =============================================================================
# Routes
# =============================================================================


@router.get("/", response_model=list[PromptListItem])
async def list_prompts() -> list[PromptListItem]:
    """List all agent prompts."""
    prompts = []

    if not PROMPTS_DIR.exists():
        logger.warning("Prompts directory not found: %s", PROMPTS_DIR)
        return prompts

    for file_path in sorted(PROMPTS_DIR.glob("*.txt")):
        agent_name = file_path.stem
        try:
            content = file_path.read_text(encoding="utf-8")
            stat = file_path.stat()

            prompts.append(
                PromptListItem(
                    agent_name=agent_name,
                    file_name=file_path.name,
                    preview=content[:200] + "..." if len(content) > 200 else content,
                    last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
                    version=len(_prompt_history.get(agent_name, [])) + 1,
                )
            )
        except Exception as e:
            logger.error("Failed to read prompt %s: %s", file_path, e)

    return prompts


@router.get("/{agent_name}", response_model=PromptInfo)
async def get_prompt(agent_name: str) -> PromptInfo:
    """Get a specific agent's prompt."""
    file_path = PROMPTS_DIR / f"{agent_name}.txt"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Prompt not found: {agent_name}")

    try:
        content = file_path.read_text(encoding="utf-8")
        stat = file_path.stat()

        history = _prompt_history.get(agent_name, [])

        return PromptInfo(
            agent_name=agent_name,
            file_name=file_path.name,
            content=content,
            last_modified=datetime.fromtimestamp(stat.st_mtime, tz=UTC),
            version=len(history) + 1,
            history_count=len(history),
        )
    except Exception as e:
        logger.error("Failed to read prompt %s: %s", agent_name, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.put("/{agent_name}")
async def update_prompt(agent_name: str, update: PromptUpdate) -> dict[str, Any]:
    """Update an agent's prompt with backup."""
    file_path = PROMPTS_DIR / f"{agent_name}.txt"

    if not file_path.exists():
        raise HTTPException(status_code=404, detail=f"Prompt not found: {agent_name}")

    try:
        # Read current content for history
        current_content = file_path.read_text(encoding="utf-8")

        # Save to history
        if agent_name not in _prompt_history:
            _prompt_history[agent_name] = []

        _prompt_history[agent_name].append(
            {
                "version": len(_prompt_history[agent_name]) + 1,
                "content": current_content,
                "updated_at": datetime.now(UTC).isoformat(),
                "updated_by": "dashboard",
            }
        )

        # Keep only last 5 versions
        if len(_prompt_history[agent_name]) > 5:
            _prompt_history[agent_name] = _prompt_history[agent_name][-5:]

        # Write new content
        file_path.write_text(update.content, encoding="utf-8")

        return {
            "success": True,
            "message": f"Prompt updated for {agent_name}",
            "version": len(_prompt_history[agent_name]) + 1,
        }
    except Exception as e:
        logger.error("Failed to update prompt %s: %s", agent_name, e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/{agent_name}/history", response_model=list[PromptHistoryItem])
async def get_prompt_history(agent_name: str) -> list[PromptHistoryItem]:
    """Get version history for an agent's prompt."""
    history = _prompt_history.get(agent_name, [])

    return [
        PromptHistoryItem(
            version=h["version"],
            content=h["content"],
            updated_at=datetime.fromisoformat(h["updated_at"]),
            updated_by=h.get("updated_by", "unknown"),
        )
        for h in reversed(history)  # Most recent first
    ]


@router.post("/{agent_name}/restore/{version}")
async def restore_prompt_version(agent_name: str, version: int) -> dict[str, Any]:
    """Restore a previous version of a prompt."""
    history = _prompt_history.get(agent_name, [])

    # Find the version
    target = None
    for h in history:
        if h["version"] == version:
            target = h
            break

    if not target:
        raise HTTPException(status_code=404, detail=f"Version {version} not found")

    # Update the prompt
    file_path = PROMPTS_DIR / f"{agent_name}.txt"
    try:
        # Save current to history first
        current_content = file_path.read_text(encoding="utf-8")
        _prompt_history[agent_name].append(
            {
                "version": len(history) + 1,
                "content": current_content,
                "updated_at": datetime.now(UTC).isoformat(),
                "updated_by": "dashboard (before restore)",
            }
        )

        # Restore
        file_path.write_text(target["content"], encoding="utf-8")

        return {
            "success": True,
            "message": f"Restored {agent_name} to version {version}",
        }
    except Exception as e:
        logger.error("Failed to restore prompt: %s", e)
        raise HTTPException(status_code=500, detail=str(e)) from e


@router.get("/info/agents")
async def get_agent_info() -> dict[str, Any]:
    """Get information about all agents."""
    return AGENT_INFO
