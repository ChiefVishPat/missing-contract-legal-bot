# isort: skip_file
# flake8: noqa
import os

# Set required env vars before importing app
os.environ.update(
    {
        "SLACK_APP_TOKEN": "xapp-123",
        "SLACK_BOT_TOKEN": "xoxb-456",
        "SLACK_SIGNING_SECRET": "secret",
        "OPENAI_API_KEY": "openai-key",
        "GITHUB_TOKEN": "gh-token",
        "GITHUB_REPO": "owner/repo",
    }
)

import aiohttp  # noqa: E402
import pytest  # noqa: E402

import app  # noqa: E402
from app import create_github_issue  # noqa: E402
from app import build_summary_blocks, handle_review, summarize_contract  # noqa: E402

# --- Helpers for mocking ---


class DummyResp:
    def __init__(self):
        self.output_text = " summarized result "


class DummyClient:
    def __init__(self, api_key=None):
        pass

    @property
    def responses(self):
        class R:
            async def create(self, model, input=None, parameters=None):
                return DummyResp()

        return R()


class DummyResponse:
    def __init__(self, status, data):
        self.status = status
        self._data = data

    async def json(self):
        return self._data

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass


class DummySession:
    def __init__(self, resp):
        self._resp = resp

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def post(self, url, json, headers):
        return self._resp


class DummyGetResp:
    def __init__(self):
        self.status = 200

    async def read(self):
        return b"dummy content"

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass


class DummyGetSession:
    def __init__(self, headers=None):
        pass

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        pass

    async def get(self, url):
        return DummyGetResp()


class DummySay:
    def __init__(self):
        self.messages = []

    async def __call__(self, *args, **kwargs):
        self.messages.append((args, kwargs))


# --- Tests ---


def test_build_summary_blocks_short():
    summary = "hello"
    blocks = build_summary_blocks(summary)
    assert len(blocks) == 1
    assert blocks[0]["text"]["text"] == "*Contract Summary:*\nhello"


def test_build_summary_blocks_long():
    long_text = "x" * 6500
    blocks = build_summary_blocks(long_text)
    # first block contains header
    assert blocks[0]["text"]["text"].startswith("*Contract Summary:*\n")
    # each block <= 3000 chars
    for blk in blocks:
        assert len(blk["text"]["text"]) <= 3000


@pytest.mark.asyncio
async def test_summarize_contract(monkeypatch):
    monkeypatch.setattr(app, "AsyncOpenAI", DummyClient)
    result = await summarize_contract("dummy text")
    assert result == "summarized result"


@pytest.mark.asyncio
async def test_create_github_issue_success(monkeypatch):
    dummy = DummyResponse(status=201, data={"html_url": "http://issue/1"})
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(aiohttp, "ClientSession", lambda: DummySession(dummy))
    issue = await create_github_issue("T", "B")
    assert issue["html_url"] == "http://issue/1"


@pytest.mark.asyncio
async def test_create_github_issue_failure(monkeypatch):
    bad = DummyResponse(status=400, data={"message": "bad"})
    monkeypatch.setenv("GITHUB_REPO", "owner/repo")
    monkeypatch.setenv("GITHUB_TOKEN", "token")
    monkeypatch.setattr(aiohttp, "ClientSession", lambda: DummySession(bad))
    with pytest.raises(RuntimeError) as excinfo:
        await create_github_issue("T", "B")
    assert "GitHub issue creation failed" in str(excinfo.value)


@pytest.mark.asyncio
async def test_handle_review_no_files():
    say = DummySay()
    event = {"text": "@legal-bot please review", "files": None}
    await handle_review(event, say)
    # Should warn about missing file
    assert say.messages
    assert "attach a contract file" in say.messages[-1][0][0]


@pytest.mark.asyncio
async def test_handle_review_success(monkeypatch):
    file_info = {
        "url_private_download": "http://dummy/contract.txt",
        "mimetype": "text/plain",
        "name": "contract.txt",
        "permalink": "http://dummy/link",
    }
    event = {"text": "@legal-bot please review", "files": [file_info]}

    # Stub download
    monkeypatch.setattr(
        aiohttp, "ClientSession", lambda headers=None: DummyGetSession()
    )

    # Stub file extraction
    monkeypatch.setattr(
        "file_utils.extract_text_from_bytes", lambda raw, mt: "extracted text"
    )

    # Stub summarization
    async def fake_summarize(text):
        assert text == "extracted text"
        return "fake summary"

    monkeypatch.setattr(app, "summarize_contract", fake_summarize)

    # Stub GitHub issue creation
    async def fake_create_issue(title, body):
        assert "contract.txt" in title
        assert "fake summary" in body
        return {"html_url": "http://issue/1"}

    monkeypatch.setattr(app, "create_github_issue", fake_create_issue)

    say = DummySay()
    await handle_review(event, say)

    # Expect summary blocks + issue confirmation
    assert len(say.messages) == 2
    # Check summary in blocks
    blocks = say.messages[0][1]["blocks"]
    assert "fake summary" in blocks[0]["text"]["text"]
    # Check issue confirmation
    assert say.messages[1][0][0] == "✅ Created GitHub issue: http://issue/1"
