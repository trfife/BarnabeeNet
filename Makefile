.PHONY: help install test lint format validate deploy logs ssh llm-paid llm-cheap llm-status

help:
	@echo "BarnabeeNet Development Commands"
	@echo "================================"
	@echo "make install    - Set up development environment"
	@echo "make test       - Run tests"
	@echo "make lint       - Run linter"
	@echo "make format     - Format code"
	@echo "make validate   - Full validation suite"
	@echo "make deploy     - Deploy to VM"
	@echo "make logs       - View VM logs"
	@echo "make ssh        - SSH to VM"
	@echo ""
	@echo "LLM Configuration:"
	@echo "make llm-status - Show current LLM config"
	@echo "make llm-paid   - Switch to paid models (best quality)"
	@echo "make llm-cheap  - Switch to low-cost models (10x cheaper)"

install:
	python -m venv .venv
	.venv/bin/pip install -e ".[dev]"
	ln -sf ../../scripts/pre-commit.sh .git/hooks/pre-commit
	chmod +x scripts/*.sh
	@echo "✓ Development environment ready"

test:
	.venv/bin/pytest -xvs

lint:
	.venv/bin/ruff check src/ tests/

format:
	.venv/bin/ruff format src/ tests/
	.venv/bin/ruff check --fix src/ tests/

validate:
	./scripts/validate.sh

deploy:
	git push
	ssh thom@192.168.86.51 'cd ~/barnabeenet && git pull'

logs:
	ssh thom@192.168.86.51 'cd ~/barnabeenet && podman-compose logs -f'

ssh:
	ssh thom@192.168.86.51

# LLM Configuration switching
llm-status:
	@bash scripts/switch-llm-config.sh status

llm-paid:
	@bash scripts/switch-llm-config.sh paid

llm-cheap:
	@bash scripts/switch-llm-config.sh cheap