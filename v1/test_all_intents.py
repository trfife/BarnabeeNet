#!/usr/bin/env python3
"""Comprehensive intent testing for BarnabeeNet.

Tests all intent categories with multiple variations to ensure proper routing and handling.
Excludes Home Assistant device control.
"""

import asyncio
import json
import time
from datetime import datetime
from typing import Any

import httpx


BASE_URL = "http://192.168.86.51:8000"
API_BASE = f"{BASE_URL}/api/v1"

# Test results tracking
results: list[dict[str, Any]] = []
issues: list[dict[str, Any]] = []


async def test_request(text: str, speaker: str = "thom", room: str = "office") -> dict[str, Any]:
    """Make a test request and return response."""
    async with httpx.AsyncClient(timeout=30.0) as client:
        try:
            resp = await client.post(
                f"{API_BASE}/chat",
                json={
                    "text": text,
                    "speaker": speaker,
                    "room": room,
                },
            )
            if resp.status_code == 200:
                return resp.json()
            else:
                return {"error": f"HTTP {resp.status_code}", "response": resp.text}
        except Exception as e:
            return {"error": str(e)}


def record_result(
    category: str,
    test_name: str,
    input_text: str,
    result: dict[str, Any],
    expected_intent: str | None = None,
    expected_agent: str | None = None,
) -> None:
    """Record test result and check for issues."""
    intent = result.get("intent", "unknown")
    agent = result.get("agent", "unknown")
    response = result.get("response", "")
    error = result.get("error")

    passed = True
    issues_found = []

    # Check for errors
    if error:
        passed = False
        issues_found.append(f"Error: {error}")

    # Check intent classification
    if expected_intent and intent != expected_intent:
        passed = False
        issues_found.append(f"Intent mismatch: expected '{expected_intent}', got '{intent}'")

    # Check agent routing
    if expected_agent and agent != expected_agent:
        passed = False
        issues_found.append(f"Agent mismatch: expected '{expected_agent}', got '{agent}'")

    # Check for empty/invalid responses
    if not response or len(response.strip()) < 5:
        passed = False
        issues_found.append(f"Empty or too short response: '{response[:50]}'")

    result_entry = {
        "category": category,
        "test": test_name,
        "input": input_text,
        "intent": intent,
        "agent": agent,
        "response_length": len(response),
        "passed": passed,
        "issues": issues_found,
        "response_preview": response[:100] if response else "",
    }

    results.append(result_entry)

    if not passed:
        issues.append(result_entry)
        print(f"  ❌ {test_name}: {', '.join(issues_found)}")
    else:
        print(f"  ✅ {test_name}: {intent} → {agent}")


async def test_instant_intents():
    """Test Instant Agent intents (time, date, greetings)."""
    print("\n[1] Testing Instant Agent Intents...")

    # Time queries
    time_variations = [
        "What time is it?",
        "What's the time?",
        "Tell me the time",
        "Time?",
        "What time?",
        "Current time",
    ]

    for text in time_variations:
        result = await test_request(text)
        record_result("instant", f"Time: {text}", text, result, "instant", "instant")
        await asyncio.sleep(0.2)

    # Date queries
    date_variations = [
        "What's the date?",
        "What date is it?",
        "Tell me the date",
        "Date?",
        "What's today's date?",
        "Current date",
    ]

    for text in date_variations:
        result = await test_request(text)
        record_result("instant", f"Date: {text}", text, result, "instant", "instant")
        await asyncio.sleep(0.2)

    # Greetings
    greeting_variations = [
        "Hello",
        "Hi",
        "Hey",
        "Good morning",
        "Good afternoon",
        "Good evening",
        "Greetings",
    ]

    for text in greeting_variations:
        result = await test_request(text)
        record_result("instant", f"Greeting: {text}", text, result, "instant", "instant")
        await asyncio.sleep(0.2)


async def test_interaction_intents():
    """Test Interaction Agent intents (conversations, queries)."""
    print("\n[2] Testing Interaction Agent Intents...")

    # General questions
    question_variations = [
        "What's the weather like?",
        "Tell me a joke",
        "What can you do?",
        "Explain quantum computing",
        "What is artificial intelligence?",
        "How does machine learning work?",
        "Tell me about space",
        "What are the planets?",
    ]

    for text in question_variations:
        result = await test_request(text)
        record_result("interaction", f"Question: {text[:40]}", text, result, "conversation", "interaction")
        await asyncio.sleep(0.3)

    # Follow-up conversations
    print("  Testing follow-up conversations...")
    conv_id = None
    follow_ups = [
        ("Tell me about the solar system", None),
        ("What about Mars?", None),
        ("How far is it?", None),
        ("Tell me more", None),
    ]

    for text, _ in follow_ups:
        result = await test_request(text, conversation_id=conv_id)
        if not conv_id:
            conv_id = result.get("conversation_id")
        record_result("interaction", f"Follow-up: {text}", text, result, "conversation", "interaction")
        await asyncio.sleep(0.3)


async def test_memory_intents():
    """Test Memory Agent intents (store, retrieve, forget)."""
    print("\n[3] Testing Memory Agent Intents...")

    # Store memory
    store_variations = [
        "Remember that I like coffee in the morning",
        "I prefer my office temperature at 68 degrees",
        "Note that I work from home on Fridays",
        "Remember: I don't like loud music",
        "Store this: My favorite color is blue",
    ]

    for text in store_variations:
        result = await test_request(text)
        record_result("memory", f"Store: {text[:40]}", text, result, "memory", "memory")
        await asyncio.sleep(0.3)

    # Retrieve memory
    retrieve_variations = [
        "What do I like?",
        "What's my preference?",
        "What did I tell you about coffee?",
        "What temperature do I prefer?",
        "What do you remember about me?",
    ]

    for text in retrieve_variations:
        result = await test_request(text)
        record_result("memory", f"Retrieve: {text[:40]}", text, result, "memory", "memory")
        await asyncio.sleep(0.3)

    # Forget memory
    forget_variations = [
        "Forget what I said about coffee",
        "Delete the memory about temperature",
        "Remove that preference",
    ]

    for text in forget_variations:
        result = await test_request(text)
        record_result("memory", f"Forget: {text[:40]}", text, result, "memory", "memory")
        await asyncio.sleep(0.3)


async def test_query_intents():
    """Test query intents (should route to interaction agent)."""
    print("\n[4] Testing Query Intents...")

    query_variations = [
        "What's the capital of France?",
        "Who wrote Romeo and Juliet?",
        "How many days in a year?",
        "What is the speed of light?",
        "Explain photosynthesis",
        "What is gravity?",
        "Tell me about the internet",
    ]

    for text in query_variations:
        result = await test_request(text)
        record_result("query", f"Query: {text[:40]}", text, result, "query", "interaction")
        await asyncio.sleep(0.3)


async def test_emergency_intents():
    """Test emergency intents."""
    print("\n[5] Testing Emergency Intents...")

    emergency_variations = [
        "Help!",
        "Emergency!",
        "I need help",
        "Call 911",
        "Something's wrong",
    ]

    for text in emergency_variations:
        result = await test_request(text)
        record_result("emergency", f"Emergency: {text}", text, result, "emergency", "interaction")
        await asyncio.sleep(0.3)


async def test_self_improvement_intents():
    """Test self-improvement intents."""
    print("\n[6] Testing Self-Improvement Intents...")

    si_variations = [
        "Improve the code",
        "Make the system better",
        "Optimize performance",
        "Self-improve",
    ]

    for text in si_variations:
        result = await test_request(text)
        record_result("self_improvement", f"SI: {text}", text, result, "self_improvement", "self_improvement")
        await asyncio.sleep(0.3)


async def test_meta_classification():
    """Test Meta Agent intent classification accuracy."""
    print("\n[7] Testing Meta Agent Classification...")

    test_cases = [
        ("What time is it?", "instant", "instant"),
        ("Turn on the lights", "action", "action"),  # Will fail device control, but intent should be correct
        ("What's the weather?", "query", "interaction"),
        ("Remember I like coffee", "memory", "memory"),
        ("Hello", "instant", "instant"),
        ("Tell me a joke", "conversation", "interaction"),
        ("Help!", "emergency", "interaction"),
    ]

    for text, expected_intent, expected_agent in test_cases:
        result = await test_request(text)
        record_result("meta", f"Classification: {text[:30]}", text, result, expected_intent, expected_agent)
        await asyncio.sleep(0.2)


async def test_edge_cases():
    """Test edge cases and unusual inputs."""
    print("\n[8] Testing Edge Cases...")

    edge_cases = [
        ("", "Empty string"),
        ("   ", "Whitespace only"),
        ("?", "Single character"),
        ("What", "Single word"),
        ("What time is it? What's the date? Hello", "Multiple questions"),
        ("A" * 500, "Very long input"),
        ("What time is it? " * 10, "Repeated question"),
    ]

    for text, description in edge_cases:
        result = await test_request(text)
        record_result("edge_case", description, text[:100], result)
        await asyncio.sleep(0.2)


async def main():
    """Run all intent tests."""
    print("=" * 70)
    print("BarnabeeNet Intent Testing Suite")
    print("=" * 70)
    print(f"Server: {BASE_URL}")
    print(f"Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
    print("\nTesting all intents (excluding Home Assistant device control)...")

    start_time = time.time()

    # Run all test suites
    await test_instant_intents()
    await test_interaction_intents()
    await test_memory_intents()
    await test_query_intents()
    await test_emergency_intents()
    await test_self_improvement_intents()
    await test_meta_classification()
    await test_edge_cases()

    total_time = time.time() - start_time

    # Summary
    print("\n" + "=" * 70)
    print("TEST SUMMARY")
    print("=" * 70)

    total_tests = len(results)
    passed_tests = sum(1 for r in results if r["passed"])
    failed_tests = total_tests - passed_tests

    print(f"\nTotal Tests: {total_tests}")
    print(f"Passed: {passed_tests} ({passed_tests/total_tests*100:.1f}%)")
    print(f"Failed: {failed_tests} ({failed_tests/total_tests*100:.1f}%)")
    print(f"Total Time: {total_time:.1f}s")

    # Group by category
    print("\nResults by Category:")
    categories = {}
    for r in results:
        cat = r["category"]
        if cat not in categories:
            categories[cat] = {"total": 0, "passed": 0}
        categories[cat]["total"] += 1
        if r["passed"]:
            categories[cat]["passed"] += 1

    for cat, stats in sorted(categories.items()):
        pct = stats["passed"] / stats["total"] * 100
        print(f"  {cat:20s}: {stats['passed']:3d}/{stats['total']:3d} ({pct:5.1f}%)")

    # Issues list
    if issues:
        print("\n" + "=" * 70)
        print("ISSUES FOUND - NEEDS TO BE FIXED")
        print("=" * 70)

        for i, issue in enumerate(issues, 1):
            print(f"\n{i}. {issue['category']} - {issue['test']}")
            print(f"   Input: \"{issue['input'][:80]}\"")
            print(f"   Got: intent={issue['intent']}, agent={issue['agent']}")
            print(f"   Issues: {', '.join(issue['issues'])}")
            if issue['response_preview']:
                print(f"   Response: {issue['response_preview']}...")

        # Save issues to file
        with open("intent_test_issues.json", "w") as f:
            json.dump(issues, f, indent=2)
        print(f"\n✓ Issues saved to intent_test_issues.json")
    else:
        print("\n✅ No issues found! All tests passed.")

    print("\n" + "=" * 70)

    return failed_tests == 0


if __name__ == "__main__":
    success = asyncio.run(main())
    exit(0 if success else 1)
