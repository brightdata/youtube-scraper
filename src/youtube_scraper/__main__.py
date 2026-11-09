"""youtube-scraper "python tutorial", or python -m youtube_scraper "python tutorial" """

from __future__ import annotations

import argparse
import sys
import threading
import time
from contextlib import contextmanager

from .scrape import TokenMissing, search_keyword, token, write

FRAMES = "⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏"


def positive(value: str) -> int:
    """Reject a limit the API would charge for and not honour."""
    number = int(value)
    if number < 1:
        raise argparse.ArgumentTypeError(f"{value} is not 1 or more")
    return number


@contextmanager
def waiting(label: str):
    """A spinner and a running clock, so minutes of waiting look alive.

    Outside a terminal it prints one plain line instead: a log wants a line,
    not an animation.
    """
    if not sys.stdout.isatty():
        print(f"asking  {label}...", flush=True)
        yield
        return
    done = threading.Event()
    started = time.monotonic()

    def spin() -> None:
        frame = 0
        while not done.wait(0.1):
            secs = int(time.monotonic() - started)
            clock = f"{secs // 3600}:{secs // 60 % 60:02d}:{secs % 60:02d}"
            sys.stdout.write(f"\r\033[2K{FRAMES[frame % len(FRAMES)]} {label} {clock}")
            sys.stdout.flush()
            frame += 1

    thread = threading.Thread(target=spin, daemon=True)
    thread.start()
    try:
        yield
    finally:
        done.set()
        thread.join()
        sys.stdout.write("\r\033[2K")  # leave the line clean for the result
        sys.stdout.flush()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        prog="youtube-scraper",
        description="Find YouTube videos for one or more search keywords.",
    )
    parser.add_argument("keywords", nargs="+", help="what you would type into YouTube, quoted")
    parser.add_argument("--limit", type=positive, default=5, help="videos per keyword, default 5")
    parser.add_argument("--out", default="youtube.json", help="output file, default %(default)s")
    args = parser.parse_args(argv)

    print(
        f"Finding up to {args.limit} videos per keyword, for: {', '.join(args.keywords)}\n"
        "Usually two to ten minutes each. Billed per video, 5,000 free credits a month.",
        flush=True,  # piped, an unflushed header would print after the error below
    )
    try:
        token()  # fail before the first wait, not after it
    except TokenMissing as exc:
        print(exc, file=sys.stderr)
        return 2

    outcomes = []
    for keyword in args.keywords:
        with waiting(repr(keyword)):
            outcome = search_keyword(keyword, args.limit)
        print(outcome.line(), flush=True)
        outcomes.append(outcome)

    path = write(outcomes, args.out)
    found = [video for outcome in outcomes for video in outcome.videos]
    fields = f" ({len(found[0])} fields per video)" if found else ""
    print(f"\nSaved {len(found)} videos as JSON to {path}{fields}")
    return 0 if all(o.ok for o in outcomes) else 1


if __name__ == "__main__":
    sys.exit(main())
