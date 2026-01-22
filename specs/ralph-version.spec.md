# Ralph Version

Users should be able to check which version of Ralph is installed.

## Goal

`ralph --version` displays the current version number.

## Success Criteria

- [ ] `ralph --version` outputs the version (e.g., "ralph 0.3.0" or similar)
- [ ] Version matches `__version__` in `src/ralph/__init__.py`
- [ ] Test coverage ensures this keeps working correctly
- [ ] Documented in README.md and relevant docs where version checking is useful
