"""Tests for ActionAgent - device control and home automation."""

from __future__ import annotations

import pytest

from barnabeenet.agents.action import (
    ActionAgent,
    ActionType,
    DeviceDomain,
)


@pytest.fixture
def action_agent() -> ActionAgent:
    """Create an ActionAgent for testing."""
    return ActionAgent()


@pytest.fixture
async def initialized_agent(action_agent: ActionAgent) -> ActionAgent:
    """Create an initialized ActionAgent."""
    await action_agent.init()
    return action_agent


# =============================================================================
# Turn On/Off Tests
# =============================================================================


class TestTurnOnOff:
    """Test turn on/off action parsing."""

    @pytest.mark.asyncio
    async def test_turn_on_lights(self, initialized_agent: ActionAgent) -> None:
        """Turn on lights should parse correctly."""
        action = await initialized_agent.parse_action("turn on the lights")
        assert action.action_type == ActionType.TURN_ON
        assert action.entity_name == "lights"
        assert "turn_on" in action.service

    @pytest.mark.asyncio
    async def test_turn_off_lights(self, initialized_agent: ActionAgent) -> None:
        """Turn off lights should parse correctly."""
        action = await initialized_agent.parse_action("turn off the lights")
        assert action.action_type == ActionType.TURN_OFF
        assert action.entity_name == "lights"
        assert "turn_off" in action.service

    @pytest.mark.asyncio
    async def test_switch_on(self, initialized_agent: ActionAgent) -> None:
        """Switch on should work like turn on."""
        action = await initialized_agent.parse_action("switch on the kitchen light")
        assert action.action_type == ActionType.TURN_ON
        assert "kitchen light" in action.entity_name

    @pytest.mark.asyncio
    async def test_switch_off(self, initialized_agent: ActionAgent) -> None:
        """Switch off should work like turn off."""
        action = await initialized_agent.parse_action("switch off the fan")
        assert action.action_type == ActionType.TURN_OFF
        assert "fan" in action.entity_name

    @pytest.mark.asyncio
    async def test_enable_device(self, initialized_agent: ActionAgent) -> None:
        """Enable should turn on."""
        action = await initialized_agent.parse_action("enable the heater")
        assert action.action_type == ActionType.TURN_ON

    @pytest.mark.asyncio
    async def test_disable_device(self, initialized_agent: ActionAgent) -> None:
        """Disable should turn off."""
        action = await initialized_agent.parse_action("disable the alarm")
        assert action.action_type == ActionType.TURN_OFF


# =============================================================================
# Light Control Tests
# =============================================================================


class TestLightControl:
    """Test light-specific actions."""

    @pytest.mark.asyncio
    async def test_dim_lights(self, initialized_agent: ActionAgent) -> None:
        """Dim lights should set low brightness."""
        action = await initialized_agent.parse_action("dim the living room lights")
        assert action.action_type == ActionType.SET_VALUE
        assert action.domain == DeviceDomain.LIGHT
        assert action.target_value == 30  # Default dim value

    @pytest.mark.asyncio
    async def test_dim_to_specific_percent(self, initialized_agent: ActionAgent) -> None:
        """Dim to specific percentage."""
        action = await initialized_agent.parse_action("dim the lights to 50%")
        assert action.action_type == ActionType.SET_VALUE
        assert action.target_value == 50

    @pytest.mark.asyncio
    async def test_brighten_lights(self, initialized_agent: ActionAgent) -> None:
        """Brighten lights should set high brightness."""
        action = await initialized_agent.parse_action("brighten the bedroom lights")
        assert action.action_type == ActionType.SET_VALUE
        assert action.target_value == 100  # Default brighten value

    @pytest.mark.asyncio
    async def test_set_brightness(self, initialized_agent: ActionAgent) -> None:
        """Set brightness to specific value."""
        action = await initialized_agent.parse_action("set the lamp brightness to 75%")
        assert action.action_type == ActionType.SET_VALUE
        assert action.target_value == 75
        assert "brightness_pct" in action.service_data


# =============================================================================
# Climate Control Tests
# =============================================================================


class TestClimateControl:
    """Test climate/thermostat actions."""

    @pytest.mark.asyncio
    async def test_set_temperature(self, initialized_agent: ActionAgent) -> None:
        """Set temperature should parse correctly."""
        action = await initialized_agent.parse_action("set the temperature to 72")
        assert action.action_type == ActionType.SET_VALUE
        assert action.domain == DeviceDomain.CLIMATE
        assert action.target_value == 72

    @pytest.mark.asyncio
    async def test_set_thermostat(self, initialized_agent: ActionAgent) -> None:
        """Set thermostat should work."""
        action = await initialized_agent.parse_action("set thermostat to 68")
        assert action.action_type == ActionType.SET_VALUE
        assert action.target_value == 68

    @pytest.mark.asyncio
    async def test_set_temperature_with_degrees(self, initialized_agent: ActionAgent) -> None:
        """Temperature with degree symbol."""
        action = await initialized_agent.parse_action("set temperature to 70°F")
        assert action.action_type == ActionType.SET_VALUE
        assert action.target_value == 70


# =============================================================================
# Lock Control Tests
# =============================================================================


class TestLockControl:
    """Test lock actions."""

    @pytest.mark.asyncio
    async def test_lock_door(self, initialized_agent: ActionAgent) -> None:
        """Lock door should parse correctly."""
        action = await initialized_agent.parse_action("lock the front door")
        assert action.action_type == ActionType.LOCK
        assert action.domain == DeviceDomain.LOCK
        assert "front door" in action.entity_name
        assert action.requires_confirmation is False  # Lock is safe

    @pytest.mark.asyncio
    async def test_unlock_door_requires_confirmation(self, initialized_agent: ActionAgent) -> None:
        """Unlock door should require confirmation."""
        action = await initialized_agent.parse_action("unlock the back door")
        assert action.action_type == ActionType.UNLOCK
        assert action.requires_confirmation is True


# =============================================================================
# Cover Control Tests
# =============================================================================


class TestCoverControl:
    """Test cover (garage, blinds) actions."""

    @pytest.mark.asyncio
    async def test_open_garage(self, initialized_agent: ActionAgent) -> None:
        """Open garage should require confirmation."""
        action = await initialized_agent.parse_action("open the garage door")
        assert action.action_type == ActionType.OPEN
        assert action.domain == DeviceDomain.COVER
        assert action.requires_confirmation is True

    @pytest.mark.asyncio
    async def test_close_garage(self, initialized_agent: ActionAgent) -> None:
        """Close garage should not require confirmation."""
        action = await initialized_agent.parse_action("close the garage")
        assert action.action_type == ActionType.CLOSE
        assert action.requires_confirmation is False

    @pytest.mark.asyncio
    async def test_open_blinds(self, initialized_agent: ActionAgent) -> None:
        """Open blinds."""
        action = await initialized_agent.parse_action("open the blinds")
        assert action.action_type == ActionType.OPEN
        assert action.domain == DeviceDomain.COVER

    @pytest.mark.asyncio
    async def test_close_curtains(self, initialized_agent: ActionAgent) -> None:
        """Close curtains."""
        action = await initialized_agent.parse_action("close the curtains")
        assert action.action_type == ActionType.CLOSE


# =============================================================================
# Media Control Tests
# =============================================================================


class TestMediaControl:
    """Test media player actions."""

    @pytest.mark.asyncio
    async def test_play_music(self, initialized_agent: ActionAgent) -> None:
        """Play music should parse correctly."""
        action = await initialized_agent.parse_action("play music")
        assert action.action_type == ActionType.PLAY
        assert action.domain == DeviceDomain.MEDIA_PLAYER

    @pytest.mark.asyncio
    async def test_pause_tv(self, initialized_agent: ActionAgent) -> None:
        """Pause TV."""
        action = await initialized_agent.parse_action("pause the tv")
        assert action.action_type == ActionType.PAUSE
        assert action.domain == DeviceDomain.MEDIA_PLAYER

    @pytest.mark.asyncio
    async def test_stop_playback(self, initialized_agent: ActionAgent) -> None:
        """Stop playback."""
        action = await initialized_agent.parse_action("stop the music")
        assert action.action_type == ActionType.STOP

    @pytest.mark.asyncio
    async def test_skip_track(self, initialized_agent: ActionAgent) -> None:
        """Skip track."""
        action = await initialized_agent.parse_action("skip")
        assert action.action_type == ActionType.SKIP

    @pytest.mark.asyncio
    async def test_play_on_speaker(self, initialized_agent: ActionAgent) -> None:
        """Play on specific speaker."""
        action = await initialized_agent.parse_action("play on the living room speaker")
        assert action.action_type == ActionType.PLAY
        assert "living room speaker" in action.entity_name


# =============================================================================
# Scene Control Tests
# =============================================================================


class TestSceneControl:
    """Test scene activation."""

    @pytest.mark.asyncio
    async def test_activate_scene(self, initialized_agent: ActionAgent) -> None:
        """Activate scene should parse correctly."""
        action = await initialized_agent.parse_action("activate the movie scene")
        assert action.action_type == ActionType.ACTIVATE_SCENE
        assert action.domain == DeviceDomain.SCENE
        assert "movie" in action.entity_name

    @pytest.mark.asyncio
    async def test_start_mode(self, initialized_agent: ActionAgent) -> None:
        """Start mode should activate scene."""
        action = await initialized_agent.parse_action("start the bedtime mode")
        assert action.action_type == ActionType.ACTIVATE_SCENE
        assert "bedtime" in action.entity_name

    @pytest.mark.asyncio
    async def test_run_scene(self, initialized_agent: ActionAgent) -> None:
        """Run scene should activate."""
        action = await initialized_agent.parse_action("run the party scene")
        assert action.action_type == ActionType.ACTIVATE_SCENE


# =============================================================================
# Generic Set Tests
# =============================================================================


class TestGenericSet:
    """Test generic set commands."""

    @pytest.mark.asyncio
    async def test_set_device_to_value(self, initialized_agent: ActionAgent) -> None:
        """Generic set command."""
        action = await initialized_agent.parse_action("set the volume to 50")
        assert action.action_type == ActionType.SET_VALUE
        assert "volume" in action.entity_name
        assert action.target_value == "50"

    @pytest.mark.asyncio
    async def test_change_device_to_value(self, initialized_agent: ActionAgent) -> None:
        """Change command should work like set."""
        action = await initialized_agent.parse_action("change the mode to eco")
        assert action.action_type == ActionType.SET_VALUE
        assert "mode" in action.entity_name


# =============================================================================
# Domain Inference Tests
# =============================================================================


class TestDomainInference:
    """Test automatic domain inference."""

    @pytest.mark.asyncio
    async def test_light_keyword_infers_domain(self, initialized_agent: ActionAgent) -> None:
        """Light keyword should infer light domain."""
        action = await initialized_agent.parse_action("turn on the bedroom light")
        assert action.domain == DeviceDomain.LIGHT

    @pytest.mark.asyncio
    async def test_lamp_keyword_infers_domain(self, initialized_agent: ActionAgent) -> None:
        """Lamp keyword should infer light domain."""
        action = await initialized_agent.parse_action("turn off the desk lamp")
        assert action.domain == DeviceDomain.LIGHT

    @pytest.mark.asyncio
    async def test_thermostat_keyword_infers_domain(self, initialized_agent: ActionAgent) -> None:
        """Thermostat keyword should infer climate domain."""
        action = await initialized_agent.parse_action("turn on the thermostat")
        assert action.domain == DeviceDomain.CLIMATE

    @pytest.mark.asyncio
    async def test_tv_keyword_infers_domain(self, initialized_agent: ActionAgent) -> None:
        """TV keyword should infer media_player domain."""
        action = await initialized_agent.parse_action("turn on the tv")
        assert action.domain == DeviceDomain.MEDIA_PLAYER


# =============================================================================
# Entity ID Generation Tests
# =============================================================================


class TestEntityIdGeneration:
    """Test entity ID generation."""

    @pytest.mark.asyncio
    async def test_entity_id_generated(self, initialized_agent: ActionAgent) -> None:
        """Entity ID should be generated from name."""
        action = await initialized_agent.parse_action("turn on the living room lights")
        assert action.entity_id is not None
        assert "living_room_lights" in action.entity_id
        assert action.entity_id.startswith("light.")

    @pytest.mark.asyncio
    async def test_entity_id_sanitized(self, initialized_agent: ActionAgent) -> None:
        """Entity ID should be sanitized."""
        action = await initialized_agent.parse_action("turn on the Kid's Room Light!")
        assert action.entity_id is not None
        assert " " not in action.entity_id
        assert "!" not in action.entity_id


# =============================================================================
# Response Generation Tests
# =============================================================================


class TestResponseGeneration:
    """Test spoken response generation."""

    @pytest.mark.asyncio
    async def test_turn_on_response(self, initialized_agent: ActionAgent) -> None:
        """Turn on should generate appropriate response."""
        action = await initialized_agent.parse_action("turn on the lights")
        assert "Turning on" in action.spoken_response
        assert "lights" in action.spoken_response

    @pytest.mark.asyncio
    async def test_set_value_response(self, initialized_agent: ActionAgent) -> None:
        """Set value should include the value in response."""
        action = await initialized_agent.parse_action("dim the lights to 50%")
        assert "50" in action.spoken_response

    @pytest.mark.asyncio
    async def test_temperature_response(self, initialized_agent: ActionAgent) -> None:
        """Temperature should mention degrees."""
        action = await initialized_agent.parse_action("set temperature to 72")
        assert "72" in action.spoken_response
        assert "degrees" in action.spoken_response.lower()


# =============================================================================
# handle_input Tests
# =============================================================================


class TestHandleInput:
    """Test the Agent interface handle_input method."""

    @pytest.mark.asyncio
    async def test_handle_input_returns_dict(self, initialized_agent: ActionAgent) -> None:
        """handle_input should return a dictionary."""
        result = await initialized_agent.handle_input("turn on the lights")
        assert isinstance(result, dict)
        assert "response" in result
        assert "agent" in result
        assert "action" in result
        assert "success" in result

    @pytest.mark.asyncio
    async def test_handle_input_agent_name(self, initialized_agent: ActionAgent) -> None:
        """Agent name should be 'action'."""
        result = await initialized_agent.handle_input("turn on the lights")
        assert result["agent"] == "action"

    @pytest.mark.asyncio
    async def test_handle_input_success(self, initialized_agent: ActionAgent) -> None:
        """Valid action should succeed."""
        result = await initialized_agent.handle_input("turn on the lights")
        assert result["success"] is True
        assert result["action"] is not None

    @pytest.mark.asyncio
    async def test_handle_input_unknown_action(self, initialized_agent: ActionAgent) -> None:
        """Unknown action should fail gracefully."""
        result = await initialized_agent.handle_input("do the impossible thing")
        assert result["success"] is False
        assert result["action"] is None

    @pytest.mark.asyncio
    async def test_handle_input_confirmation_required(self, initialized_agent: ActionAgent) -> None:
        """High-risk action should require confirmation."""
        result = await initialized_agent.handle_input("unlock the front door")
        assert result.get("requires_confirmation") is True
        assert "sure" in result["response"].lower()


# =============================================================================
# Edge Cases
# =============================================================================


class TestEdgeCases:
    """Test edge cases and error handling."""

    @pytest.mark.asyncio
    async def test_empty_input(self, initialized_agent: ActionAgent) -> None:
        """Empty input should not crash."""
        result = await initialized_agent.handle_input("")
        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_whitespace_input(self, initialized_agent: ActionAgent) -> None:
        """Whitespace input should not crash."""
        result = await initialized_agent.handle_input("   ")
        assert result is not None

    @pytest.mark.asyncio
    async def test_none_context(self, initialized_agent: ActionAgent) -> None:
        """None context should work."""
        result = await initialized_agent.handle_input("turn on the lights", context=None)
        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_case_insensitive(self, initialized_agent: ActionAgent) -> None:
        """Actions should be case insensitive."""
        result = await initialized_agent.handle_input("TURN ON THE LIGHTS")
        assert result["success"] is True
        assert result["action"]["action_type"] == "turn_on"

    @pytest.mark.asyncio
    async def test_with_article_variations(self, initialized_agent: ActionAgent) -> None:
        """Should work with or without 'the'."""
        result1 = await initialized_agent.handle_input("turn on the lights")
        result2 = await initialized_agent.handle_input("turn on lights")
        assert result1["success"] is True
        assert result2["success"] is True


# =============================================================================
# Lifecycle Tests
# =============================================================================


class TestLifecycle:
    """Test agent lifecycle methods."""

    @pytest.mark.asyncio
    async def test_init_compiles_patterns(self, action_agent: ActionAgent) -> None:
        """Init should compile patterns."""
        assert len(action_agent._compiled_patterns) == 0
        await action_agent.init()
        assert len(action_agent._compiled_patterns) > 0

    @pytest.mark.asyncio
    async def test_shutdown_clears_patterns(self, initialized_agent: ActionAgent) -> None:
        """Shutdown should clear patterns."""
        assert len(initialized_agent._compiled_patterns) > 0
        await initialized_agent.shutdown()
        assert len(initialized_agent._compiled_patterns) == 0

    @pytest.mark.asyncio
    async def test_reinitialize_after_shutdown(self, initialized_agent: ActionAgent) -> None:
        """Agent should reinitialize after shutdown."""
        await initialized_agent.shutdown()
        await initialized_agent.init()
        result = await initialized_agent.handle_input("turn on the lights")
        assert result["success"] is True
