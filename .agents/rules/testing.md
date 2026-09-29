# Testing Guidelines for Ugrator

## Purpose
This workspace maintains a centralized unit test suite in the `tests/` directory to ensure reliability and prevent regressions across all core migration, parsing, mapping, and automation modules.

## Test Discovery & Execution Command
Always run the full test suite from the repository root:
```bash
python -m unittest discover tests
```

To run a single test module:
```bash
python -m unittest tests.test_auth
python -m unittest tests.test_voice
python -m unittest tests.test_assign
```

## Developer & Agent Rules
1. **Mandatory Verification**: Before completing any task or pushing changes to `core/`, run `python -m unittest discover tests` and verify all tests pass.
2. **Add Tests for New Core Features & Fixes**:
   - `core/auth.py` changes &rarr; add test cases to `tests/test_auth.py`
   - `core/voice.py` changes (naming rules, URL normalization) &rarr; add test cases to `tests/test_voice.py`
   - `core/assign.py` changes &rarr; add test cases to `tests/test_assign.py`
   - `core/fields.py` / `core/templates.py` changes &rarr; add test cases to `tests/test_fields.py`
3. **Keep Tests Clean**: Do not create temporary `test_*.py` scratch scripts in the workspace root. Always add test cases directly into the structured `tests/` suite.
