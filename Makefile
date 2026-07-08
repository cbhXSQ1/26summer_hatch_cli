.PHONY: test build clean install dev-install lint typecheck

# Run all tests
test:
	pytest -v

# Build wheel package
build:
	python -m build

# Clean build artifacts
clean:
	rm -rf dist/ build/ *.egg-info/ .pytest_cache/
	rm -rf __pycache__/ hatch/__pycache__/ hatch/**/__pycache__/
	rm -rf .mypy_cache/

# Install the package
install:
	pip install .

# Install in editable mode with dev dependencies
dev-install:
	pip install -e ".[dev]"

# Run flake8 linting
lint:
	flake8 hatch/ tests/

# Run mypy type checking
typecheck:
	mypy hatch/