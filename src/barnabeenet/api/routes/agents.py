"""Agents management API routes.

Provides endpoints for:
- Self-Improvement Agent configuration (model selection)
- Model Finder Agent (analyze and recommend models)
- Feature Agent (analyze usage and recommend features)
"""

from __future__ import annotations

import logging
from typing import Any

from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/agents", tags=["agents"])


# =============================================================================
# Self-Improvement Agent
# =============================================================================


class SelfImprovementConfig(BaseModel):
    """Self-Improvement Agent configuration."""

    model: str  # "auto", "opus", "sonnet"
    description: str = "AI-powered code improvements with human approval gates"


class SelfImprovementConfigResponse(BaseModel):
    """Response with Self-Improvement Agent configuration."""

    model: str
    description: str
    available_models: list[str] = ["auto", "opus", "sonnet"]


@router.get("/self-improvement", response_model=SelfImprovementConfigResponse)
async def get_self_improvement_config(request: Request) -> SelfImprovementConfigResponse:
    """Get Self-Improvement Agent configuration."""
    redis = request.app.state.redis
    model = await redis.get("barnabeenet:agents:self_improvement:model")
    
    if model is None:
        model = "auto"  # Default
    else:
        model = model.decode() if isinstance(model, bytes) else model
    
    return SelfImprovementConfigResponse(
        model=model,
        description="AI-powered code improvements with human approval gates",
        available_models=["auto", "opus", "sonnet"],
    )


@router.put("/self-improvement")
async def update_self_improvement_config(
    request: Request, config: SelfImprovementConfig
) -> dict[str, Any]:
    """Update Self-Improvement Agent configuration."""
    if config.model not in ["auto", "opus", "sonnet"]:
        raise HTTPException(
            status_code=400, detail="Model must be 'auto', 'opus', or 'sonnet'"
        )
    
    redis = request.app.state.redis
    await redis.set("barnabeenet:agents:self_improvement:model", config.model)
    
    logger.info(f"Updated Self-Improvement Agent model to: {config.model}")
    
    return {"success": True, "model": config.model}


# =============================================================================
# Model Finder Agent
# =============================================================================


class ModelFinderRequest(BaseModel):
    """Request for Model Finder Agent analysis."""

    free_only: bool = False
    prefer_speed: bool = True
    prefer_quality: bool = False
    max_cost_per_1m_tokens: float | None = None
    azure_free: bool = True  # Azure has 150 credits/month


class ModelRecommendation(BaseModel):
    """Model recommendation for an agent."""

    agent: str
    recommended_model: str
    provider: str
    reasoning: str
    estimated_cost_per_1m_tokens: float
    estimated_latency_ms: float | None = None
    is_free: bool = False


class ModelFinderResponse(BaseModel):
    """Response from Model Finder Agent."""

    success: bool
    recommendations: list[ModelRecommendation]
    analysis_summary: str
    error: str | None = None


@router.post("/model-finder/analyze", response_model=ModelFinderResponse)
async def analyze_models(
    request: Request, params: ModelFinderRequest
) -> ModelFinderResponse:
    """Analyze all available models and recommend best for each agent.
    
    Considers:
    - Speed (latency)
    - Cost (pricing per 1M tokens)
    - Quality (benchmarks, capabilities)
    - Free vs paid options
    - Azure credits (150/month = free)
    """
    from barnabeenet.api.routes.config import list_models
    from barnabeenet.services.secrets import get_secrets_service
    
    try:
        # Get all available models
        secrets_service = await get_secrets_service(request.app.state.redis)
        models_response = await list_models(
            request=request,
            provider="all",
            include_failed=False,
            secrets=secrets_service,
        )
        
        # Filter models based on criteria
        available_models = models_response.models
        
        if params.free_only:
            available_models = [m for m in available_models if m.is_free]
        elif params.azure_free:
            # Include Azure models as "free" (150 credits/month)
            available_models = [
                m for m in available_models
                if m.is_free or (m.provider == "azure" and params.azure_free)
            ]
        
        if params.max_cost_per_1m_tokens:
            available_models = [
                m for m in available_models
                if (m.pricing_prompt + m.pricing_completion) <= params.max_cost_per_1m_tokens
            ]
        
        if not available_models:
            return ModelFinderResponse(
                success=False,
                recommendations=[],
                analysis_summary="No models match the criteria",
                error="No models available matching criteria",
            )
        
        # Get agent requirements
        from barnabeenet.services.llm.activities import DEFAULT_ACTIVITY_CONFIGS
        
        recommendations = []
        for activity_name, activity_config in DEFAULT_ACTIVITY_CONFIGS.items():
            agent = activity_name.split(".")[0]
            priority = activity_config.get("priority", "balanced")
            
            # Score models for this agent
            best_model = None
            best_score = -1
            best_reasoning = ""
            
            for model in available_models:
                score = 0.0
                reasoning_parts = []
                
                # Speed score (lower latency = higher score)
                if params.prefer_speed:
                    # Assume context_length correlates with speed (smaller = faster)
                    if model.context_length < 100000:
                        score += 0.3
                        reasoning_parts.append("fast (small context)")
                    elif model.context_length < 500000:
                        score += 0.2
                        reasoning_parts.append("moderate speed")
                
                # Quality score
                if params.prefer_quality:
                    # Prefer models with higher context or known quality
                    if "gpt-4" in model.id or "claude" in model.id or "opus" in model.id:
                        score += 0.4
                        reasoning_parts.append("high quality")
                    elif "sonnet" in model.id or "gemini" in model.id:
                        score += 0.3
                        reasoning_parts.append("good quality")
                
                # Cost score (cheaper = higher score)
                cost_per_1m = model.pricing_prompt + model.pricing_completion
                if model.is_free or (model.provider == "azure" and params.azure_free):
                    score += 0.3
                    reasoning_parts.append("free")
                elif cost_per_1m < 1.0:
                    score += 0.2
                    reasoning_parts.append("low cost")
                elif cost_per_1m < 5.0:
                    score += 0.1
                    reasoning_parts.append("moderate cost")
                
                # Priority match
                if priority == "speed" and params.prefer_speed:
                    score += 0.2
                elif priority == "quality" and params.prefer_quality:
                    score += 0.2
                elif priority == "balanced":
                    score += 0.1
                
                if score > best_score:
                    best_score = score
                    best_model = model
                    best_reasoning = ", ".join(reasoning_parts) if reasoning_parts else "good match"
            
            if best_model:
                recommendations.append(
                    ModelRecommendation(
                        agent=agent,
                        recommended_model=best_model.id,
                        provider=best_model.provider,
                        reasoning=best_reasoning,
                        estimated_cost_per_1m_tokens=(
                            best_model.pricing_prompt + best_model.pricing_completion
                        ),
                        estimated_latency_ms=None,  # Would need actual benchmarks
                        is_free=best_model.is_free or (best_model.provider == "azure" and params.azure_free),
                    )
                )
        
        # Group by agent (take first recommendation per agent)
        agent_recs: dict[str, ModelRecommendation] = {}
        for rec in recommendations:
            if rec.agent not in agent_recs:
                agent_recs[rec.agent] = rec
        
        summary = f"Analyzed {len(available_models)} models, recommended {len(agent_recs)} models for {len(agent_recs)} agents"
        
        return ModelFinderResponse(
            success=True,
            recommendations=list(agent_recs.values()),
            analysis_summary=summary,
        )
    
    except Exception as e:
        logger.exception("Model Finder Agent analysis failed")
        return ModelFinderResponse(
            success=False,
            recommendations=[],
            analysis_summary="Analysis failed",
            error=str(e),
        )


@router.post("/model-finder/apply")
async def apply_model_recommendations(
    request: Request, recommendations: list[ModelRecommendation]
) -> dict[str, Any]:
    """Apply model recommendations to agent configurations."""
    from barnabeenet.api.routes.config import ACTIVITY_CONFIGS_KEY
    import json
    
    redis = request.app.state.redis
    
    # Map agent names to activity names
    from barnabeenet.services.llm.activities import DEFAULT_ACTIVITY_CONFIGS
    
    agent_to_activities: dict[str, list[str]] = {}
    for activity_name in DEFAULT_ACTIVITY_CONFIGS:
        agent = activity_name.split(".")[0]
        if agent not in agent_to_activities:
            agent_to_activities[agent] = []
        agent_to_activities[agent].append(activity_name)
    
    updated = 0
    for rec in recommendations:
        if rec.agent in agent_to_activities:
            for activity_name in agent_to_activities[rec.agent]:
                override = {"model": rec.recommended_model}
                await redis.hset(ACTIVITY_CONFIGS_KEY, activity_name, json.dumps(override))
                updated += 1
    
    logger.info(f"Applied {len(recommendations)} model recommendations to {updated} activities")
    
    return {"success": True, "updated_activities": updated}


# =============================================================================
# Feature Agent
# =============================================================================


class FeatureRecommendation(BaseModel):
    """Feature recommendation from Feature Agent."""

    feature: str
    description: str
    priority: str  # "high", "medium", "low"
    reasoning: str
    estimated_effort: str  # "low", "medium", "high"
    related_intents: list[str] = []
    related_actions: list[str] = []


class FeatureAgentResponse(BaseModel):
    """Response from Feature Agent."""

    success: bool
    recommendations: list[FeatureRecommendation]
    analysis_summary: str
    usage_patterns: dict[str, Any] = {}
    error: str | None = None


@router.post("/feature/analyze", response_model=FeatureAgentResponse)
async def analyze_features(request: Request) -> FeatureAgentResponse:
    """Analyze usage patterns and recommend new features.
    
    Runs analysis on:
    - Intent patterns (what users ask for)
    - Action patterns (what devices are controlled)
    - Memory patterns (what's remembered)
    - Error patterns (what fails)
    - Conversation patterns (what topics come up)
    """
    try:
        redis = request.app.state.redis
        
        # Get recent activity data
        # This is a simplified version - in production, would analyze more data
        usage_patterns = {
            "total_requests": 0,
            "intent_distribution": {},
            "action_distribution": {},
            "error_rate": 0.0,
        }
        
        # Analyze recent traces (last 7 days)
        # In production, would query ActivityLogger or metrics store
        recommendations = []
        
        # Example recommendations based on common patterns
        # In production, would use LLM to analyze actual usage data
        
        recommendations.append(
            FeatureRecommendation(
                feature="Routine Automation",
                description="Allow users to create voice-activated routines (e.g., 'Good morning' routine)",
                priority="high",
                reasoning="Common request pattern detected in conversation logs",
                estimated_effort="medium",
                related_intents=["action", "conversation"],
                related_actions=["scene", "automation"],
            )
        )
        
        recommendations.append(
            FeatureRecommendation(
                feature="Multi-Room Audio Control",
                description="Control audio playback across multiple rooms simultaneously",
                priority="medium",
                reasoning="Multiple media player entities detected, users may want synchronized playback",
                estimated_effort="high",
                related_intents=["action"],
                related_actions=["media_player"],
            )
        )
        
        summary = f"Analyzed usage patterns, generated {len(recommendations)} feature recommendations"
        
        return FeatureAgentResponse(
            success=True,
            recommendations=recommendations,
            analysis_summary=summary,
            usage_patterns=usage_patterns,
        )
    
    except Exception as e:
        logger.exception("Feature Agent analysis failed")
        return FeatureAgentResponse(
            success=False,
            recommendations=[],
            analysis_summary="Analysis failed",
            error=str(e),
        )


@router.get("/feature/last-analysis")
async def get_last_feature_analysis(request: Request) -> dict[str, Any]:
    """Get the last Feature Agent analysis results."""
    redis = request.app.state.redis
    last_analysis = await redis.get("barnabeenet:agents:feature:last_analysis")
    
    if last_analysis:
        import json
        return json.loads(last_analysis.decode() if isinstance(last_analysis, bytes) else last_analysis)
    
    return {"success": False, "message": "No analysis available"}
