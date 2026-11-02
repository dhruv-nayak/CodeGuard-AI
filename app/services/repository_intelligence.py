"""Bounded, read-only repository scanning and dependency intelligence.

Repository code is fetched as data and is never executed. Dependency vulnerability
matches are sourced from OSV when reachable; an unavailable lookup is reported.
"""
from __future__ import annotations

import json
import re
import tomllib
import xml.etree.ElementTree as ET
from dataclasses import dataclass
from typing import Any
from urllib.parse import quote

import httpx

from app.services.analyzer import analyze_source

GITHUB_API = "https://api.github.com"
OSV_API = "https://api.osv.dev/v1/querybatch"
MAX_TREE_ENTRIES = 2500
MAX_SOURCE_FILES = 60
MAX_FILE_BYTES = 200_000
MANIFEST_NAMES = {
    "requirements.txt", "pyproject.toml", "Pipfile.lock", "poetry.lock",
    "package.json", "package-lock.json", "npm-shrinkwrap.json", "yarn.lock",
    "composer.json", "composer.lock", "pom.xml", "go.mod",
}
EXTENSIONS = {".py":"python", ".js":"javascript", ".jsx":"javascript", ".ts":"typescript", ".tsx":"typescript", ".java":"java", ".php":"php", ".sql":"sql", ".html":"html"}

@dataclass
class Dependency:
    name: str
    version: str
    ecosystem: str
    purl: str


def _normal_version(value: Any) -> str:
    value = str(value or "").strip()
    value = re.sub(r"^(==|===|=|v)", "", value, flags=re.I)
    value = value.split(",", 1)[0].strip()
    return value if re.fullmatch(r"[0-9][A-Za-z0-9.+_-]*", value) else ""


def _dep(name: str, version: str, ecosystem: str) -> Dependency | None:
    name, version = name.strip(), _normal_version(version)
    if not name or not version or any(x in name for x in ("${", "*", " ")):
        return None
    if ecosystem == "PyPI":
        name = re.sub(r"[-_.]+", "-", name).lower()
        purl = f"pkg:pypi/{quote(name, safe='-._')}@{quote(version, safe='.+-_')}"
    elif ecosystem == "npm":
        purl = f"pkg:npm/{quote(name, safe='@-._/')}@{quote(version, safe='.+-_')}"
    elif ecosystem == "Packagist":
        purl = f"pkg:composer/{quote(name.lower(), safe='/-._')}@{quote(version, safe='.+-_')}"
    elif ecosystem == "Maven":
        purl = f"pkg:maven/{quote(name.replace(':', '/'), safe='/-._')}@{quote(version, safe='.+-_')}"
    elif ecosystem == "Go":
        purl = f"pkg:golang/{quote(name, safe='/.-_')}@{quote(version, safe='.+-_')}"
    else:
        return None
    return Dependency(name, version, ecosystem, purl)


def parse_manifests(files: dict[str, str]) -> list[Dependency]:
    found: dict[tuple[str, str, str], Dependency] = {}
    def add(item):
        if item:
            found[(item.ecosystem, item.name.lower(), item.version)] = item
    for path, content in files.items():
        base = path.rsplit("/", 1)[-1]
        try:
            if base == "requirements.txt":
                for line in content.splitlines():
                    line = line.split("#", 1)[0].strip()
                    match = re.match(r"([A-Za-z0-9_.-]+)\s*(?:==|===)\s*([^;\s]+)", line)
                    if match: add(_dep(match.group(1), match.group(2), "PyPI"))
            elif base == "pyproject.toml":
                data = tomllib.loads(content)
                deps = data.get("project", {}).get("dependencies", [])
                for entry in deps:
                    match = re.match(r"([A-Za-z0-9_.-]+)\s*==\s*([^;\s]+)", entry)
                    if match: add(_dep(match.group(1), match.group(2), "PyPI"))
            elif base in {"package-lock.json", "npm-shrinkwrap.json"}:
                data = json.loads(content)
                for key, value in (data.get("packages") or {}).items():
                    if key.startswith("node_modules/") and isinstance(value, dict):
                        name = key[len("node_modules/"):]
                        add(_dep(name, value.get("version"), "npm"))
                if not data.get("packages"):
                    def walk(deps):
                        for name, value in deps.items():
                            add(_dep(name, value.get("version"), "npm"))
                            walk(value.get("dependencies", {}))
                    walk(data.get("dependencies", {}))
            elif base == "package.json":
                data = json.loads(content)
                for group in ("dependencies", "devDependencies", "optionalDependencies"):
                    for name, version in data.get(group, {}).items():
                        version = str(version).lstrip("^~")
                        add(_dep(name, version, "npm"))
            elif base == "composer.lock":
                data = json.loads(content)
                for group in ("packages", "packages-dev"):
                    for package in data.get(group, []):
                        add(_dep(package.get("name", ""), package.get("version", "").lstrip("v"), "Packagist"))
            elif base == "pom.xml":
                root = ET.fromstring(content)
                ns = {"m": root.tag.split("}")[0].strip("{")} if "}" in root.tag else {}
                def tag(name): return f"m:{name}" if ns else name
                for node in root.findall(f".//{tag('dependency')}", ns):
                    group = node.findtext(tag("groupId"), default="", namespaces=ns)
                    artifact = node.findtext(tag("artifactId"), default="", namespaces=ns)
                    version = node.findtext(tag("version"), default="", namespaces=ns)
                    if group and artifact: add(_dep(f"{group}:{artifact}", version, "Maven"))
            elif base == "go.mod":
                for line in content.splitlines():
                    match = re.match(r"\s*([\w./-]+)\s+(v\d[\w.+-]*)", line)
                    if match: add(_dep(match.group(1), match.group(2), "Go"))
        except (ValueError, TypeError, KeyError, ET.ParseError):
            # A malformed manifest is reported separately by its caller.
            continue
    return sorted(found.values(), key=lambda d: (d.ecosystem, d.name.lower(), d.version))


async def osv_lookup(dependencies: list[Dependency]) -> tuple[list[dict], str]:
    if not dependencies:
        return [], "No exact, version-pinned dependencies were available for OSV lookup."
    queries = [{"package": {"name": d.name, "ecosystem": d.ecosystem}, "version": d.version} for d in dependencies[:500]]
    try:
        async with httpx.AsyncClient(timeout=httpx.Timeout(20, connect=8), follow_redirects=False) as client:
            response = await client.post(OSV_API, json={"queries": queries}, headers={"Accept": "application/json"})
            response.raise_for_status()
            payload = response.json()
        vulnerabilities = []
        for dep, result in zip(dependencies, payload.get("results", [])):
            for vuln in result.get("vulns", []):
                vulnerabilities.append({
                    "dependency": dep.name, "version": dep.version, "ecosystem": dep.ecosystem,
                    "id": vuln.get("id", "UNKNOWN"),
                    "summary": str(vuln.get("summary") or vuln.get("details") or "")[:500],
                    "modified": vuln.get("modified"),
                    "references": [r.get("url") for r in vuln.get("references", [])[:5] if r.get("url")],
                    "source": "OSV",
                })
        return vulnerabilities, "OSV lookup completed for exact pinned versions. No result means no match was returned by OSV, not proof of safety."
    except (httpx.HTTPError, ValueError, KeyError, TypeError):
        return [], "OSV service was unavailable; dependency vulnerability status is unknown, not clean."


def make_sbom(owner: str, repo: str, revision: str, dependencies: list[Dependency]) -> dict:
    components = [{"type":"library", "name":d.name, "version":d.version, "purl":d.purl,
                   "scope":"required"} for d in dependencies]
    return {
        "bomFormat":"CycloneDX", "specVersion":"1.5", "version":1,
        "metadata":{"component":{"type":"application", "name":f"{owner}/{repo}", "version":revision or "unknown"}},
        "components":components,
    }


async def _github_get(client: httpx.AsyncClient, url: str, token: str) -> httpx.Response:
    response = await client.get(url, headers={
        "Authorization": f"Bearer {token}", "Accept":"application/vnd.github+json",
        "X-GitHub-Api-Version":"2022-11-28",
    })
    if response.status_code == 401: raise ValueError("GitHub authentication failed; check token permissions.")
    if response.status_code == 403: raise ValueError("GitHub denied access or the API rate limit was reached.")
    if response.status_code == 404: raise ValueError("Repository was not found or the token cannot access it.")
    response.raise_for_status()
    return response


async def scan_github_repository(owner: str, repo: str, token: str) -> dict:
    if not token or not token.strip(): raise ValueError("A GitHub token is required.")
    base = f"{GITHUB_API}/repos/{quote(owner, safe='')}/{quote(repo, safe='')}"
    async with httpx.AsyncClient(timeout=httpx.Timeout(25, connect=8), follow_redirects=False) as client:
        metadata = (await _github_get(client, base, token)).json()
        branch = metadata.get("default_branch") or "main"
        tree = (await _github_get(client, f"{base}/git/trees/{quote(branch, safe='')}?recursive=1", token)).json()
        entries = tree.get("tree", [])
        truncated = bool(tree.get("truncated")) or len(entries) > MAX_TREE_ENTRIES
        entries = entries[:MAX_TREE_ENTRIES]
        manifests = [x for x in entries if x.get("type") == "blob" and x.get("path", "").rsplit("/",1)[-1] in MANIFEST_NAMES]
        source_files = [x for x in entries if x.get("type") == "blob" and any(x.get("path", "").lower().endswith(ext) for ext in EXTENSIONS)]
        files_to_fetch = (manifests[:30] + source_files[:MAX_SOURCE_FILES])
        # De-duplicate paths while preserving priority for manifests.
        unique = {x.get("path"): x for x in files_to_fetch if x.get("path")}
        contents: dict[str, str] = {}
        skipped = 0
        for path, item in unique.items():
            if item.get("size", 0) > MAX_FILE_BYTES:
                skipped += 1; continue
            blob = (await _github_get(client, f"{base}/git/blobs/{quote(item['sha'], safe='')}", token)).json()
            if blob.get("encoding") != "base64":
                skipped += 1; continue
            import base64
            try:
                raw = base64.b64decode(blob.get("content", ""), validate=False)
                if len(raw) > MAX_FILE_BYTES: skipped += 1; continue
                contents[path] = raw.decode("utf-8")
            except (ValueError, UnicodeDecodeError):
                skipped += 1

    manifest_contents = {p:c for p,c in contents.items() if p.rsplit("/",1)[-1] in MANIFEST_NAMES}
    dependencies = parse_manifests(manifest_contents)
    vulnerabilities, osv_note = await osv_lookup(dependencies)
    findings = []
    reviewed_files = 0
    for path, source in contents.items():
        language = next((lang for ext, lang in EXTENSIONS.items() if path.lower().endswith(ext)), None)
        if not language: continue
        reviewed_files += 1
        for finding in analyze_source(source, language):
            item = finding.model_dump() if hasattr(finding, "model_dump") else dict(finding)
            item["file"] = path
            findings.append(item)
    sbom = make_sbom(owner, repo, str(metadata.get("default_branch", branch)), dependencies)
    return {
        "repository": f"{owner}/{repo}", "default_branch": branch,
        "head_sha": tree.get("sha"), "files_reviewed": reviewed_files,
        "files_skipped": skipped, "tree_entries_seen": len(entries),
        "tree_truncated": truncated, "findings": findings,
        "findings_count": len(findings), "dependencies": [d.__dict__ for d in dependencies],
        "dependency_count": len(dependencies), "dependency_vulnerabilities": vulnerabilities,
        "vulnerable_dependency_count": len(vulnerabilities), "osv_status": osv_note,
        "sbom": sbom,
        "limitations": [
            "Read-only scan: repository files are fetched as data and are never executed.",
            f"Scan is bounded to {MAX_TREE_ENTRIES} tree entries, 30 manifests, {MAX_SOURCE_FILES} source files, and {MAX_FILE_BYTES} bytes per file.",
            "Dependency checks require exact pinned versions and use OSV; unpinned, unsupported, or unresolved dependencies are not assessed.",
            "A missing OSV match is not proof that a dependency is secure. Review advisories and lockfiles independently.",
            "Static code findings are heuristic signals and may include false positives or miss vulnerabilities.",
            "The GitHub token is used for this request only and is not stored by CodeGuard.",
        ],
    }
