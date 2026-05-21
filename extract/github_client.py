import calendar
import os
import time

import httpx
from dotenv import load_dotenv

load_dotenv()

GITHUB_GRAPHQL_URL = "https://api.github.com/graphql"
RATE_LIMIT_BUFFER = 100  # pause when fewer than this many points remain


class GitHubClient:
    def __init__(self):
        """Initialize the authenticated httpx client."""
        token = os.getenv("GITHUB_TOKEN")
        if not token:
            raise ValueError("GITHUB_TOKEN is not set in .env")

        self._client = httpx.Client(
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            }
        )

    def execute(self, query: str, variables: dict) -> dict:
        """
        Send a GraphQL query to the GitHub API and return the response data.

        Raises on HTTP errors or GraphQL-level errors in the response.
        Always includes rateLimit in the response — call _handle_rate_limit after.
        """
        try:
            response = self._client.post(
                GITHUB_GRAPHQL_URL, json={"query": query, "variables": variables}
            )
            
            response.raise_for_status()
            data = response.json()

            if "errors" in data:
                print("GraphQL errors in response:", data["errors"])
                raise Exception("GraphQL errors: " + str(data["errors"]))

            self._handle_rate_limit(data.get("data", {}).get("rateLimit", {}))
            return data.get("data", {})
        except httpx.HTTPError as e:
            print("HTTP error during GitHub GraphQL API request:", e)
            raise e

    def _handle_rate_limit(self, data: dict) -> None:
        """
        Inspect the rateLimit field from a GraphQL response.

        If remaining points are below RATE_LIMIT_BUFFER, sleep until resetAt.
        """
        remaining = data.get("remaining", 0)
        reset_at = data.get("resetAt")
        if remaining < RATE_LIMIT_BUFFER and reset_at:
            reset_time = time.strptime(reset_at, "%Y-%m-%dT%H:%M:%SZ")
            reset_timestamp = calendar.timegm(reset_time)
            sleep_seconds = max(0, reset_timestamp - time.time())
            print(
                f"Rate limit low ({remaining} points remaining). "
                f"Sleeping for {sleep_seconds:.2f} seconds until reset at {reset_at}."
            )
            time.sleep(sleep_seconds)

    def close(self) -> None:
        """Close the authenticated httpx client."""
        self._client.close()
