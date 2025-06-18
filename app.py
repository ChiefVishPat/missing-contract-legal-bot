import asyncio
import os

import aiohttp
from dotenv import load_dotenv
from openai import AsyncOpenAI, OpenAIError
from slack_bolt.adapter.socket_mode.aiohttp import AsyncSocketModeHandler
from slack_bolt.async_app import AsyncApp

import file_utils

load_dotenv()

# Validate required environment variables up-front
required_env_vars = [
    "SLACK_APP_TOKEN",
    "SLACK_BOT_TOKEN",
    "SLACK_SIGNING_SECRET",
    "OPENAI_API_KEY",
    "GITHUB_TOKEN",
    "GITHUB_REPO",
]
missing = [var for var in required_env_vars if not os.getenv(var)]
if missing:
    raise RuntimeError(f"Missing required environment variables: {', '.join(missing)}")

# Initialize Slack app
app = AsyncApp(
    token=os.getenv("SLACK_BOT_TOKEN"),
    signing_secret=os.getenv("SLACK_SIGNING_SECRET"),
)


async def create_github_issue(title: str, body: str) -> dict:
    """
    Create a GitHub issue in the repo specified by GITHUB_REPO.
    Returns the parsed JSON response.
    """
    repo: str = os.getenv("GITHUB_REPO", "")
    token: str = os.getenv("GITHUB_TOKEN", "")
    url = f"https://api.github.com/repos/{repo}/issues"
    headers = {
        "Authorization": f"token {token}",
        "Accept": "application/vnd.github.v3+json",
    }
    payload = {"title": title, "body": body}

    async with aiohttp.ClientSession() as session:
        resp = await session.post(url, json=payload, headers=headers)
        data = await resp.json()
        if resp.status != 201:
            raise RuntimeError(f"GitHub issue creation failed [{resp.status}]: {data}")
        return data


async def summarize_contract(text: str) -> str:
    """
    Send contract text to OpenAI and return a concise summary.
    """
    client = AsyncOpenAI(api_key=os.getenv("OPENAI_API_KEY"))
    # Use GPT-4.1 nano model for summarization
    response = await client.responses.create(
        model="gpt-4.1-nano",
        input=[
            {
                "role": "system",
                "content": "You are a top-notch, reliable, legal assistant.",
            },
            {"role": "user", "content": f"Summarize the key points:\n\n{text}"},
        ],
    )
    return response.output_text.strip()


# Constants
MAX_BLOCK_CHARS = 3000
SUMMARY_HEADER = "*Contract Summary:*\n"


def build_summary_blocks(summary: str) -> list[dict]:
    """
    Split the summary into Slack-safe section blocks, each <= MAX_BLOCK_CHARS
    including the SUMMARY_HEADER on the first block.
    """
    blocks = []

    # 1) First block gets the header + as much text as fits
    first_chunk = summary[: MAX_BLOCK_CHARS - len(SUMMARY_HEADER)]
    blocks.append(
        {
            "type": "section",
            "text": {"type": "mrkdwn", "text": SUMMARY_HEADER + first_chunk},
        }
    )

    # 2) Remaining text in MAX_BLOCK_CHARS slices
    rest = summary[len(first_chunk) :]
    for i in range(0, len(rest), MAX_BLOCK_CHARS):
        chunk = rest[i : i + MAX_BLOCK_CHARS]
        blocks.append({"type": "section", "text": {"type": "mrkdwn", "text": chunk}})

    return blocks


@app.event("app_mention")
async def handle_review(event, say):
    """
    On @mention with 'please review' and an attached file:
    - Download the contract
    - Extract its text
    - Summarize via OpenAI
    - Post the summary in multiple section blocks
    - Create a GitHub issue with the summary
    """
    text = event.get("text", "")
    files = event.get("files")

    if "please review" not in text.lower() or not files:
        await say(
            "⚠️ Please mention me with `please review` and attach a contract file."
        )
        return

    file_info = files[0]
    file_url = file_info.get("url_private_download")
    headers = {"Authorization": f"Bearer {os.getenv('SLACK_BOT_TOKEN', '')}"}

    # Download contract bytes
    async with aiohttp.ClientSession(headers=headers) as session:
        resp = await session.get(file_url)
        if resp.status != 200:
            return await say(f"⚠️ Failed to download file (status {resp.status})")
        raw_bytes = await resp.read()

        # Convert bytes -> text, via the utlity file
        try:
            contract_text = await asyncio.to_thread(
                file_utils.extract_text_from_bytes,
                raw_bytes,
                file_info.get("mimetype"),
            )
        except ValueError:
            return await say(f"⚠️ Unsupported file type `{file_info.get('mimetype')}`.")
        except RuntimeError as e:
            return await say(f"⚠️ Error processing file: {e}")

    # Summarize via OpenAI
    try:
        summary = await summarize_contract(contract_text)
    except OpenAIError as e:
        await say(f"❌ OpenAI API error: {e}")
        return

    blocks = build_summary_blocks(summary=summary)
    await say(text=summary[:3000], blocks=blocks)

    # Create GitHub issue
    try:
        issue = await create_github_issue(
            title=f"Review Contract: {file_info.get('name', 'contract')}",
            body=(
                f"**Summary**:\n{summary}\n\n"
                f"**Original file**: {file_info.get('permalink')}"
            ),
        )
    except RuntimeError as e:
        await say(f"❌ Failed to create GitHub issue: {e}")
        return
    issue_url = issue.get("html_url")
    if issue_url:
        await say(f"✅ Created GitHub issue: {issue_url}")


async def main():
    handler = AsyncSocketModeHandler(app, os.getenv("SLACK_APP_TOKEN"))
    await handler.start_async()


if __name__ == "__main__":
    asyncio.run(main())
