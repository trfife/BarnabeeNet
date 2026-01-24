# Tests

## Structure

- `unit/` - Unit tests for individual components
- `integration/` - Integration tests requiring services
- `e2e/` - End-to-end tests of full pipelines

## Running Tests

```bash
# All tests
pytest

# With coverage
pytest --cov=barnabeenet

# Specific test file
pytest tests/unit/test_meta_agent.py
```
