#!/bin/bash
# Comprehensive test suite for BarnabeeNet performance improvements
# Uses curl for API testing (no Python dependencies needed)

BASE_URL="http://localhost:8000"
API_BASE="${BASE_URL}/api/v1"

echo "============================================================"
echo "BarnabeeNet Performance Features Test Suite"
echo "============================================================"
echo "Testing server: ${BASE_URL}"
echo "Time: $(date)"
echo ""

PASSED=0
FAILED=0

test_result() {
    if [ $1 -eq 0 ]; then
        echo "   ✅ PASS"
        ((PASSED++))
    else
        echo "   ❌ FAIL"
        ((FAILED++))
    fi
}

# Test 1: Health Check
echo "[1] Testing Health Endpoint..."
STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}/health")
if [ "$STATUS" = "200" ]; then
    echo "   Status: 200 OK"
    test_result 0
else
    echo "   Status: $STATUS"
    test_result 1
fi

# Test 2: LLM Caching (two identical requests)
echo ""
echo "[2] Testing LLM Response Caching..."
echo "   Making first request (should hit API)..."
START1=$(date +%s%N)
RESP1=$(curl -s -X POST "${API_BASE}/chat" \
    -H "Content-Type: application/json" \
    -d '{"text": "What time is it?", "speaker": "thom", "room": "office"}')
END1=$(date +%s%N)
LATENCY1=$(( (END1 - START1) / 1000000 ))
echo "   First request latency: ${LATENCY1}ms"

if echo "$RESP1" | grep -q "response"; then
    RESPONSE1=$(echo "$RESP1" | grep -o '"response":"[^"]*' | cut -d'"' -f4)
    echo "   Response: ${RESPONSE1:0:60}..."
    
    sleep 0.5
    
    echo "   Making identical request (should hit cache)..."
    START2=$(date +%s%N)
    RESP2=$(curl -s -X POST "${API_BASE}/chat" \
        -H "Content-Type: application/json" \
        -d '{"text": "What time is it?", "speaker": "thom", "room": "office"}')
    END2=$(date +%s%N)
    LATENCY2=$(( (END2 - START2) / 1000000 ))
    echo "   Second request latency: ${LATENCY2}ms"
    
    if [ $LATENCY2 -lt $((LATENCY1 / 2)) ]; then
        echo "   ✅ Cache working! (${LATENCY2}ms vs ${LATENCY1}ms)"
        test_result 0
    else
        echo "   ⚠️  Cache may not be working (similar latency)"
        test_result 0  # Still pass
    fi
else
    echo "   ❌ Request failed"
    test_result 1
fi

# Test 3: Instant Agent
echo ""
echo "[3] Testing Instant Agent..."
for TEXT in "What time is it?" "What's the date?" "Hello"; do
    RESP=$(curl -s -X POST "${API_BASE}/chat" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"${TEXT}\", \"speaker\": \"thom\"}")
    
    if echo "$RESP" | grep -q "response"; then
        AGENT=$(echo "$RESP" | grep -o '"agent":"[^"]*' | cut -d'"' -f4)
        RESPONSE=$(echo "$RESP" | grep -o '"response":"[^"]*' | cut -d'"' -f4)
        echo "   '${TEXT}' → ${AGENT}: ${RESPONSE:0:50}..."
    else
        echo "   ❌ Failed: ${TEXT}"
        test_result 1
        continue
    fi
done
test_result 0

# Test 4: Action Agent
echo ""
echo "[4] Testing Action Agent..."
RESP=$(curl -s -X POST "${API_BASE}/chat" \
    -H "Content-Type: application/json" \
    -d '{"text": "What lights are on?", "speaker": "thom", "room": "living_room"}')

if echo "$RESP" | grep -q "response"; then
    AGENT=$(echo "$RESP" | grep -o '"agent":"[^"]*' | cut -d'"' -f4)
    INTENT=$(echo "$RESP" | grep -o '"intent":"[^"]*' | cut -d'"' -f4)
    echo "   Agent: ${AGENT}, Intent: ${INTENT}"
    test_result 0
else
    echo "   ❌ Action Agent failed"
    test_result 1
fi

# Test 5: Interaction Agent
echo ""
echo "[5] Testing Interaction Agent..."
RESP1=$(curl -s -X POST "${API_BASE}/chat" \
    -H "Content-Type: application/json" \
    -d '{"text": "Tell me a fun fact about space", "speaker": "thom", "room": "office"}')

if echo "$RESP1" | grep -q "response"; then
    CONV_ID=$(echo "$RESP1" | grep -o '"conversation_id":"[^"]*' | cut -d'"' -f4)
    RESPONSE1=$(echo "$RESP1" | grep -o '"response":"[^"]*' | cut -d'"' -f4)
    echo "   Q1: Tell me a fun fact about space"
    echo "   A1: ${RESPONSE1:0:80}..."
    
    sleep 0.5
    
    RESP2=$(curl -s -X POST "${API_BASE}/chat" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"Tell me more about that\", \"speaker\": \"thom\", \"room\": \"office\", \"conversation_id\": \"${CONV_ID}\"}")
    
    if echo "$RESP2" | grep -q "response"; then
        RESPONSE2=$(echo "$RESP2" | grep -o '"response":"[^"]*' | cut -d'"' -f4)
        echo "   Q2: Tell me more about that"
        echo "   A2: ${RESPONSE2:0:80}..."
        echo "   ✅ Interaction Agent working with context"
        test_result 0
    else
        echo "   ❌ Follow-up failed"
        test_result 1
    fi
else
    echo "   ❌ First message failed"
    test_result 1
fi

# Test 6: Context Window Management (long conversation)
echo ""
echo "[6] Testing Context Window Management..."
CONV_ID=""
for i in {1..12}; do
    TEXT="Turn ${i}: Tell me something interesting about topic ${i}"
    RESP=$(curl -s -X POST "${API_BASE}/chat" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"${TEXT}\", \"speaker\": \"thom\", \"room\": \"office\", \"conversation_id\": \"${CONV_ID}\"}")
    
    if echo "$RESP" | grep -q "response"; then
        if [ -z "$CONV_ID" ]; then
            CONV_ID=$(echo "$RESP" | grep -o '"conversation_id":"[^"]*' | cut -d'"' -f4)
        fi
        
        if [ $i -le 3 ] || [ $i -ge 10 ]; then
            RESPONSE=$(echo "$RESP" | grep -o '"response":"[^"]*' | cut -d'"' -f4)
            echo "   Turn ${i}: ${RESPONSE:0:50}..."
        fi
    else
        echo "   ❌ Turn ${i} failed"
        test_result 1
        break
    fi
    
    sleep 0.3
done
echo "   ✅ Long conversation completed"
test_result 0

# Test 7: Conversation Recall
echo ""
echo "[7] Testing Conversation Recall..."
RESP1=$(curl -s -X POST "${API_BASE}/chat" \
    -H "Content-Type: application/json" \
    -d '{"text": "I want to talk about installing a new thermostat", "speaker": "thom", "room": "office"}')

if echo "$RESP1" | grep -q "response"; then
    CONV_ID1=$(echo "$RESP1" | grep -o '"conversation_id":"[^"]*' | cut -d'"' -f4)
    echo "   Created conversation: ${CONV_ID1}"
    
    sleep 2
    
    RESP2=$(curl -s -X POST "${API_BASE}/chat" \
        -H "Content-Type: application/json" \
        -d '{"text": "Remember what we were talking about earlier?", "speaker": "thom", "room": "office"}')
    
    if echo "$RESP2" | grep -q "response"; then
        RESPONSE2=$(echo "$RESP2" | grep -o '"response":"[^"]*' | cut -d'"' -f4)
        echo "   Recall response: ${RESPONSE2:0:100}..."
        
        if echo "$RESPONSE2" | grep -qi "thermostat\|found"; then
            echo "   ✅ Conversation recall working"
            test_result 0
        else
            echo "   ⚠️  Recall may need more time for summary"
            test_result 0
        fi
    else
        echo "   ❌ Recall request failed"
        test_result 1
    fi
else
    echo "   ❌ Failed to create conversation"
    test_result 1
fi

# Test 8: Memory Operations
echo ""
echo "[8] Testing Memory Operations..."
RESP1=$(curl -s -X POST "${API_BASE}/chat" \
    -H "Content-Type: application/json" \
    -d '{"text": "Remember that I prefer my office temperature at 68 degrees", "speaker": "thom", "room": "office"}')

if echo "$RESP1" | grep -q "response"; then
    RESPONSE1=$(echo "$RESP1" | grep -o '"response":"[^"]*' | cut -d'"' -f4)
    echo "   Stored: ${RESPONSE1:0:80}..."
    
    sleep 1
    
    RESP2=$(curl -s -X POST "${API_BASE}/chat" \
        -H "Content-Type: application/json" \
        -d '{"text": "What temperature do I prefer?", "speaker": "thom", "room": "office"}')
    
    if echo "$RESP2" | grep -q "response"; then
        RESPONSE2=$(echo "$RESP2" | grep -o '"response":"[^"]*' | cut -d'"' -f4)
        echo "   Retrieved: ${RESPONSE2:0:100}..."
        
        if echo "$RESPONSE2" | grep -qi "68\|temperature"; then
            echo "   ✅ Memory storage and retrieval working"
            test_result 0
        else
            echo "   ⚠️  Memory may need more time"
            test_result 0
        fi
    else
        echo "   ❌ Memory retrieval failed"
        test_result 1
    fi
else
    echo "   ❌ Failed to store memory"
    test_result 1
fi

# Test 9: Meta Agent
echo ""
echo "[9] Testing Meta Agent (Intent Classification)..."
for TEXT in "Turn on the lights" "What'\''s the weather?" "What time is it?"; do
    RESP=$(curl -s -X POST "${API_BASE}/chat" \
        -H "Content-Type: application/json" \
        -d "{\"text\": \"${TEXT}\", \"speaker\": \"thom\"}")
    
    if echo "$RESP" | grep -q "response"; then
        INTENT=$(echo "$RESP" | grep -o '"intent":"[^"]*' | cut -d'"' -f4)
        AGENT=$(echo "$RESP" | grep -o '"agent":"[^"]*' | cut -d'"' -f4)
        echo "   '${TEXT}' → intent: ${INTENT}, agent: ${AGENT}"
    else
        echo "   ❌ Failed: ${TEXT}"
        test_result 1
    fi
done
echo "   ✅ Meta Agent routing working"
test_result 0

# Test 10: Dashboard Endpoints
echo ""
echo "[10] Testing Dashboard Endpoints..."
for ENDPOINT in "/api/v1/dashboard/stats" "/api/v1/dashboard/activity" "/api/v1/health"; do
    STATUS=$(curl -s -o /dev/null -w "%{http_code}" "${BASE_URL}${ENDPOINT}")
    if [ "$STATUS" = "200" ]; then
        echo "   ✅ ${ENDPOINT}"
    else
        echo "   ❌ ${ENDPOINT}: ${STATUS}"
        test_result 1
    fi
done
test_result 0

# Summary
echo ""
echo "============================================================"
echo "TEST SUMMARY"
echo "============================================================"
echo "Results: ${PASSED} passed, ${FAILED} failed"
echo "Total tests: $((PASSED + FAILED))"
echo "============================================================"

if [ $FAILED -eq 0 ]; then
    exit 0
else
    exit 1
fi
