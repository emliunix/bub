# System F Cleanup Specification

## Entry Point Design Decision

**Decision**: Delete `main.py`, keep `demo.py` as a standalone educational script

**Rationale**:
- `main.py` is a 6-line placeholder with zero functionality - it serves no purpose
- `demo.py` contains 221 lines of valuable educational content demonstrating all System F features
- The demo showcases: data types, polymorphism, type application, pattern matching, higher-order functions
- The README already documents the proper CLI entry points (`python -m systemf check/run/repl`)
- demo.py can be run successfully with `uv run --pythonpath=src demo.py` after the package is properly importable
- Keeping demo.py in the root makes it discoverable for users exploring the project
- Deleting rather than consolidating avoids maintaining two files with different purposes

**Implementation Details**:
1. Delete `main.py` entirely
2. Keep `demo.py` in project root as educational material
3. Optionally add a shebang and execution instructions to demo.py
4. No changes needed to pyproject.toml (no console_scripts entry points required)
5. The existing `python -m systemf` CLI (documented in README) remains the primary entry point

**Alternative Considered**:
- Converting demo.py to a CLI subcommand was rejected because:
  - It would require modifying pyproject.toml and package structure
  - The demo is primarily educational, not a tool
  - Keeping it as a standalone script maintains simplicity

## .gitignore Specification

```gitignore
# Python
__pycache__/
*.py[cod]
*$py.class
*.so
.Python
build/
develop-eggs/
dist/
downloads/
eggs/
.eggs/
lib/
lib64/
parts/
sdist/
var/
wheels/
share/python-wheels/
*.egg-info/
.installed.cfg
*.egg
MANIFEST

# PyInstaller
*.manifest
*.spec

# Installer logs
pip-log.txt
pip-delete-this-directory.txt

# Unit test / coverage reports
htmlcov/
.tox/
.nox/
.coverage
.coverage.*
.cache
nosetests.xml
coverage.xml
*.cover
*.py,cover
.hypothesis/
.pytest_cache/
cover/

# Translations
*.mo
*.pot

# Django stuff:
*.log
local_settings.py
db.sqlite3
db.sqlite3-journal

# Flask stuff:
instance/
.webassets-cache

# Scrapy stuff:
.scrapy

# Sphinx documentation
docs/_build/

# PyBuilder
.pybuilder/
target/

# Jupyter Notebook
.ipynb_checkpoints

# IPython
profile_default/
ipython_config.py

# pyenv
.python-version

# pipenv
Pipfile.lock

# poetry
poetry.lock

# pdm
.pdm.toml

# PEP 582
__pypackages__/

# Celery stuff
celerybeat-schedule
celerybeat.pid

# SageMath parsed files
*.sage.py

# Environments
.env
.venv
env/
venv/
ENV/
env.bak/
venv.bak/

# Spyder project settings
.spyderproject
.spyproject

# Rope project settings
.ropeproject

# mkdocs documentation
/site

# mypy
.mypy_cache/
.dmypy.json
dmypy.json

# Pyre type checker
.pyre/

# pytype static type analyzer
.pytype/

# Cython debug symbols
cython_debug/

# PyCharm
.idea/

# VS Code
.vscode/

# Ruff
.ruff_cache/

# System F specific
src/systemf.egg-info/
```

## Cleanup Commands Specification

### Cache Directories
```bash
# Remove tool cache directories
rm -rf .mypy_cache
rm -rf .ruff_cache
rm -rf .pytest_cache
```

### Python Cache
```bash
# Remove all __pycache__ directories recursively
find . -type d -name "__pycache__" -exec rm -rf {} +

# Alternative: also remove .pyc files
find . -name "*.pyc" -delete
find . -name "*.pyo" -delete
```

### Build Artifacts
```bash
# Remove egg-info directory
rm -rf src/systemf.egg-info

# Remove any other build artifacts
rm -rf build/
rm -rf dist/
rm -rf *.egg-info
```

### Complete Cleanup Script (for reference)
```bash
#!/bin/bash
# Complete cleanup of systemf project

# Remove cache directories
rm -rf .mypy_cache .ruff_cache .pytest_cache

# Remove all __pycache__ directories
find . -type d -name "__pycache__" -exec rm -rf {} + 2>/dev/null

# Remove build artifacts
rm -rf src/systemf.egg-info build/ dist/

echo "Cleanup complete!"
```

## Files to Create
1. `.gitignore` - Root gitignore file with Python standard patterns

## Files to Modify
None - No modifications needed to existing files

## Files to Delete
1. `main.py` - 6-line placeholder with no functionality

## Verification Checklist
- [ ] .gitignore created with all standard Python patterns
- [ ] main.py deleted
- [ ] .mypy_cache removed
- [ ] .ruff_cache removed
- [ ] .pytest_cache removed
- [ ] All 9 __pycache__ directories removed
- [ ] src/systemf.egg-info/ removed
- [ ] No other files modified or deleted

## Notes for Implementor

1. **Order of operations matters**: Create .gitignore first, then delete caches
2. **demo.py should remain**: It's educational content, not cleanup target
3. **Use find carefully**: The find command for __pycache__ may need `2>/dev/null` to suppress errors about directories already removed
4. **Verify counts**: There should be 9 __pycache__ directories to remove
5. **Double-check before deleting**: Ensure main.py is the 6-line placeholder before deletion
