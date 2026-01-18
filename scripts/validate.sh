#!/bin/bash
# BarnabeeNet validation script - run before every commit

set -e  # Exit on first error

echo "🔍 BarnabeeNet Validation Suite"
echo "================================"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

# Track failures
FAILED=0

# Activate venv if exists
if [ -d ".venv" ]; then
    source .venv/bin/activate
fi

# 1. Check for secrets (real API keys, not placeholders/docs)
echo -e "\n${YELLOW}[1/6] Checking for secrets...${NC}"
# Look for actual API keys (longer strings) but exclude:
# - .env.example files
# - placeholder patterns like "sk-..." or "sk-or-v1-..."
# - test fixtures with obvious fake values
# - documentation strings about key formats
SECRETS_FOUND=$(grep -rE "(sk-[a-zA-Z0-9]{20,}|sk-ant-[a-zA-Z0-9]{20,}|sk-or-v1-[a-zA-Z0-9]{20,})" \
    --include="*.py" --include="*.yaml" --include="*.json" \
    src/ tests/ workers/ config/ 2>/dev/null \
    | grep -v ".env.example" \
    | grep -v "placeholder" \
    | grep -v "starts with" \
    | grep -v "_mask_value" \
    | grep -v "sk-test" \
    | grep -v "sk-secret-value" \
    | grep -v "sk-abcdefghijklmnop" || true)

if [ -n "$SECRETS_FOUND" ]; then
    echo "$SECRETS_FOUND"
    echo -e "${RED}❌ Potential secrets found!${NC}"
    FAILED=1
else
    echo -e "${GREEN}✓ No secrets detected${NC}"
fi

# 2. Ruff format check
echo -e "\n${YELLOW}[2/6] Checking code formatting...${NC}"
if ruff format --check src/ tests/ 2>/dev/null; then
    echo -e "${GREEN}✓ Code formatting OK${NC}"
else
    echo -e "${RED}❌ Formatting issues found. Run: ruff format src/ tests/${NC}"
    FAILED=1
fi

# 3. Ruff lint
echo -e "\n${YELLOW}[3/6] Running linter...${NC}"
if ruff check src/ tests/ 2>/dev/null; then
    echo -e "${GREEN}✓ Linting passed${NC}"
else
    echo -e "${RED}❌ Linting issues found${NC}"
    FAILED=1
fi

# 4. Type checking
echo -e "\n${YELLOW}[4/6] Type checking...${NC}"
if command -v pyright &> /dev/null; then
    if pyright src/ 2>/dev/null; then
        echo -e "${GREEN}✓ Type checking passed${NC}"
    else
        echo -e "${RED}❌ Type errors found${NC}"
        FAILED=1
    fi
else
    echo -e "${YELLOW}⚠ Pyright not installed, skipping type check${NC}"
fi

# 5. Tests
echo -e "\n${YELLOW}[5/6] Running tests...${NC}"
if pytest tests/ -x --tb=short -q 2>/dev/null; then
    echo -e "${GREEN}✓ All tests passed${NC}"
else
    echo -e "${RED}❌ Tests failed${NC}"
    FAILED=1
fi

# 6. Check CONTEXT.md is updated
echo -e "\n${YELLOW}[6/6] Checking CONTEXT.md...${NC}"
if [ -f "CONTEXT.md" ]; then
    # Check if modified in this session (within last hour)
    if [ $(find CONTEXT.md -mmin -60 2>/dev/null | wc -l) -gt 0 ]; then
        echo -e "${GREEN}✓ CONTEXT.md recently updated${NC}"
    else
        echo -e "${YELLOW}⚠ CONTEXT.md not updated recently - consider updating${NC}"
    fi
else
    echo -e "${YELLOW}⚠ CONTEXT.md not found${NC}"
fi

# Summary
echo -e "\n================================"
if [ $FAILED -eq 0 ]; then
    echo -e "${GREEN}✅ All checks passed - OK to commit${NC}"
    exit 0
else
    echo -e "${RED}❌ Validation failed - fix issues before committing${NC}"
    exit 1
fi
