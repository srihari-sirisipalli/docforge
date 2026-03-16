# =============================================================================
# DocForge — Build & Development Makefile
# =============================================================================
# Usage:
#   make install      Install DocForge with core dependencies
#   make install-all  Install with ALL optional dependencies
#   make dev          Install in development mode with dev tools
#   make setup        Run first-time setup (hardware check, model download)
#   make test         Run the test suite
#   make lint         Run linter (ruff)
#   make typecheck    Run type checker (mypy)
#   make clean        Remove build artifacts and caches
# =============================================================================

.PHONY: install install-all dev setup test lint typecheck clean help

# Default target
help:
	@echo "DocForge Development Commands"
	@echo "=============================="
	@echo "  make install       Install core package"
	@echo "  make install-all   Install with all optional deps (VLM, OCR, GPU, GUI)"
	@echo "  make dev           Install in editable mode with dev tools"
	@echo "  make setup         First-time setup (detect hardware, download models)"
	@echo "  make test          Run test suite"
	@echo "  make lint          Run ruff linter"
	@echo "  make typecheck     Run mypy type checker"
	@echo "  make clean         Remove build artifacts"

install:
	pip install .

install-all:
	pip install ".[all]"

dev:
	pip install -e ".[dev,ocr]"

setup:
	docforge setup

test:
	pytest tests/ -v --tb=short

lint:
	ruff check src/ tests/

typecheck:
	mypy src/docforge/

clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	find . -type f -name "*.pyc" -delete 2>/dev/null || true
