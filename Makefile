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
.PHONY: install test test-cov lint build wheel spec clean all help

# =============================================================================
# Version configuration (aligned with chaosblade BLADE_VERSION)
# =============================================================================
DEFAULT_BLADE_VERSION := 1.8.0
BLADE_VERSION ?= $(DEFAULT_BLADE_VERSION)

# =============================================================================
# Build-target layout (mirrors chaosblade-exec-jvm so chaosblade can `cp -R` it)
#   build-target/chaosblade-<version>/lib/python   <- agent library
#   build-target/chaosblade-<version>/yaml/*.yaml  <- plugin spec
# =============================================================================
BUILD_TARGET := build-target
BUILD_TARGET_PKG_DIR := $(BUILD_TARGET)/chaosblade-$(BLADE_VERSION)
BUILD_TARGET_LIB := $(BUILD_TARGET_PKG_DIR)/lib
BUILD_TARGET_YAML := $(BUILD_TARGET_PKG_DIR)/yaml
PYTHON_LIB_DIR := $(BUILD_TARGET_LIB)/python
PYTHON_SPEC_FILE := $(BUILD_TARGET_YAML)/chaosblade-python-spec-$(BLADE_VERSION).yaml

# Python interpreter (overridable, e.g. make build PYTHON=python3.11)
PYTHON ?= python3

# Default target
all: install test build

# Install in development mode
install:
	$(PYTHON) -m pip install -e ".[dev]"

# Run tests
test:
	pytest tests/ -v --tb=short

# Run tests with coverage
test-cov:
	pytest tests/ -v --tb=short --cov=chaosblade --cov-report=term-missing --cov-report=html

# Lint / type check
lint:
	@echo "Running syntax checks..."
	$(PYTHON) -m py_compile src/chaosblade/__init__.py src/chaosblade/cli.py
	@echo "Checking imports..."
	$(PYTHON) -c "import chaosblade; print(f'OK: chaosblade v{chaosblade.__version__}')"

# Build the full product into build-target/chaosblade-<version>/{lib,yaml}.
# This layout mirrors chaosblade-exec-jvm; chaosblade's `python-agent` target
# copies it verbatim into the final blade package.
build:
	@echo "Building chaosblade python agent product (version: $(BLADE_VERSION))..."
	rm -rf $(BUILD_TARGET_PKG_DIR)
	mkdir -p $(PYTHON_LIB_DIR) $(BUILD_TARGET_YAML)
	@echo "Installing python agent library into $(PYTHON_LIB_DIR)..."
	$(PYTHON) -m pip install --target $(PYTHON_LIB_DIR) .
	@echo "Exporting plugin spec to $(PYTHON_SPEC_FILE)..."
	PYTHONPATH=$(PYTHON_LIB_DIR) $(PYTHON) -m chaosblade spec --output $(PYTHON_SPEC_FILE)
	@echo "Build complete: $(BUILD_TARGET_PKG_DIR)"

# Build wheel + sdist (PyPI-style distribution artifacts)
wheel:
	@echo "Building wheel and sdist..."
	$(PYTHON) -m build
	@echo "Build complete: dist/"

# Export the plugin spec yaml only. Requires the package (and its entry_points)
# to be importable, so run `make install` or `make build` first.
spec:
	$(PYTHON) -m chaosblade spec --output chaosblade-python-spec-$(BLADE_VERSION).yaml

# Clean all build artifacts
clean:
	rm -rf $(BUILD_TARGET) build/ dist/ *.egg-info src/*.egg-info .pytest_cache htmlcov .coverage
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
	@echo "  build     - Build full product into build-target/chaosblade-<version>/{lib,yaml}"
	@echo "  wheel     - Build wheel + sdist into dist/"
	@echo "  spec      - Export plugin spec yaml (requires installed package)"
	@echo "  clean     - Remove all build artifacts"
	@echo "  all       - install + test + build (default)"
	@echo "  help      - Display this help"
	@echo ""
	@echo "Environment variables:"
	@echo "  BLADE_VERSION - Product version (default: $(DEFAULT_BLADE_VERSION))"
	@echo "  PYTHON        - Python interpreter (default: python3)"
