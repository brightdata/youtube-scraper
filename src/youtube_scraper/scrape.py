"""YouTube videos, transcripts, channels and comments on the Bright Data Scraper API.

    keyword -> trigger discover_by=keyword -> poll progress -> fetch snapshot -> videos

Standard library only. The Python SDK wraps nine of the ten YouTube methods,
not podcasts, so this module talks to the API over HTTP and covers all ten the
same way. Every call is an asynchronous job: trigger it, poll until the
snapshot is ready, download it. On 2026-11-09 a run took 12 seconds (one
channel) to 250 seconds (a podcast playlist); a channel's videos took 562
seconds to fail.
"""

from __future__ import annotations

import json
import os
import sys
import time
import urllib.error
import urllib.parse
import urllib.request
from collections.abc import Iterable
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

API = "https://api.brightdata.com/datasets/v3"

#: The three YouTube scrapers. Videos has one collect and six discovery methods.
VIDEOS = "gd_lk56epmy2i5g7lzu0k"  # videos and Shorts: details, transcript, chapters
CHANNELS = "gd_lk538t2k2p1k3oos71"  # channel details: subscribers, views, video count
COMMENTS = "gd_lk9q0ew71spt1mxywf"  # comments on a video URL

#: The slowest run on 2026-11-09 was 562 seconds; the wait outlasts that comfortably.
TIMEOUT = 900
POLL_SECONDS = 10

NO_TOKEN = (
    "API token required but not found.\n"
    "  export BRIGHTDATA_API_TOKEN=YOUR_API_KEY   token: https://brightdata.com/cp/setting/users\n"
    "  or run once: npx -p @brightdata/cli bdata login"
)


class ApiError(Exception):
    """The API refused a request, or a job ended without a snapshot."""


class TokenMissing(ApiError):
    """No token in the environment and no Bright Data CLI login."""


def _cli_credentials() -> Path:
    """Where `bdata login` stores the key, the same path the Python SDK reads."""
    if sys.platform == "win32":
        base = Path(os.environ.get("APPDATA", str(Path.home() / "AppData" / "Roaming")))
    elif sys.platform == "darwin":
        base = Path.home() / "Library" / "Application Support"
    else:
        base = Path.home() / ".config"
    return base / "brightdata-cli" / "credentials.json"


def token() -> str:
    """BRIGHTDATA_API_TOKEN, else the Bright Data CLI login. Never a key in code."""
    found = os.environ.get("BRIGHTDATA_API_TOKEN", "").strip()
    if found:
        return found
    try:
        found = json.loads(_cli_credentials().read_text(encoding="utf-8")).get("api_key", "")
    except (OSError, ValueError, AttributeError):
        found = ""
    if not found:
        raise TokenMissing(NO_TOKEN)
    return found


def _call(path: str, body: Any = None) -> Any:
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(
        API + path,
        data=data,
        headers={"Authorization": f"Bearer {token()}", "Content-Type": "application/json"},
    )
    try:
        with urllib.request.urlopen(request, timeout=120) as response:
            return json.loads(response.read() or b"null")
    except urllib.error.HTTPError as exc:
        detail = exc.read().decode(errors="replace").strip()
        raise ApiError(f"HTTP {exc.code}: {detail[:300]}") from None


def trigger(
    dataset_id: str,
    inputs: list[dict[str, Any]],
    *,
    discover_by: str | None = None,
    limit_per_input: int | None = None,
) -> str:
    """Start a job and return its snapshot id. Error rows are always asked for."""
    query: dict[str, Any] = {"dataset_id": dataset_id, "include_errors": "true"}
    if discover_by:
        query.update(type="discover_new", discover_by=discover_by)
    if limit_per_input is not None:
        query["limit_per_input"] = limit_per_input
    return _call("/trigger?" + urllib.parse.urlencode(query), inputs)["snapshot_id"]


def status(snapshot_id: str) -> str:
    """running, ready or failed."""
    return _call(f"/progress/{snapshot_id}")["status"]


def fetch(snapshot_id: str) -> list[dict[str, Any]]:
    """The rows of a ready snapshot. Snapshots stay downloadable for 30 days."""
    data = _call(f"/snapshot/{snapshot_id}?format=json")
    return [row for row in (data if isinstance(data, list) else [data]) if isinstance(row, dict)]


def _poll(snapshot_id: str) -> str:
    """status(), except that a dropped connection is not the end of a paid job.

    A poll is safe to repeat. A Node run of this same loop lost a job to one
    "fetch failed" on 2026-10-24, five minutes in. An HTTP error still raises.
    """
    try:
        return status(snapshot_id)
    except (urllib.error.URLError, OSError):
        return "running"


def run(
    dataset_id: str,
    inputs: list[dict[str, Any]],
    *,
    discover_by: str | None = None,
    limit_per_input: int | None = None,
    timeout: float = TIMEOUT,
) -> list[dict[str, Any]]:
    """Trigger, wait, fetch. Rows the API could not collect carry an `error` key."""
    snapshot_id = trigger(
        dataset_id, inputs, discover_by=discover_by, limit_per_input=limit_per_input
    )
    deadline = time.monotonic() + timeout
    while (state := _poll(snapshot_id)) not in ("ready", "failed"):
        if time.monotonic() > deadline:
            raise TimeoutError(f"timeout: snapshot {snapshot_id} not ready after {timeout:.0f}s")
        time.sleep(POLL_SECONDS)
    if state == "failed":
        raise ApiError(f"snapshot {snapshot_id} failed")
    return fetch(snapshot_id)


def _many(value: str | Iterable[str]) -> list[str]:
    return [value] if isinstance(value, str) else list(value)


def _set(**fields: Any) -> dict[str, Any]:
    """Only the fields that were actually set."""
    return {name: value for name, value in fields.items() if value is not None}


def _items(urls: str | Iterable[str], **fields: Any) -> list[dict[str, Any]]:
    """One input per URL, with every field that was actually set."""
    return [{"url": url, **_set(**fields)} for url in _many(urls)]


def videos(urls: str | Iterable[str], **options: Any) -> list[dict[str, Any]]:
    """Full records for video or Shorts URLs: views, likes, transcript, chapters.

    `options` go into each input as the API names them: `country` or
    `transcription_language`, for example "English".
    """
    return run(VIDEOS, _items(urls, **options))


def search(keyword: str, limit: int = 5, **options: Any) -> list[dict[str, Any]]:
    """Videos YouTube shows for a search, `limit` of them.

    `options`: `start_date` and `end_date` (MM-DD-YYYY), `country`,
    `include_shorts`. `num_of_posts` is a text field in this scraper's schema.
    """
    item = {"keyword": keyword, "num_of_posts": str(limit), **_set(**options)}
    return run(VIDEOS, [item], discover_by="keyword", limit_per_input=limit)


def search_filters(keyword: str, limit: int = 5, **filters: Any) -> list[dict[str, Any]]:
    """Videos for a search with YouTube's own filters applied.

    `filters` are YouTube's filter labels, checked against fixed lists:
    `upload_date`, `type`, `duration`, `features`, `sort_by`, `country`.
    Accepted live on 2026-11-09: "This month", "Video", "Under 4 minutes".
    "4-20 minutes" is rejected with HTTP 400.
    """
    item = {"keyword_search": keyword, **_set(**filters)}
    return run(VIDEOS, [item], discover_by="search_filters", limit_per_input=limit)


def hashtag(tag: str, limit: int = 5, **options: Any) -> list[dict[str, Any]]:
    """Videos and Shorts for a hashtag, without the #. `start_date`, `end_date` in options."""
    item = {"hashtag": tag.lstrip("#"), "num_of_posts": limit, **_set(**options)}
    return run(VIDEOS, [item], discover_by="hashtag", limit_per_input=limit)


def channel_videos(
    channel_urls: str | Iterable[str], limit: int = 5, **options: Any
) -> list[dict[str, Any]]:
    """Recent videos from a channel's /videos or /shorts URL.

    On 2026-11-09 every run returned error rows, "Parse error:
    ORIGINAL_LANGUAGE_TO_COUNTRY is not defined", after about nine minutes.
    """
    items = _items(channel_urls, num_of_posts=limit, **options)
    return run(VIDEOS, items, discover_by="url", limit_per_input=limit)


def explore(urls: str | Iterable[str], limit: int = 5, **options: Any) -> list[dict[str, Any]]:
    """Videos from a YouTube explore page, such as https://www.youtube.com/gaming/games."""
    return run(VIDEOS, _items(urls, **options), discover_by="explore", limit_per_input=limit)


def podcast(urls: str | Iterable[str], limit: int = 5) -> list[dict[str, Any]]:
    """Episodes from a podcast playlist or a channel's /podcasts URL."""
    return run(VIDEOS, _items(urls), discover_by="podcast_url", limit_per_input=limit)


def channels(urls: str | Iterable[str]) -> list[dict[str, Any]]:
    """Channel details for channel URLs: subscribers, views, video count, links."""
    return run(CHANNELS, _items(urls))


def channels_search(keyword: str, limit: int = 5) -> list[dict[str, Any]]:
    """Channels matching a keyword, with the same fields as `channels`."""
    return run(CHANNELS, [{"keyword": keyword}], discover_by="keyword", limit_per_input=limit)


def comments(urls: str | Iterable[str], limit: int = 10, **options: Any) -> list[dict[str, Any]]:
    """Comments on video URLs, `limit` per video. Billed per comment.

    `options`: `sort_by`, `load_replies`.
    """
    return run(COMMENTS, _items(urls, num_of_comments=limit, **options))


#: When a discovery reaches `limit_per_input`, crawls still running can come
#: back as rows with this error. That is the limit working, not a failure.
CANCELLED = "Crawl aborted on job cancel"


def split(rows: list[dict[str, Any]]) -> tuple[list[dict[str, Any]], list[str]]:
    """Records, and the error messages of the rows that are not records."""
    records = [row for row in rows if not row.get("error")]
    errors = [str(row["error"]) for row in rows if row.get("error") and row["error"] != CANCELLED]
    return records, errors


@dataclass
class Outcome:
    """What happened to one search keyword."""

    keyword: str
    videos: list[dict[str, Any]] = field(default_factory=list)
    error: str | None = None
    note: str = ""

    @property
    def ok(self) -> bool:
        return self.error is None

    def line(self) -> str:
        """One line a reader can understand without having read the source."""
        if not self.ok:
            return f"failed  {self.keyword!r}: {self.error}"
        tail = f", {self.note}" if self.note else ""
        return f"got     {self.keyword!r}: {len(self.videos)} videos{tail}"


def search_keyword(keyword: str, limit: int = 5) -> Outcome:
    """Fetch one keyword. Never raises for a bad keyword: a failure becomes an Outcome.

    A missing token is the exception, because it fails every keyword the same way.
    """
    outcome = Outcome(keyword=keyword)
    try:
        found, errors = split(search(keyword, limit))
    except TokenMissing:
        raise
    except Exception as exc:  # one bad keyword must not end the run
        outcome.error = str(exc) if isinstance(exc, (ApiError, TimeoutError)) else (
            f"{type(exc).__name__}: {exc}"
        )
        return outcome
    if found:
        # Keep what was paid for. A partial run reports the rest as a note.
        outcome.videos = found
        if errors:
            outcome.note = f"{len(errors)} error rows: {errors[0]}"
    elif errors:
        outcome.error = "; ".join(dict.fromkeys(errors))
    return outcome


def scrape(keywords: Iterable[str], limit: int = 5) -> list[Outcome]:
    """Run every keyword and return one Outcome each, in order."""
    return [search_keyword(keyword, limit) for keyword in keywords]


def write(outcomes: list[Outcome], path: str | Path) -> Path:
    """Write one JSON file: when it ran, and the videos found per keyword."""
    document = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "keywords": [{"keyword": o.keyword, "videos": o.videos} for o in outcomes],
    }
    target = Path(path)
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_text(json.dumps(document, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    return target
