#!/usr/bin/env bash
# BarnabeeNet Debug Log Helper for Self-Improvement Agent
# Usage: ./scripts/debug-logs.sh <command> [args]

set -euo pipefail

API_BASE="${BARNABEENET_API:-http://localhost:8000}"
REDIS_URL="${REDIS_URL:-redis://localhost:6379}"

case "${1:-help}" in
    # Get recent activity feed
    activity)
        limit="${2:-50}"
        curl -s "$API_BASE/api/v1/activity/feed?limit=$limit" | jq '.activities[] | {timestamp, type, source, title, level}'
        ;;

    # Get recent conversation traces
    traces)
        limit="${2:-10}"
        curl -s "$API_BASE/api/v1/activity/traces?limit=$limit" | jq '.traces[] | {trace_id, started_at, input: .input[:80], final_response: .final_response[:80], total_latency_ms}'
        ;;

    # Get specific trace with full reasoning chain
    trace)
        trace_id="$2"
        curl -s "$API_BASE/api/v1/activity/traces/$trace_id" | jq '.'
        ;;

    # Get recent errors from activity log
    errors)
        limit="${2:-20}"
        curl -s "$API_BASE/api/v1/activity/feed?limit=500&level=error" | jq ".activities[:$limit]"
        ;;

    # Get LLM call history (recent signals)
    llm-calls)
        limit="${2:-20}"
        redis-cli -u "$REDIS_URL" XREVRANGE barnabeenet:signals:llm + - COUNT "$limit" 2>/dev/null | head -100 || \
        echo "Redis not available or signals stream empty"
        ;;

    # Get activity stream (raw Redis)
    stream)
        limit="${2:-50}"
        redis-cli -u "$REDIS_URL" XREVRANGE barnabeenet:activity:stream + - COUNT "$limit" 2>/dev/null || \
        echo "Redis not available or activity stream empty"
        ;;

    # Search activity by type (e.g., "agent.decision", "llm.error")
    search)
        activity_type="$2"
        limit="${3:-50}"
        curl -s "$API_BASE/api/v1/activity/feed?limit=$limit&types=$activity_type" | jq '.activities'
        ;;

    # Get HA error log
    ha-errors)
        curl -s "$API_BASE/api/v1/homeassistant/logs" | jq '.entries | map(select(.level == "ERROR" or .level == "WARNING")) | .[:20]'
        ;;

    # Get system journal logs
    journal)
        lines="${2:-100}"
        journalctl -u barnabeenet --no-pager -n "$lines" 2>/dev/null || \
        echo "Journal not available (not running as systemd service?)"
        ;;

    # Get journal errors only
    journal-errors)
        lines="${2:-50}"
        journalctl -u barnabeenet --no-pager -n 500 -p err 2>/dev/null | head -n "$lines" || \
        echo "Journal not available"
        ;;

    # Get pipeline stats
    stats)
        curl -s "$API_BASE/api/v1/dashboard/stats" | jq '.'
        ;;

    # Get latency history for component
    latency)
        component="${2:-stt}"
        minutes="${3:-60}"
        curl -s "$API_BASE/api/v1/dashboard/metrics/latency/$component?window_minutes=$minutes" | jq '.'
        ;;

    # Get health status
    health)
        curl -s "$API_BASE/health" | jq '.'
        ;;

    # Get self-improvement sessions
    improve-sessions)
        curl -s "$API_BASE/api/v1/self-improve/sessions" | jq '.'
        ;;

    # Get self-improvement cost report
    improve-costs)
        curl -s "$API_BASE/api/v1/self-improve/cost-report" | jq '.'
        ;;

    help|*)
        cat <<EOF
BarnabeeNet Debug Log Helper

Usage: ./scripts/debug-logs.sh <command> [args]

Commands:
  activity [limit]           Get recent activity feed (default: 50)
  traces [limit]             Get recent conversation traces (default: 10)
  trace <trace_id>           Get specific trace with full reasoning chain
  errors [limit]             Get recent errors (default: 20)
  llm-calls [limit]          Get recent LLM calls from Redis (default: 20)
  stream [limit]             Get raw activity stream from Redis (default: 50)
  search <type> [limit]      Search by activity type (e.g., "agent.decision")
  ha-errors                  Get Home Assistant error log
  journal [lines]            Get systemd journal logs (default: 100)
  journal-errors [lines]     Get journal errors only (default: 50)
  stats                      Get pipeline statistics
  latency <component> [min]  Get latency history (stt|tts|llm, default: 60 min)
  health                     Get service health status
  improve-sessions           Get self-improvement sessions
  improve-costs              Get self-improvement cost report

Activity Types:
  user.input, user.voice, agent.thinking, agent.decision, agent.response,
  meta.classify, meta.route, instant.match, action.parse, action.execute,
  interaction.respond, memory.search, memory.store, llm.request, llm.response,
  llm.error, ha.state_change, ha.service_call, system.error

Examples:
  ./scripts/debug-logs.sh traces 5                    # Last 5 conversations
  ./scripts/debug-logs.sh trace abc123                # Full trace details
  ./scripts/debug-logs.sh search llm.error 10        # Recent LLM errors
  ./scripts/debug-logs.sh errors                      # Recent system errors
  ./scripts/debug-logs.sh health                      # Service health
EOF
        ;;
esac
