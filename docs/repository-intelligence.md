# Phase 8 – Repository Intelligence & DevSecOps

## Capabilities

- Authenticated, read-only GitHub repository scanning using a fine-grained PAT or GitHub App installation token.
- Bounded repository tree traversal and static source checks for supported Python, JavaScript/TypeScript, Java, PHP, SQL and HTML files.
- Dependency extraction from pinned `requirements.txt`, `pyproject.toml` project dependencies, npm lock/package files, Composer lockfiles, Maven `pom.xml`, and `go.mod` declarations.
- Exact-version vulnerability lookup through the OSV query-batch API.
- CycloneDX 1.5 JSON SBOM generation and authenticated download from review history.
- A GitHub Actions workflow for Python dependency auditing/SBOM generation and optional Node audit/SBOM generation.

## API

`POST /api/v1/github/repositories/scan`

```json
{
  "owner": "octocat",
  "repo": "hello-world",
  "github_token": "<request-only-token>"
}
```

Use `installation_id` instead of `github_token` when the GitHub App is configured. The GitHub App installation must have repository Contents: read permission. A fine-grained PAT needs repository Contents: read access. The token is not saved to the database or audit log.

`GET /api/v1/reviews/history/{review_id}/sbom` downloads the saved CycloneDX JSON SBOM. Review ownership is enforced by the existing history service.

## Bounds and safety

- Maximum 2,500 repository tree entries considered.
- Maximum 30 dependency manifests and 60 source files fetched.
- Maximum 200 KB per file.
- No repository code, build scripts, package lifecycle scripts, or tests are executed.
- No dependency is installed as part of a repository scan.
- Static code checks are heuristics, not a full SAST engine.
- OSV lookups are limited to exact version-pinned dependencies supported by OSV ecosystems. Unpinned dependencies and unsupported manifest forms are omitted.
- OSV service errors are reported as unknown status, not as a clean result. No OSV match is not proof of safety.
- The CycloneDX output is generated from successfully parsed manifest declarations; it is not a claim of complete transitive dependency resolution unless the supplied lockfile provides that data.

## GitHub Actions workflow

`.github/workflows/security.yml` runs `pip-audit` and creates a CycloneDX SBOM for `requirements.txt`. If `package-lock.json` exists, a separate Node job runs `npm audit` and `npm sbom`. Artifacts are uploaded for later inspection. The scheduled run is weekly.

## Required GitHub permissions

For a GitHub App installation, grant repository **Contents: read-only**. No write permission is required for repository scanning. For a PAT, grant the minimum repository read access required to read the target repository's tree and blobs.

## Operational note

The repository scan calls GitHub and OSV at request time. External connectivity, credentials, rate limits and provider availability affect results. The automated test suite uses local fixtures for parsing and SBOM behavior; it does not authenticate against a live GitHub repository or assert live OSV results.
