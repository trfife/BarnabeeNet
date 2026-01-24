#!/bin/bash
# Clear all BarnabeeNet data: memories, conversations, caches, profiles

set -e

REDIS_URL="${REDIS_URL:-redis://localhost:6379}"

echo "🗑️  Clearing all BarnabeeNet data..."
echo "=================================="

# Check if redis-cli is available
if ! command -v redis-cli &> /dev/null; then
    echo "❌ redis-cli not found. Install Redis tools."
    exit 1
fi

echo ""
echo "⚠️  WARNING: This will delete ALL data:"
echo "   - All memories"
echo "   - All conversations"
echo "   - All working memory"
echo "   - All profiles (cached)"
echo "   - All activity logs"
echo "   - All metrics"
echo ""
read -p "Are you sure? Type 'yes' to continue: " confirm

if [ "$confirm" != "yes" ]; then
    echo "Cancelled."
    exit 0
fi

echo ""
echo "Clearing Redis data..."

# Clear all BarnabeeNet keys
redis-cli --scan --pattern "barnabeenet:*" | while read key; do
    redis-cli DEL "$key"
    echo "  Deleted: $key"
done

# Clear conversation contexts
redis-cli --scan --pattern "conversation:*" | while read key; do
    redis-cli DEL "$key"
    echo "  Deleted: $key"
done

# Clear working memory
redis-cli --scan --pattern "working:*" | while read key; do
    redis-cli DEL "$key"
    echo "  Deleted: $key"
done

# Clear memory storage
redis-cli --scan --pattern "memory:*" | while read key; do
    redis-cli DEL "$key"
    echo "  Deleted: $key"
done

# Clear profile cache
redis-cli --scan --pattern "profile:*" | while read key; do
    redis-cli DEL "$key"
    echo "  Deleted: $key"
done

# Clear activity logs
redis-cli --scan --pattern "activity:*" | while read key; do
    redis-cli DEL "$key"
    echo "  Deleted: $key"
done

# Clear metrics
redis-cli --scan --pattern "metrics:*" | while read key; do
    redis-cli DEL "$key"
    echo "  Deleted: $key"
done

# Clear pipeline signals
redis-cli --scan --pattern "pipeline:*" | while read key; do
    redis-cli DEL "$key"
    echo "  Deleted: $key"
done

# Clear self-improvement sessions
redis-cli --scan --pattern "self_improvement:*" | while read key; do
    redis-cli DEL "$key"
    echo "  Deleted: $key"
done

echo ""
echo "✅ All data cleared!"
echo ""
echo "Note: Profiles stored in Redis will need to be re-synced from Home Assistant"
echo "      if you want to keep them."
