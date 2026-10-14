"""Smoke test: keyless call to your Foundry model deployment.

Run after setup-foundry.ps1 has written .env:
    uv add "azure-ai-projects>=2.3.0" azure-identity
    uv run smoke_test.py

Auth is DefaultAzureCredential: locally it uses your `az login`;
on Azure Container Apps it will use the app's managed identity. No API keys.
"""

import os
from pathlib import Path

from azure.ai.projects import AIProjectClient
from azure.identity import DefaultAzureCredential


def load_env(path: str = ".env") -> None:
    """Tiny .env reader so we don't need python-dotenv."""
    env_file = Path(path)
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8-sig").splitlines():
        line = line.strip()
        if line and not line.startswith("#") and "=" in line:
            key, value = line.split("=", 1)
            os.environ.setdefault(key.strip(), value.strip())


def main() -> None:
    load_env()
    endpoint = os.environ.get("FOUNDRY_PROJECT_ENDPOINT")
    if not endpoint:
        raise SystemExit("FOUNDRY_PROJECT_ENDPOINT not set - run setup-foundry.ps1 first.")
    model = os.environ.get("FOUNDRY_MODEL", "gpt-5-mini")

    project = AIProjectClient(endpoint=endpoint, credential=DefaultAzureCredential())
    openai = project.get_openai_client()

    response = openai.responses.create(
        model=model,
        input=(
            "In two sentences, explain why a football team might concede "
            "more goals from set pieces in away matches."
        ),
    )
    text = (response.output_text or "").strip()
    if not text:
        raise RuntimeError("Model returned an empty response.")
    print(f"[{model}] {text}")


if __name__ == "__main__":
    main()
