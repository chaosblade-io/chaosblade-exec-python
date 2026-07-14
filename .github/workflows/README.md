# GitHub Actions Workflow Documentation

This project contains two GitHub Actions workflows for automated building, testing, and releasing.

## Workflow Files

### 1. CI Workflow (`ci.yml`)

**Triggers:**
- Push to `main` or `master` branch
- Pull Request to `main` or `master` branch

**Features:**
- Python version matrix testing (3.9, 3.10, 3.11, 3.12, 3.13)
- Development dependency installation
- Full test suite execution with coverage reporting
- Coverage report upload as artifact
- Wheel build verification

**Jobs:**
1. **test:** Run test suite across multiple Python versions
2. **build:** Build wheel package and verify installation

**Artifacts:**
- Coverage report: `coverage-report` (HTML format)
- Wheel package: `wheel-package`
- Artifacts are retained for 7 days

### 2. Release Workflow (`release.yml`)

**Triggers:**
- Push version tags (format: `v*`, e.g., `v0.1.0`)

**Features:**
- Build wheel package from tagged version
- Create GitHub Release with auto-generated notes
- Upload wheel as release asset

## Usage

### Daily Development

1. **For PRs:** CI workflow runs full test suite on all supported Python versions
2. **For main branch pushes:** Same CI workflow validates the merge
3. Check build status on GitHub Actions page
4. If build fails, review test logs and coverage report

### Release New Version

1. Ensure code is merged to main/master branch
2. Update version in `pyproject.toml`
3. Update `CHANGELOG.md`
4. Create and push version tag:
   ```bash
   git tag v0.1.0
   git push origin v0.1.0
   ```
5. Release workflow runs automatically and creates GitHub Release

### Local Development

```bash
# Install in development mode
make install

# Run tests
make test

# Run tests with coverage
make test-cov

# Build wheel
make build

# Clean build artifacts
make clean

# Full pipeline: install + test + build
make all
```

## Build Environment

- **Operating System:** Ubuntu Latest
- **Python Versions:** 3.9, 3.10, 3.11, 3.12, 3.13
- **Package Manager:** pip
- **Cache:** pip dependency cache enabled (keyed on pyproject.toml)

## Troubleshooting

### Common Issues

1. **Test Failures:**
   - Check specific test error messages in the Actions log
   - Run `make test` locally to reproduce
   - Verify Python version compatibility

2. **Build Failures:**
   - Ensure `hatchling` build backend is properly configured in `pyproject.toml`
   - Check for missing dependencies in `[project.optional-dependencies]`

3. **Release Failures:**
   - Ensure tag format matches `v*` pattern
   - Check GitHub Token permissions
   - Verify version in `pyproject.toml` matches the tag

### Local Testing Before Push

```bash
# Validate the package builds correctly
make clean && make all

# Check import works
python -c "import chaosblade; print(chaosblade.__version__)"

# Run specific tests
pytest tests/test_specific.py -v
```

## Configuration

### Environment Variables

- `GITHUB_TOKEN`: Automatically provided for GitHub API access (release creation, artifact upload)

### Cache Configuration

- pip dependency cache enabled for faster subsequent builds
- Cache key based on `pyproject.toml` content hash
- Falls back to OS-level pip cache prefix on miss

### Matrix Strategy

CI workflow uses matrix strategy to test across Python 3.9-3.13 simultaneously, ensuring broad compatibility.
