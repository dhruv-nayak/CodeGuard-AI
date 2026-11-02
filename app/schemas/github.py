from typing import Literal

from pydantic import BaseModel, Field, model_validator

class GitHubReviewRequest(BaseModel):
    owner: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9-]+$")
    repo: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    pull_number: int = Field(ge=1)
    github_token: str | None = Field(default=None, max_length=500)
    installation_id: int | None = Field(default=None, ge=1)
    ai_provider: Literal["auto", "openai", "gemini", "ollama"] = "auto"

    @model_validator(mode="after")
    def require_auth_method(self):
        if not self.github_token and not self.installation_id:
            raise ValueError("Provide a GitHub token or GitHub App installation ID.")
        return self


class GitHubFileFinding(BaseModel):
    filename: str
    status: str
    additions: int
    deletions: int
    findings: list[dict]

class GitHubReviewResponse(BaseModel):
    review_id: str | None = None
    repository: str
    pull_number: int
    pull_title: str
    pull_url: str
    head_sha: str
    files_reviewed: int
    files_skipped: int
    findings_count: int
    file_results: list[GitHubFileFinding]
    ai_summary: str | None = None
    ai_provider: str | None = None
    limitations: list[str]


class PublishCommentsRequest(BaseModel):
    github_token: str | None = Field(default=None, max_length=500)
    installation_id: int | None = Field(default=None, ge=1)
    confirmation: Literal["PUBLISH_COMMENTS"]

    @model_validator(mode="after")
    def require_auth_method(self):
        if not self.github_token and not self.installation_id:
            raise ValueError("Provide a GitHub token or GitHub App installation ID.")
        return self


class GitHubAppTokenRequest(BaseModel):
    installation_id: int = Field(ge=1)


class RepositoryScanRequest(BaseModel):
    owner: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9-]+$")
    repo: str = Field(min_length=1, max_length=100, pattern=r"^[A-Za-z0-9_.-]+$")
    github_token: str | None = Field(default=None, max_length=500)
    installation_id: int | None = Field(default=None, ge=1)

    @model_validator(mode="after")
    def require_auth_method(self):
        if not self.github_token and not self.installation_id:
            raise ValueError("Provide a GitHub token or GitHub App installation ID.")
        return self
