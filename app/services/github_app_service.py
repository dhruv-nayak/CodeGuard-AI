import os
import time
import httpx
import jwt


GITHUB_API = "https://api.github.com"


def _app_credentials() -> tuple[str, str]:
    app_id = os.getenv("GITHUB_APP_ID", "").strip()
    private_key = os.getenv("GITHUB_APP_PRIVATE_KEY", "").replace("\\n", "\n")
    if not app_id or not private_key:
        raise ValueError("GitHub App is not configured. Set GITHUB_APP_ID and GITHUB_APP_PRIVATE_KEY.")
    return app_id, private_key


def create_app_jwt() -> str:
    app_id, private_key = _app_credentials()
    now = int(time.time())
    return jwt.encode(
        {"iat": now - 30, "exp": now + 8 * 60, "iss": app_id},
        private_key,
        algorithm="RS256",
    )


async def create_installation_token(installation_id: int) -> dict:
    if installation_id < 1:
        raise ValueError("A valid GitHub App installation ID is required.")
    app_jwt = create_app_jwt()
    url = f"{GITHUB_API}/app/installations/{installation_id}/access_tokens"
    async with httpx.AsyncClient(timeout=httpx.Timeout(20.0, connect=10.0)) as client:
        response = await client.post(
            url,
            headers={
                "Authorization": f"Bearer {app_jwt}",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
    if response.status_code in (401, 403):
        raise ValueError("GitHub App authentication failed. Verify the App ID, private key and installation.")
    if response.status_code == 404:
        raise ValueError("GitHub App installation was not found or is not accessible.")
    response.raise_for_status()
    data = response.json()
    if not data.get("token"):
        raise ValueError("GitHub did not return an installation access token.")
    return {"token": data["token"], "expires_at": data.get("expires_at")}


def github_app_configured() -> bool:
    return bool(os.getenv("GITHUB_APP_ID", "").strip() and os.getenv("GITHUB_APP_PRIVATE_KEY", "").strip())
