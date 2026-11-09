"""These run without a token. The API is a stub."""

from __future__ import annotations

import io
import json
import os
import re
import subprocess
import sys
import urllib.error
import urllib.parse
from pathlib import Path

import pytest

import youtube_scraper.__main__ as cli

# the package exports a function named scrape, which hides the module of that name
yt = sys.modules["youtube_scraper.scrape"]

ROOT = Path(__file__).resolve().parents[1]


class FakeApi:
    """Answers trigger, progress and snapshot the way the live API does."""

    def __init__(self, rows=None, states=("ready",)):
        self.rows = rows or []
        self.states = list(states)
        self.calls = []

    def __call__(self, path, body=None):
        self.calls.append((path, body))
        if path.startswith("/trigger"):
            return {"snapshot_id": "sd_test"}
        if path.startswith("/progress/"):
            return {"status": self.states.pop(0) if len(self.states) > 1 else self.states[0]}
        if path.startswith("/snapshot/"):
            return self.rows
        raise AssertionError(path)

    def trigger(self):
        path, body = self.calls[0]
        return dict(urllib.parse.parse_qsl(path.split("?", 1)[1])), body


@pytest.fixture
def api(monkeypatch):
    def install(**kwargs):
        fake = FakeApi(**kwargs)
        monkeypatch.setattr(yt, "_call", fake)
        monkeypatch.setattr(yt, "POLL_SECONDS", 0)
        return fake

    return install


@pytest.fixture
def no_login(monkeypatch, tmp_path):
    """No token in the environment and no CLI login: the stranger's machine."""
    monkeypatch.delenv("BRIGHTDATA_API_TOKEN", raising=False)
    monkeypatch.setattr(yt, "_cli_credentials", lambda: tmp_path / "missing.json")


def test_a_keyword_search_is_capped_twice_and_sends_the_limit_as_text(api):
    fake = api()
    yt.search("python tutorial", 3, country="US")

    query, body = fake.trigger()
    assert query == {
        "dataset_id": yt.VIDEOS,
        "include_errors": "true",
        "type": "discover_new",
        "discover_by": "keyword",
        "limit_per_input": "3",
    }
    # num_of_posts is a text field in this scraper's schema
    assert body == [{"keyword": "python tutorial", "num_of_posts": "3", "country": "US"}]


@pytest.mark.parametrize(
    ("call", "args", "dataset", "discover_by", "item"),
    [
        (yt.videos, ("https://www.youtube.com/watch?v=jNQXAC9IVRw",), "VIDEOS", None,
         {"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw"}),
        (yt.search_filters, ("python tutorial", 2), "VIDEOS", "search_filters",
         {"keyword_search": "python tutorial"}),
        (yt.hashtag, ("#cooking", 2), "VIDEOS", "hashtag", {"hashtag": "cooking", "num_of_posts": 2}),
        (yt.channel_videos, ("https://www.youtube.com/@NASA/videos", 2), "VIDEOS", "url",
         {"url": "https://www.youtube.com/@NASA/videos", "num_of_posts": 2}),
        (yt.explore, ("https://www.youtube.com/gaming/games", 2), "VIDEOS", "explore",
         {"url": "https://www.youtube.com/gaming/games"}),
        (yt.podcast, ("https://www.youtube.com/playlist?list=PL1", 2), "VIDEOS", "podcast_url",
         {"url": "https://www.youtube.com/playlist?list=PL1"}),
        (yt.channels, ("https://www.youtube.com/@MrBeast/about",), "CHANNELS", None,
         {"url": "https://www.youtube.com/@MrBeast/about"}),
        (yt.channels_search, ("home cooking", 2), "CHANNELS", "keyword", {"keyword": "home cooking"}),
        (yt.comments, ("https://www.youtube.com/watch?v=jNQXAC9IVRw", 3), "COMMENTS", None,
         {"url": "https://www.youtube.com/watch?v=jNQXAC9IVRw", "num_of_comments": 3}),
    ],
)
def test_each_method_sends_the_input_the_live_api_validates(api, call, args, dataset, discover_by, item):
    fake = api()
    call(*args)
    query, body = fake.trigger()
    assert query["dataset_id"] == getattr(yt, dataset)
    assert query.get("discover_by") == discover_by
    assert body == [item]
    if discover_by:  # every discovery is capped, so a typo cannot bill every match
        assert query["limit_per_input"] == str(args[1])


def test_options_are_passed_through_and_unset_ones_are_left_out(api):
    fake = api()
    yt.videos(["https://a", "https://b"], transcription_language="English", country=None)
    assert fake.trigger()[1] == [
        {"url": "https://a", "transcription_language": "English"},
        {"url": "https://b", "transcription_language": "English"},
    ]


def test_run_polls_until_the_snapshot_is_ready(api):
    fake = api(rows=[{"title": "Me at the zoo"}], states=("running", "running", "ready"))
    assert yt.run(yt.VIDEOS, [{"url": "x"}]) == [{"title": "Me at the zoo"}]
    assert [p for p, _ in fake.calls].count("/progress/sd_test") == 3


def test_a_dropped_poll_does_not_lose_the_job(api, monkeypatch):
    fake = api(rows=[{"title": "Me at the zoo"}])
    dropped = []

    def flaky(path, body=None):
        if path.startswith("/progress/") and not dropped:
            dropped.append(path)
            raise urllib.error.URLError("connection reset")
        return fake(path, body)

    monkeypatch.setattr(yt, "_call", flaky)
    assert yt.run(yt.VIDEOS, [{"url": "x"}]) == [{"title": "Me at the zoo"}]
    assert dropped


def test_a_failed_snapshot_is_an_error(api):
    api(states=("failed",))
    with pytest.raises(yt.ApiError, match="sd_test failed"):
        yt.run(yt.VIDEOS, [{"url": "x"}])


def test_a_job_that_never_finishes_times_out(api):
    api(states=("running",))
    with pytest.raises(TimeoutError, match="timeout"):
        yt.run(yt.VIDEOS, [{"url": "x"}], timeout=0)


def test_an_http_error_names_the_status_and_the_reason(monkeypatch):
    monkeypatch.setenv("BRIGHTDATA_API_TOKEN", "test")

    def refuse(request, timeout):
        body = io.BytesIO(b'{"errors":[["duration","This value is not allowed"]]}')
        raise urllib.error.HTTPError(request.full_url, 400, "Bad Request", {}, body)

    monkeypatch.setattr(yt.urllib.request, "urlopen", refuse)
    with pytest.raises(yt.ApiError, match="HTTP 400.*duration"):
        yt.trigger(yt.VIDEOS, [{"keyword_search": "x", "duration": "4-20 minutes"}])


def test_the_token_comes_from_the_environment_then_the_cli_login(monkeypatch, tmp_path, no_login):
    with pytest.raises(yt.TokenMissing, match="export BRIGHTDATA_API_TOKEN"):
        yt.token()

    credentials = tmp_path / "credentials.json"
    credentials.write_text(json.dumps({"api_key": "from-login"}), encoding="utf-8")
    monkeypatch.setattr(yt, "_cli_credentials", lambda: credentials)
    assert yt.token() == "from-login"

    monkeypatch.setenv("BRIGHTDATA_API_TOKEN", "from-env")
    assert yt.token() == "from-env"


def test_error_rows_alone_fail_the_keyword(api):
    api(rows=[{"error": "Parse error: something", "error_code": "parse_error"}])
    outcome = yt.search_keyword("zzqqxx")

    assert not outcome.ok
    assert outcome.line() == "failed  'zzqqxx': Parse error: something"


def test_videos_already_paid_for_are_kept_and_a_cancelled_crawl_is_not_an_error(api):
    api(rows=[
        {"title": "Python for Beginners"},
        {"error": yt.CANCELLED},
        {"error": "Video unavailable", "error_code": "dead_page"},
    ])
    outcome = yt.search_keyword("python tutorial")

    assert outcome.ok
    assert outcome.videos == [{"title": "Python for Beginners"}]
    assert outcome.line() == "got     'python tutorial': 1 videos, 1 error rows: Video unavailable"


def test_one_bad_keyword_does_not_end_the_run(monkeypatch):
    def search(keyword, limit):
        if keyword == "boom":
            raise RuntimeError("boom")
        return [{"title": keyword}]

    monkeypatch.setattr(yt, "search", search)
    first, second = yt.scrape(["boom", "bread"])

    assert first.error == "RuntimeError: boom"
    assert second.ok and second.videos == [{"title": "bread"}]


def test_a_run_writes_what_it_found(api, tmp_path):
    api(rows=[{"title": "Me at the zoo", "views": 448084582}])
    path = yt.write(yt.scrape(["first youtube video"], 1), tmp_path / "out.json")

    document = json.loads(path.read_text(encoding="utf-8"))
    assert document["keywords"] == [
        {"keyword": "first youtube video", "videos": [{"title": "Me at the zoo", "views": 448084582}]}
    ]
    assert document["generated_at"]


def fake_cli(monkeypatch, outcome_for):
    monkeypatch.setattr(cli, "token", lambda: "test")
    monkeypatch.setattr(cli, "search_keyword", lambda k, limit: outcome_for(k))


def test_the_cli_exit_code_says_whether_every_keyword_worked(monkeypatch, tmp_path):
    fake_cli(monkeypatch, lambda k: yt.Outcome(k, videos=[{"title": "x"}]))
    assert cli.main(["python tutorial", "--out", str(tmp_path / "ok.json")]) == 0

    fake_cli(monkeypatch, lambda k: yt.Outcome(k, error="boom"))
    assert cli.main(["python tutorial", "--out", str(tmp_path / "bad.json")]) == 1


def test_each_result_prints_before_the_next_keyword_starts(monkeypatch, tmp_path, capsys):
    fake_cli(monkeypatch, lambda k: yt.Outcome(k, videos=[{"title": "x"}]))
    cli.main(["python tutorial", "home cooking", "--out", str(tmp_path / "o.json")])

    out = capsys.readouterr().out.splitlines()
    assert [ln for ln in out if ln.startswith(("asking", "got"))] == [
        "asking  'python tutorial'...",
        "got     'python tutorial': 1 videos",
        "asking  'home cooking'...",
        "got     'home cooking': 1 videos",
    ]


def test_a_limit_below_one_is_refused_before_any_request(capsys):
    for bad in ("0", "-3"):
        with pytest.raises(SystemExit):
            cli.main(["x", "--limit", bad])
    assert "1 or more" in capsys.readouterr().err


def test_a_missing_token_is_a_message_not_a_traceback(no_login, capsys):
    assert cli.main(["python tutorial"]) == 2
    err = capsys.readouterr().err
    assert "export BRIGHTDATA_API_TOKEN" in err and "bdata login" in err
    assert "Traceback" not in err


def test_piped_output_keeps_the_header_before_the_error(tmp_path):
    """A log or an agent reads a pipe. The header must not land after the error."""
    env = {k: v for k, v in os.environ.items() if k != "BRIGHTDATA_API_TOKEN"}
    env["HOME"] = str(tmp_path)  # no CLI login: the stranger's machine
    env["APPDATA"] = str(tmp_path)
    run = subprocess.run(
        [sys.executable, "-m", "youtube_scraper", "python tutorial"],
        cwd=tmp_path,
        env={**env, "PYTHONPATH": str(ROOT / "src")},
        stdout=subprocess.PIPE,
        stderr=subprocess.STDOUT,
        text=True,
        timeout=60,
    )
    assert run.returncode == 2, run.stdout
    assert run.stdout.index("Finding up to") < run.stdout.index("API token required")


def test_the_readme_excerpt_is_the_start_of_the_example_file():
    """The README shows the first 20 lines of the real file, verbatim, and links it."""
    sample = (ROOT / "examples" / "sample_output.json").read_text(encoding="utf-8")
    readme = (ROOT / "README.md").read_text(encoding="utf-8")

    assert "\n".join(sample.splitlines()[:20]) in readme, "README excerpt drifted from the file"
    assert "](examples/sample_output.json)" in readme


def test_every_in_page_link_has_its_heading():
    """A renamed heading would break the header row silently; the link check sees only URLs."""
    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    headings = re.findall(r"^#{1,6} (.+)$", readme, re.M)
    anchors = {re.sub(r"[^a-z0-9 -]", "", h.lower()).replace(" ", "-") for h in headings}
    for anchor in re.findall(r"\]\(#([^)]+)\)", readme):
        assert anchor in anchors, f"#{anchor} points at no heading"
