#!/bin/bash

# Timer Functionality Test Script
# Tests all timer features with office fan and light

API_BASE="${API_BASE:-http://192.168.86.51:8000}"

echo "=========================================="
echo "BarnabeeNet Timer Functionality Tests"
echo "=========================================="
echo ""

# Check if service is running
echo "Checking service health..."
health=$(curl -s "${API_BASE}/health" 2>/dev/null)
if [ -z "$health" ]; then
    echo "⚠️  Service not responding at ${API_BASE}"
    echo "Trying localhost..."
    API_BASE="http://localhost:8000"
    health=$(curl -s "${API_BASE}/health" 2>/dev/null)
    if [ -z "$health" ]; then
        echo "❌ Service not running. Please start BarnabeeNet first."
        exit 1
    fi
fi
echo "✓ Service is running at ${API_BASE}"
echo ""

TOTAL=0
PASSED=0
FAILED=0

# Helper function to make API calls
call_api() {
    local text="$1"
    local speaker="${2:-thom}"
    local room="${3:-office}"
    
    curl -s -X POST "${API_BASE}/api/v1/chat" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"$text\", \"speaker\": \"$speaker\", \"room\": \"$room\"}"
}

# Test function
test_timer() {
    local test_name="$1"
    local command="$2"
    local expected_intent="${3:-action}"
    local expected_agent="${4:-action}"
    
    TOTAL=$((TOTAL + 1))
    
    echo "Test $TOTAL: $test_name"
    echo "Command: $command"
    
    response=$(call_api "$command")
    
    # Extract fields from JSON response
    intent=$(echo "$response" | grep -o '"intent":"[^"]*' | cut -d'"' -f4)
    agent=$(echo "$response" | grep -o '"agent":"[^"]*' | cut -d'"' -f4)
    response_text=$(echo "$response" | grep -o '"response":"[^"]*' | cut -d'"' -f4)
    error=$(echo "$response" | grep -o '"error":"[^"]*' | cut -d'"' -f4)
    timer_info=$(echo "$response" | grep -o '"timer_info":{[^}]*}' | head -1)
    
    local passed=true
    local issues=""
    
    # Check for errors
    if [ -n "$error" ]; then
        passed=false
        issues="Error: $error"
    fi
    
    # Check intent
    if [ -n "$expected_intent" ] && [ "$intent" != "$expected_intent" ]; then
        passed=false
        issues="${issues}Intent mismatch: expected '$expected_intent', got '$intent'. "
    fi
    
    # Check agent
    if [ -n "$expected_agent" ] && [ "$agent" != "$expected_agent" ]; then
        passed=false
        issues="${issues}Agent mismatch: expected '$expected_agent', got '$agent'. "
    fi
    
    # Check response
    if [ -z "$response_text" ] || [ ${#response_text} -lt 5 ]; then
        passed=false
        issues="${issues}Empty or too short response. "
    fi
    
    if [ "$passed" = true ]; then
        PASSED=$((PASSED + 1))
        echo "✓ PASSED"
        echo "Response: $response_text"
        if [ -n "$timer_info" ]; then
            echo "Timer Info: $timer_info"
        fi
    else
        FAILED=$((FAILED + 1))
        echo "✗ FAILED: $issues"
        echo "Response: $response_text"
        echo "Full response: $response"
    fi
    
    echo ""
    sleep 1  # Small delay between tests
}

echo "=== Basic Timer Creation ==="
test_timer "Simple timer" "set a timer for 1 minute" "action" "action"
test_timer "Labeled timer" "set a lasagna timer for 2 minutes" "action" "action"
test_timer "Pizza timer" "start a pizza timer for 3 minutes" "action" "action"

echo "=== Timer Queries ==="
test_timer "Query lasagna timer" "how long on lasagna" "action" "action"
test_timer "Query time left" "how much time left on pizza" "action" "action"
test_timer "Time left query" "time left on lasagna" "action" "action"

echo "=== Device Duration Timers ==="
test_timer "Turn on fan for duration" "turn on the office fan for 2 minutes" "action" "action"
sleep 3  # Wait a bit for timer to start
test_timer "Query fan timer" "how long on office fan" "action" "action"

echo "=== Delayed Actions ==="
test_timer "Delayed turn off" "in 30 seconds turn off the office light" "action" "action"
test_timer "Wait then action" "wait 1 minute turn on the office fan" "action" "action"

echo "=== Timer Control ==="
test_timer "Pause timer" "pause the lasagna timer" "action" "action"
test_timer "Resume timer" "resume the lasagna timer" "action" "action"
test_timer "Cancel timer" "cancel the pizza timer" "action" "action"

echo "=== Chained Actions ==="
test_timer "Chained actions" "wait 1 minute turn on the office fan and then in 20 seconds turn it off again" "action" "action"

echo "=========================================="
echo "Test Results"
echo "=========================================="
echo "Total: $TOTAL"
echo "Passed: $PASSED"
echo "Failed: $FAILED"
echo "Success Rate: $(( PASSED * 100 / TOTAL ))%"
echo ""

if [ $FAILED -eq 0 ]; then
    echo "🎉 All tests passed!"
    exit 0
else
    echo "❌ Some tests failed"
    exit 1
fi
