#!/bin/bash

# Test Timer Actions with Office Light
# Verifies that timers actually execute device control actions

API_BASE="${API_BASE:-http://192.168.86.51:8000}"

echo "=========================================="
echo "Timer Action Execution Tests"
echo "=========================================="
echo ""

# Helper to get light state
get_light_state() {
    curl -s "${API_BASE}/api/v1/homeassistant/entities/light.office_light" 2>/dev/null | python3 -m json.tool | grep -E '"state"|"is_on"' | head -2
}

# Helper to make API calls
call_api() {
    local text="$1"
    curl -s -X POST "${API_BASE}/api/v1/chat" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"$text\", \"speaker\": \"thom\", \"room\": \"office\"}"
}

echo "=== Test 1: Device Duration Timer ==="
echo "Step 1: Check initial light state"
INITIAL_STATE=$(get_light_state)
echo "Initial state: $INITIAL_STATE"
echo ""

echo "Step 2: Create timer to turn on light for 20 seconds"
RESPONSE=$(call_api "turn on the office light for 20 seconds")
echo "Response: $(echo "$RESPONSE" | python3 -m json.tool | grep '"response"' | head -1)"
echo ""

echo "Step 3: Wait 3 seconds, check if light is ON"
sleep 3
STATE_AFTER_START=$(get_light_state)
echo "State after timer start: $STATE_AFTER_STATE"
echo ""

echo "Step 4: Wait 25 seconds for timer to complete"
sleep 25
STATE_AFTER_TIMER=$(get_light_state)
echo "State after timer completes: $STATE_AFTER_TIMER"
echo ""

echo "=== Test 2: Delayed Action Timer ==="
echo "Step 1: Turn light ON first"
call_api "turn on the office light" > /dev/null
sleep 2
echo "Light should be ON now"
echo ""

echo "Step 2: Create delayed action to turn OFF in 15 seconds"
RESPONSE=$(call_api "in 15 seconds turn off the office light")
echo "Response: $(echo "$RESPONSE" | python3 -m json.tool | grep '"response"' | head -1)"
echo ""

echo "Step 3: Wait 3 seconds, verify light still ON"
sleep 3
STATE_DURING_DELAY=$(get_light_state)
echo "State during delay: $STATE_DURING_DELAY"
echo ""

echo "Step 4: Wait 18 seconds for delayed action to execute"
sleep 18
STATE_AFTER_DELAYED=$(get_light_state)
echo "State after delayed action: $STATE_AFTER_DELAYED"
echo ""

echo "=========================================="
echo "Test Complete"
echo "=========================================="
