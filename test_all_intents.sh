#!/bin/bash
# Comprehensive intent testing for BarnabeeNet using curl

BASE_URL="http://localhost:8000"
API_BASE="${BASE_URL}/api/v1"

# Test results
TOTAL=0
PASSED=0
FAILED=0
ISSUES=()

test_request() {
    local text="$1"
    local speaker="${2:-thom}"
    local room="${3:-office}"
    local conv_id="${4:-}"

    local json_payload
    if [ -n "$conv_id" ]; then
        json_payload="{\"text\": \"$text\", \"speaker\": \"$speaker\", \"room\": \"$room\", \"conversation_id\": \"$conv_id\"}"
    else
        json_payload="{\"text\": \"$text\", \"speaker\": \"$speaker\", \"room\": \"$room\"}"
    fi

    curl -s -X POST "${API_BASE}/chat" \
        -H "Content-Type: application/json" \
        -d "$json_payload"
}

check_result() {
    local category="$1"
    local test_name="$2"
    local input_text="$3"
    local response="$4"
    local expected_intent="${5:-}"
    local expected_agent="${6:-}"

    TOTAL=$((TOTAL + 1))

    # Extract fields from JSON response
    local intent=$(echo "$response" | grep -o '"intent":"[^"]*' | cut -d'"' -f4)
    local agent=$(echo "$response" | grep -o '"agent":"[^"]*' | cut -d'"' -f4)
    local response_text=$(echo "$response" | grep -o '"response":"[^"]*' | cut -d'"' -f4)
    local error=$(echo "$response" | grep -o '"error":"[^"]*' | cut -d'"' -f4)

    local passed=true
    local issues_str=""

    # Check for errors
    if [ -n "$error" ]; then
        passed=false
        issues_str="Error: $error"
    fi

    # Check intent
    if [ -n "$expected_intent" ] && [ "$intent" != "$expected_intent" ]; then
        passed=false
        if [ -n "$issues_str" ]; then
            issues_str="$issues_str; "
        fi
        issues_str="${issues_str}Intent mismatch: expected '$expected_intent', got '$intent'"
    fi

    # Check agent
    if [ -n "$expected_agent" ] && [ "$agent" != "$expected_agent" ]; then
        passed=false
        if [ -n "$issues_str" ]; then
            issues_str="$issues_str; "
        fi
        issues_str="${issues_str}Agent mismatch: expected '$expected_agent', got '$agent'"
    fi

    # Check response
    if [ -z "$response_text" ] || [ ${#response_text} -lt 5 ]; then
        passed=false
        if [ -n "$issues_str" ]; then
            issues_str="$issues_str; "
        fi
        issues_str="${issues_str}Empty or too short response"
    fi

    if [ "$passed" = true ]; then
        PASSED=$((PASSED + 1))
        echo "  ✅ $test_name: $intent → $agent"
    else
        FAILED=$((FAILED + 1))
        echo "  ❌ $test_name: $issues_str"
        ISSUES+=("$category|$test_name|$input_text|$intent|$agent|$issues_str")
    fi
}

echo "======================================================================"
echo "BarnabeeNet Intent Testing Suite"
echo "======================================================================"
echo "Server: ${BASE_URL}"
echo "Time: $(date)"
echo ""
echo "Testing all intents (excluding Home Assistant device control)..."
echo ""

# Test 1: Instant Agent
echo "[1] Testing Instant Agent Intents..."
time_variations=(
    "What time is it?"
    "What's the time?"
    "Tell me the time"
    "Time?"
    "What time?"
    "Current time"
)

for text in "${time_variations[@]}"; do
    resp=$(test_request "$text")
    check_result "instant" "Time: $text" "$text" "$resp" "instant" "instant"
    sleep 0.2
done

date_variations=(
    "What's the date?"
    "What date is it?"
    "Tell me the date"
    "Date?"
    "What's today's date?"
    "Current date"
)

for text in "${date_variations[@]}"; do
    resp=$(test_request "$text")
    check_result "instant" "Date: $text" "$text" "$resp" "instant" "instant"
    sleep 0.2
done

greeting_variations=(
    "Hello"
    "Hi"
    "Hey"
    "Good morning"
    "Good afternoon"
    "Good evening"
)

for text in "${greeting_variations[@]}"; do
    resp=$(test_request "$text")
    check_result "instant" "Greeting: $text" "$text" "$resp" "instant" "instant"
    sleep 0.2
done

# Test 2: Interaction Agent
echo ""
echo "[2] Testing Interaction Agent Intents..."
question_variations=(
    "What's the weather like?"
    "Tell me a joke"
    "What can you do?"
    "Explain quantum computing"
    "What is artificial intelligence?"
    "Tell me about space"
)

for text in "${question_variations[@]}"; do
    resp=$(test_request "$text")
    check_result "interaction" "Question: ${text:0:40}" "$text" "$resp" "conversation" "interaction"
    sleep 0.3
done

# Test 3: Memory Agent
echo ""
echo "[3] Testing Memory Agent Intents..."
store_variations=(
    "Remember that I like coffee in the morning"
    "I prefer my office temperature at 68 degrees"
    "Note that I work from home on Fridays"
    "Remember: I don't like loud music"
)

for text in "${store_variations[@]}"; do
    resp=$(test_request "$text")
    check_result "memory" "Store: ${text:0:40}" "$text" "$resp" "memory" "memory"
    sleep 0.3
done

retrieve_variations=(
    "What do I like?"
    "What's my preference?"
    "What did I tell you about coffee?"
    "What temperature do I prefer?"
)

for text in "${retrieve_variations[@]}"; do
    resp=$(test_request "$text")
    check_result "memory" "Retrieve: ${text:0:40}" "$text" "$resp" "memory" "memory"
    sleep 0.3
done

# Test 4: Query Intents
echo ""
echo "[4] Testing Query Intents..."
query_variations=(
    "What's the capital of France?"
    "Who wrote Romeo and Juliet?"
    "How many days in a year?"
    "What is the speed of light?"
    "Explain photosynthesis"
)

for text in "${query_variations[@]}"; do
    resp=$(test_request "$text")
    check_result "query" "Query: ${text:0:40}" "$text" "$resp" "query" "interaction"
    sleep 0.3
done

# Test 5: Emergency Intents
echo ""
echo "[5] Testing Emergency Intents..."
emergency_variations=(
    "Help!"
    "Emergency!"
    "I need help"
)

for text in "${emergency_variations[@]}"; do
    resp=$(test_request "$text")
    check_result "emergency" "Emergency: $text" "$text" "$resp" "emergency" "interaction"
    sleep 0.3
done

# Test 6: Self-Improvement Intents
echo ""
echo "[6] Testing Self-Improvement Intents..."
si_variations=(
    "Improve the code"
    "Make the system better"
    "Optimize performance"
)

for text in "${si_variations[@]}"; do
    resp=$(test_request "$text")
    check_result "self_improvement" "SI: $text" "$text" "$resp" "self_improvement" "self_improvement"
    sleep 0.3
done

# Test 7: Meta Classification
echo ""
echo "[7] Testing Meta Agent Classification..."
test_cases=(
    "What time is it?|instant|instant"
    "What's the weather?|query|interaction"
    "Remember I like coffee|memory|memory"
    "Hello|instant|instant"
    "Tell me a joke|conversation|interaction"
    "Help!|emergency|interaction"
)

for case in "${test_cases[@]}"; do
    IFS='|' read -r text expected_intent expected_agent <<< "$case"
    resp=$(test_request "$text")
    check_result "meta" "Classification: ${text:0:30}" "$text" "$resp" "$expected_intent" "$expected_agent"
    sleep 0.2
done

# Summary
echo ""
echo "======================================================================"
echo "TEST SUMMARY"
echo "======================================================================"
echo ""
echo "Total Tests: $TOTAL"
echo "Passed: $PASSED ($(( PASSED * 100 / TOTAL ))%)"
echo "Failed: $FAILED ($(( FAILED * 100 / TOTAL ))%)"
echo ""

if [ ${#ISSUES[@]} -gt 0 ]; then
    echo "======================================================================"
    echo "ISSUES FOUND - NEEDS TO BE FIXED"
    echo "======================================================================"
    echo ""

    i=1
    for issue in "${ISSUES[@]}"; do
        IFS='|' read -r category test_name input_text intent agent issues_str <<< "$issue"
        echo "$i. $category - $test_name"
        echo "   Input: \"${input_text:0:80}\""
        echo "   Got: intent=$intent, agent=$agent"
        echo "   Issues: $issues_str"
        echo ""
        i=$((i + 1))
    done

    # Save to file
    {
        echo "["
        i=0
        for issue in "${ISSUES[@]}"; do
            IFS='|' read -r category test_name input_text intent agent issues_str <<< "$issue"
            if [ $i -gt 0 ]; then
                echo ","
            fi
            echo "  {"
            echo "    \"category\": \"$category\","
            echo "    \"test\": \"$test_name\","
            echo "    \"input\": \"$input_text\","
            echo "    \"intent\": \"$intent\","
            echo "    \"agent\": \"$agent\","
            echo "    \"issues\": \"$issues_str\""
            echo -n "  }"
            i=$((i + 1))
        done
        echo ""
        echo "]"
    } > intent_test_issues.json

    echo "✓ Issues saved to intent_test_issues.json"
else
    echo "✅ No issues found! All tests passed."
fi

echo ""
echo "======================================================================"

exit $([ $FAILED -eq 0 ] && echo 0 || echo 1)
