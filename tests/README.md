# Ugrator Test Suite

This directory contains automated unit tests for all core business logic and transformation engines in `Ugrator`.

## Test Modules
- `test_auth.py`: Tests PowerShell script parsing, cookie extraction, x-csrf-token extraction, and JSON body payload parsing.
- `test_voice.py`: Tests URL normalization for arbitrary user paths, voice naming rules, and directory audio scanning.
- `test_assign.py`: Tests agent and group mapping extractions and CSV assignment parsing.

## Running Tests
Run the entire suite from the workspace root:
```bash
python -m unittest discover tests
```

Run a specific test module:
```bash
python -m unittest tests.test_voice
```
