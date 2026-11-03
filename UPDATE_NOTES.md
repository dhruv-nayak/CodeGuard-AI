# CodeGuard AI — Updated ZIP Notes

## Included updates
- Applied line wrapping to the remaining long Python lines identified in the supplied Ruff output.
- Preserved string contents and application behavior by using adjacent Python string literals / parenthesized expressions.
- Removed the temporary `show_ruff_context.py` diagnostic helper.
- Kept the project's application source, tests, documentation, workflows, and deployment files.

## Local checks performed during packaging
- Python AST parsing: passed for all Python source files.
- Python compileall: exited successfully for `app`, `tests`, and `alembic`.
- Remaining Python source lines over 100 characters: none found by a local line-length scan.

## Checks not performed
- Ruff itself could not be executed in the packaging environment, so a fresh `ruff check` result is not claimed.
- Pytest was not run in the packaging environment. Install the development dependencies and run the suite locally.

## Run checks on Windows PowerShell
```powershell
python -m pip install -r requirements-dev.txt
python -m ruff check app tests alembic
python -m ruff format --check app tests alembic
python -m pytest -q
```

## Security and packaging hygiene
- The uploaded archive contained a `.env` file and a `.git` directory. Both are intentionally excluded from this clean ZIP.
- `.env.example` and `.env.production.example` are retained.
- No local Git history is included. Extract this ZIP into a new folder or copy the files into your existing working repository after backing it up.
- If the `.env` file contained real credentials and was ever committed or pushed, rotate those credentials.
