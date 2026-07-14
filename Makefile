# Copyright 2025 The ChaosBlade Authors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

# ChaosBlade Python Executor Makefile
.PHONY: install test test-cov lint build clean all help

VERSION ?= 0.1.0

# Default target
all: install test build

# Install in development mode
install:
	pip install -e ".[dev]"

# Run tests
test:
	pytest tests/ -v --tb=short

# Run tests with coverage
test-cov:
	pytest tests/ -v --tb=short --cov=chaosblade --cov-report=term-missing --cov-report=html

# Lint / type check
lint:
	@echo "Running syntax checks..."
	python -m py_compile src/chaosblade/__init__.py
	@echo "Checking imports..."
	python -c "import chaosblade; print(f'OK: chaosblade v{chaosblade.__version__}')"

# Build wheel package
build:
	@echo "Building wheel..."
	python -m build --wheel
	@echo "Build complete: dist/"

# Clean all build artifacts
clean:
	rm -rf build/ dist/ *.egg-info src/*.egg-info .pytest_cache htmlcov .coverage
	find . -type d -name __pycache__ -exec rm -rf {} + 2>/dev/null || true
	@echo "Clean complete"

# Display help
help:
	@echo "ChaosBlade Python Executor - Build Tools"
	@echo ""
	@echo "Available targets:"
	@echo "  install   - Install in development mode with dev dependencies"
	@echo "  test      - Run test suite"
	@echo "  test-cov  - Run tests with coverage report"
	@echo "  lint      - Run syntax and import checks"
	@echo "  build     - Build wheel package"
	@echo "  clean     - Remove all build artifacts"
	@echo "  all       - install + test + build (default)"
	@echo "  help      - Display this help"
	@echo ""
	@echo "Environment variables:"
	@echo "  VERSION   - Package version (default: $(VERSION))"
