# Pre-commit Hooks - PEP8 Enforcement

This project uses pre-commit hooks to enforce code quality and PEP8 standards.

## Quick Start

```bash
# Install pre-commit and dependencies
pip install -r anidb-service/requirements-dev.txt

# Install git hooks
pre-commit install

# Run manually on all files
pre-commit run --all-files
```

## What Gets Checked

### 1. **Black** - Code Formatting
- Automatically formats Python code
- Line length: 100 characters
- Compatible with PEP8

### 2. **isort** - Import Sorting
- Organizes imports alphabetically
- Groups imports by category
- Compatible with Black

### 3. **flake8** - PEP8 Linting
- Checks for PEP8 violations
- Includes docstring checks
- Detects common bugs

### 4. **Pre-commit Hooks** - File Checks
- Removes trailing whitespace
- Fixes end-of-file
- Validates YAML, JSON, TOML
- Checks for merge conflicts
- Prevents large files

### 5. **Bandit** - Security Scanning
- Finds common security issues
- Excludes test files

### 6. **mypy** - Type Checking
- Static type checking
- Catches type errors early

## Configuration Files

- `.pre-commit-config.yaml` - Hook configuration
- `pyproject.toml` - Tool settings (black, isort, bandit, mypy)
- `.flake8` - Flake8 specific settings
- `requirements-dev.txt` - Development dependencies

## Usage

### Automatic (on git commit)
Hooks run automatically when you commit:
```bash
git add .
git commit -m "Your message"
# Hooks run automatically and may modify files
```

### Manual Run
```bash
# Run on all files
pre-commit run --all-files

# Run specific hook
pre-commit run black --all-files
pre-commit run flake8 --all-files

# Skip hooks for emergency commits
git commit --no-verify -m "Emergency fix"
```

### Update Hooks
```bash
pre-commit autoupdate
```

## Common Issues

### Line Too Long
Black formats to 100 chars. If flake8 complains, Black should fix it:
```bash
black your_file.py
```

### Import Order
Let isort fix import ordering:
```bash
isort your_file.py
```

### Flake8 Errors
View specific error codes at: https://www.flake8rules.com/

## IDE Integration

### VS Code
Install extensions:
- Python (Microsoft)
- Black Formatter
- Flake8
- isort

Add to `.vscode/settings.json`:
```json
{
  "python.formatting.provider": "black",
  "python.linting.flake8Enabled": true,
  "editor.formatOnSave": true,
  "[python]": {
    "editor.codeActionsOnSave": {
      "source.organizeImports": true
    }
  }
}
```

### PyCharm
- Settings → Tools → Black
- Settings → Tools → External Tools → Add flake8
- Enable "Reformat code" on commit
