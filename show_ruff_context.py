
import json
import subprocess
from pathlib import Path

result = subprocess.run(
    [
        "python", "-m", "ruff", "check",
        "app", "tests", "alembic",
        "--output-format=json"
    ],
    capture_output=True,
    text=True
)

issues = json.loads(result.stdout)

for issue in issues:
    path = Path(issue["filename"])
    line_no = issue["location"]["row"]

    lines = path.read_text(encoding="utf-8").splitlines()

    print(f"\n{'=' * 75}")
    print(f"{path}:{line_no} [{issue['code']}]")
    print(f"{issue['message']}")

    start = max(0, line_no - 3)
    end = min(len(lines), line_no + 2)

    for i in range(start, end):
        print(f"{i + 1:4}: {lines[i]}")
