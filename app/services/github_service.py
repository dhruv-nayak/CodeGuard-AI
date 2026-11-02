import base64
import re
from urllib.parse import quote

import httpx

from app.services.analyzer import analyze_python
from app.services.ai_providers import get_hybrid_review

GITHUB_API = "https://api.github.com"
MAX_FILES = 30
MAX_FILE_BYTES = 250_000
PYTHON_EXTENSIONS = (".py",)

def changed_line_numbers(patch: str | None) -> set[int]:
    """Return new-file line numbers represented by added lines in a unified diff."""
    if not patch:
        return set()
    changed = set()
    new_line = 0
    for line in patch.splitlines():
        if line.startswith("@@"):
            match = re.search(r"\+(\d+)(?:,(\d+))?", line)
            if match:
                new_line = int(match.group(1))
        elif line.startswith("+++"):
            continue
        elif line.startswith("+"):
            changed.add(new_line)
            new_line += 1
        elif line.startswith("-"):
            continue
        elif line.startswith("\\"):
            continue
        else:
            new_line += 1
    return changed

async def _github_get(client: httpx.AsyncClient, url: str, token: str, accept: str = "application/vnd.github+json"):
    response = await client.get(
        url,
        headers={
            "Authorization": f"Bearer {token}",
            "Accept": accept,
            "X-GitHub-Api-Version": "2022-11-28",
        },
    )
    if response.status_code == 401:
        raise ValueError("GitHub authentication failed. Check the token and its permissions.")
    if response.status_code == 403:
        raise ValueError("GitHub denied the request. Check token permissions and API rate limits.")
    if response.status_code == 404:
        raise ValueError("Repository or pull request was not found, or the token cannot access it.")
    response.raise_for_status()
    return response

async def review_pull_request(owner: str, repo: str, pull_number: int, token: str, ai_provider: str = "auto") -> dict:
    if not token.strip():
        raise ValueError("A GitHub token is required.")

    safe_owner = quote(owner, safe="")
    safe_repo = quote(repo, safe="")
    base = f"{GITHUB_API}/repos/{safe_owner}/{safe_repo}"

    timeout = httpx.Timeout(30.0, connect=10.0)
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=False) as client:
        pr_response = await _github_get(client, f"{base}/pulls/{pull_number}", token)
        pr = pr_response.json()

        if pr.get("state") != "open":
            # Closed PRs can still be inspected; report state in summary only.
            pass

        files_response = await _github_get(
            client, f"{base}/pulls/{pull_number}/files?per_page={MAX_FILES}", token
        )
        files = files_response.json()
        if not isinstance(files, list):
            raise ValueError("GitHub returned an unexpected pull-request files response.")

        results = []
        skipped = 0
        total_findings = 0
        ai_summaries = []
        head_sha = pr.get("head", {}).get("sha", "")

        for item in files[:MAX_FILES]:
            filename = item.get("filename", "")
            status = item.get("status", "unknown")
            if not filename.endswith(PYTHON_EXTENSIONS) or status == "removed":
                skipped += 1
                continue

            # Fetch exact file content at PR head; never execute repository code.
            contents_url = f"{base}/contents/{quote(filename, safe='/')}?ref={quote(head_sha, safe='')}"
            try:
                content_response = await _github_get(client, contents_url, token)
                content_obj = content_response.json()
                if content_obj.get("encoding") != "base64":
                    skipped += 1
                    continue
                raw = base64.b64decode(content_obj.get("content", ""))
                if len(raw) > MAX_FILE_BYTES:
                    skipped += 1
                    continue
                source = raw.decode("utf-8")
            except (UnicodeDecodeError, ValueError, httpx.HTTPStatusError):
                skipped += 1
                continue

            findings = analyze_python(source)
            patch_lines = changed_line_numbers(item.get("patch"))
            # Keep findings that intersect changed lines; if GitHub omits the patch,
            # retain findings but clearly note that changed-line filtering was unavailable.
            if patch_lines:
                findings = [f for f in findings if f.line in patch_lines]
            serialised = [f.model_dump() for f in findings]
            total_findings += len(serialised)

            results.append({
                "filename": filename,
                "status": status,
                "additions": item.get("additions", 0),
                "deletions": item.get("deletions", 0),
                "findings": serialised,
            })

            # One optional AI review per file, bounded to avoid excessive API usage.
            if len(ai_summaries) < 5 and source.strip():
                ai_data, provider, _errors = await get_hybrid_review(filename, source[:50000], ai_provider)
                if ai_data:
                    ai_summaries.append({
                        "file": filename,
                        "provider": provider,
                        "summary": str(ai_data.get("summary", ""))[:1200],
                        "findings": ai_data.get("findings", [])[:10],
                    })

    return {
        "repository": f"{owner}/{repo}",
        "pull_number": pull_number,
        "pull_title": pr.get("title", ""),
        "pull_url": pr.get("html_url", ""),
        "head_sha": head_sha,
        "files_reviewed": len(results),
        "files_skipped": skipped,
        "findings_count": total_findings,
        "file_results": results,
        "ai_summary": "\n\n".join(
            f"{x['file']} ({x['provider']}): {x['summary']}" for x in ai_summaries
        ) or None,
        "ai_provider": ", ".join(sorted({x["provider"] for x in ai_summaries})) or None,
        "limitations": [
            "This integration is read-only: it does not post comments, approve, merge or modify pull requests.",
            "Only Python files are analysed in this version; removed, binary, oversized and unsupported files are skipped.",
            "Repository source is fetched at the pull request head and is never executed.",
            "Static findings are filtered to changed lines when GitHub provides a patch; files without patch data may not have changed-line filtering.",
            "AI review is advisory and may send source code to the selected external provider. Use only repositories permitted by your organisation.",
            "The GitHub token is used for this request only and is not stored by CodeGuard.",
        ],
    }
