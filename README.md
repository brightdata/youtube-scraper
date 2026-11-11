# YouTube scraper for Python

Scrape YouTube videos, transcripts, Shorts, comments and channels to JSON with Python. No YouTube Data API key, no quota.
Built on the [Bright Data YouTube Scraper API](https://brightdata.com/products/web-scraper/youtube?utm_source=github&utm_medium=referral&utm_content=youtube-scraper). New accounts get 5,000 free credits a month.

[![Live check](https://github.com/brightdata/youtube-scraper/actions/workflows/live.yml/badge.svg)](https://github.com/brightdata/youtube-scraper/actions/workflows/live.yml)
[![last verified](https://img.shields.io/badge/last%20verified-11%20Nov%202026-brightgreen)](https://github.com/brightdata/youtube-scraper/actions/workflows/live.yml) <!-- verified: rewritten by the daily run -->

[Quickstart](#how-to-scrape-youtube-videos-with-python) · [No API key](#scrape-youtube-without-the-youtube-data-api) · [CLI](#bulk-youtube-search-scraper-cli) · [Endpoints](#scrape-youtube-videos-transcripts-shorts-channels-and-comments) · [Transcripts](#scrape-youtube-video-transcripts) · [Data](#youtube-video-data-fields-json) · [Errors](#youtube-scraper-errors) · [MCP and Claude Code](#youtube-mcp-server-and-claude-code-skill) · [Free credits](#is-this-youtube-scraper-free) · [Docs](https://docs.brightdata.com/products/scrapers/youtube/introduction) · [Support](#support)

YouTube data as JSON, in Python: videos and Shorts with views, likes,
transcripts and chapters, search results, hashtags, channels, comments and
podcast episodes. All three Bright Data YouTube scrapers and all ten of their
methods, one function each. No YouTube Data API key, no quota, no browser, no
dependencies. Built on the
[Bright Data YouTube Scraper API](https://brightdata.com/products/web-scraper/youtube?utm_source=github&utm_medium=referral&utm_content=youtube-scraper).

Also here: a one-command CLI for keyword searches, and the
[Bright Data CLI](#youtube-mcp-server-and-claude-code-skill), which needs no Python at all.

## How to scrape YouTube videos with Python

Python 3.10 or newer, and nothing to install: this is the standard library.

```bash
export BRIGHTDATA_API_TOKEN=YOUR_API_KEY
```

Get a token from the
[Bright Data control panel](https://brightdata.com/cp/setting/users). No
account yet? [Create one](https://brightdata.com/cp/start); new accounts get
[5,000 free credits a month](https://docs.brightdata.com/general/account/billing-and-pricing/free-tier).

```python
import json
import os
import time
import urllib.parse
import urllib.request

API = "https://api.brightdata.com/datasets/v3"
HEADERS = {
    "Authorization": f"Bearer {os.environ['BRIGHTDATA_API_TOKEN']}",
    "Content-Type": "application/json",
}


def call(path, body=None):
    data = None if body is None else json.dumps(body).encode()
    request = urllib.request.Request(API + path, data=data, headers=HEADERS)
    with urllib.request.urlopen(request) as response:
        return json.load(response)


query = urllib.parse.urlencode({
    "dataset_id": "gd_lk56epmy2i5g7lzu0k",
    "type": "discover_new",
    "discover_by": "keyword",
    "limit_per_input": 3,
    "include_errors": "true",
})
job = call(f"/trigger?{query}", [{"keyword": "python tutorial", "num_of_posts": "3"}])
while call(f"/progress/{job['snapshot_id']}")["status"] not in ("ready", "failed"):
    time.sleep(10)
for video in call(f"/snapshot/{job['snapshot_id']}?format=json"):
    if "error" in video:
        print("error row:", video["error"])
        continue
    print(video["views"], video["likes"], video["title"][:50])
```

```
error row: Parse error: ORIGINAL_LANGUAGE_TO_COUNTRY is not defined
8099775 172885 Python Full Course for Beginners
13396612 377300 Python Full Course for free 🐍
```

Expect two to eleven minutes: the API runs a search job and the loop waits for
it. Billed [per video](https://brightdata.com/pricing/web-scraper).

Three things in that snippet are not optional.

`limit_per_input` caps the run, and the bill. `num_of_posts` asks for the same
number; it is a text field in this scraper, so it is sent as `"3"`.

`include_errors=true` makes the API report a video it could not collect as a
row with an `error` key. The API default is off, and a failed search then
looks the same as a search with no results.

The `error row` branch is there because, on 9 Nov 2026, some videos in a
search came back as "Parse error: ORIGINAL_LANGUAGE_TO_COUNTRY is not
defined" while the rest came back whole. See
[YouTube scraper errors](#youtube-scraper-errors).

## Scrape YouTube without the YouTube Data API

The YouTube Scraper API needs no Google Cloud project, no YouTube Data API key
and no OAuth, and it has no daily quota. The only credential is a Bright Data
API key, set as `BRIGHTDATA_API_TOKEN`. This package and its command also find
the key stored by `bdata login`. It collects what a logged-out visitor can
see, the transcript included.

## Bulk YouTube search scraper CLI

The command in this repo runs the Python quickstart for several keywords at
once and writes one JSON file.

```bash
pip install git+https://github.com/brightdata/youtube-scraper
youtube-scraper "python tutorial" "home workout" --limit 2
```

```
Finding up to 2 videos per keyword, for: python tutorial, home workout
Usually two to ten minutes each. Billed per video, 5,000 free credits a month.
asking  'python tutorial'...
got     'python tutorial': 1 videos, 1 error rows: Parse error: ORIGINAL_LANGUAGE_TO_COUNTRY is not defined
asking  'home workout'...
got     'home workout': 2 videos

Saved 3 videos as JSON to youtube.json (51 fields per video)
```

In a terminal the `asking` lines are replaced by a spinner and a running
clock, updating in place, so you can see it is working and how long it has
been going.

```
--limit N      videos per keyword, default 5, minimum 1
--out PATH     output file, default youtube.json
```

`python -m youtube_scraper` works too. The command finds the token in
`BRIGHTDATA_API_TOKEN`, or, if you ran `npx -p @brightdata/cli bdata login`
once, in the stored login, for you and for any coding agent in that terminal.

Import it instead of running it, for `ok`, `note` and `error` per keyword
instead of raw rows. `scrape` never raises for one bad keyword; check `ok`
before reading `videos`:

```python
from youtube_scraper import scrape

for outcome in scrape(["python tutorial", "home workout"], limit=1):
    if outcome.ok:
        video = outcome.videos[0]
        print(f"{outcome.keyword}: {video['title'][:45]} ({video['views']} views)")
    else:
        print(f"{outcome.keyword} failed: {outcome.error}")
```

```
python tutorial: Curso de PYTHON desde CERO (Completo) (6251934 views)
home workout: 25 MIN FULL BODY HIIT for Beginners - No Equi (34828112 views)
```

A keyword fails only when every row it returns is an error row. When a search
returns some videos and some error rows, the videos are kept, and the errors
land in `note`.

## Scrape YouTube videos, transcripts, Shorts, channels and comments

Bright Data has three YouTube scrapers, videos, channels and comments, with
ten ways to call them, each documented in the
[YouTube Scraper API docs](https://docs.brightdata.com/api-reference/scrapers/social-media-apis/youtube-videos-collect-by-url).
This package has one function for each. Every snippet below is complete:
paste it as is after the `pip install` above. Every one of them runs in
Actions each Monday, a smaller check runs every other day, and the badge at
the top is the latest result.

| you have | want | how |
| --- | --- | --- |
| video or Shorts URLs | views, likes, transcript, chapters | `videos(urls)` |
| a search, like "python tutorial" | matching videos | `search("python tutorial", 5)` |
| a search and YouTube's filters | filtered videos | `search_filters("python tutorial", 5, upload_date="This month")` |
| a hashtag | its videos and Shorts | `hashtag("baking", 5)` |
| video URLs | their comments | `comments(urls, 10)`, billed per comment |
| channel URLs | subscribers, views, video count | `channels(urls)` |
| a keyword | matching channels | `channels_search("home cooking", 5)` |
| a podcast playlist URL | its episodes | `podcast(url, 5)` |
| an explore page URL | its videos | `explore("https://www.youtube.com/gaming/games", 5)` |
| a channel's `/videos` URL | its recent videos | `channel_videos(url, 5)`, broken upstream on 9 Nov 2026 |

Each takes one URL or a list. A list is one job, not one per URL. Each returns
a list of rows, and a row the API could not collect carries an `error` key
instead of the record. Functions that take a limit pass any other input the
API accepts as a keyword argument, named as the API names it:
`search("python tutorial", 5, start_date="10-01-2026")`.

### Scrape a YouTube video by URL

```python
from youtube_scraper import videos

video = videos("https://www.youtube.com/watch?v=jNQXAC9IVRw")[0]
print(video["title"], "|", video["youtuber"], "|", video["date_posted"][:10])
print(video["views"], "views,", video["likes"], "likes,", video["num_comments"], "comments")
print(video["video_length"], "seconds,", video["category"], "| tags:", ", ".join(video["tags"]))
```

```
Me at the zoo | @jawed | 2005-04-24
448085592 views, 20132396 likes, 10646129 comments
19 seconds, Film & Animation | tags: me at the zoo, jawed karim, first youtube video
```

Collecting a video by URL took 12 to 178 seconds. Shorts URLs work the same way.

### Scrape YouTube video transcripts

```python
from youtube_scraper import videos

url = "https://www.youtube.com/watch?v=jNQXAC9IVRw"
video = videos(url, transcription_language="English")[0]
for line in video["formatted_transcript"][:3]:
    text = " ".join(line["text"].split())
    print(f"{line['start_time'] / 1000:5.1f}s  {text}")
print(len(video["transcript"]), "characters in all")
```

```
  1.2s  All right, so here we are, in front of the elephants
  5.3s  the cool thing about these guys is that they have really...
  8.0s  really really long trunks
217 characters in all
```

Every video record carries the transcript twice: `transcript` as plain text
and `formatted_transcript` as timed lines, `start_time` and `end_time` in
milliseconds. `transcript_language` lists the languages YouTube offers, and
`chapters` the video's chapters. The text keeps YouTube's line breaks.

### Scrape YouTube search results with filters

```python
from youtube_scraper import search_filters

found = search_filters(
    "python tutorial", 2, upload_date="This month", type="Video", duration="Under 4 minutes"
)
for video in found:
    if "error" in video:
        print("error row:", video["error"])
        continue
    print(video["date_posted"][:10], video["video_length"], "s |", video["title"][:50])
```

```
2026-10-12 79 s | Python for Beginners: Complete Tutorial & Practice
2026-10-23 82 s | Python Tutorial: Functions and Parameter Passing
```

The filters are YouTube's own labels, checked against fixed lists.
"This month", "Video" and "Under 4 minutes" were accepted; "4-20 minutes" is
an HTTP 400, `["duration", "This value is not allowed"]`.

### Scrape YouTube Shorts by hashtag

```python
from youtube_scraper import hashtag

for video in hashtag("baking", 2):
    if "error" in video:
        print("error row:", video["error"])
        continue
    print(video["post_type"], video["views"], video["url"])
```

```
post 5183839 https://www.youtube.com/watch?v=zdpxBdtBL4w
post 3349958 https://www.youtube.com/watch?v=3NvvOVrm1uY
```

Pass the tag without the `#`. `start_date` and `end_date`, `MM-DD-YYYY`, narrow
it to a window.

### Scrape YouTube comments from a video

```python
from youtube_scraper import comments

for comment in comments("https://www.youtube.com/watch?v=jNQXAC9IVRw", 3):
    print(comment["likes"], "|", comment["username"], "|", comment["comment_text"][:50])
```

```
4800000 | @SanDiegoZoo | We're so honored that the first ever YouTube video
1 | @roshac995 | 10M comment
1 | @دمینېنغمېپښتو | Happy 21years youtube
```

The limit is the `num_of_comments` input: 3 asked, 3 returned, in 43 seconds.
`sort_by` and `load_replies` go in as keyword arguments.

### Scrape YouTube channel data

```python
from youtube_scraper import channels

channel = channels("https://www.youtube.com/@NASA/about")[0]
print(channel["name"], channel["handle"])
print(channel["subscribers"], "subscribers,", channel["videos_count"], "videos,", channel["views"], "views")
```

```
NASA @NASA
15100000 subscribers, 6201 videos, 1134859779 views
```

The fastest call: 12 seconds.

### Find YouTube channels by keyword

```python
from youtube_scraper import channels_search

for channel in channels_search("home cooking", 2):
    print(channel["subscribers"], channel["name"], channel["url"])
```

```
3300000 HomeCookingShow https://www.youtube.com/@homecookingshow
1400000 HomeCooking Tamil https://www.youtube.com/@homecookingtamil
```

### Scrape YouTube podcast episodes

```python
from youtube_scraper import podcast

playlist = "https://www.youtube.com/playlist?list=PLbnMTcZEga8QCKJvxsJVQV4uHD6bENdnP"
for episode in podcast(playlist, 2):
    print(episode["date_posted"][:10], episode["views"], "|", episode["title"][:60])
```

```
2026-11-09 7455 | Are you risking your career if you post about work on social
2026-11-02 16738 | She gave all her employees flexible work. Here’s how she kep
```

A podcast playlist URL or a channel's `/podcasts` URL. The Python SDK has no
method for this one.

### Scrape the YouTube explore and gaming pages

```python
from youtube_scraper import explore

for video in explore("https://www.youtube.com/gaming/games", 2):
    print(video["live_status"], video["views"], "|", video["title"][:50])
```

```
is_live 3974 | ADDRESSING THE AGENDA - AMPHOREUS WATCHPARTY 1900 
is_live 4698 | 【#崩壊スターレイル 】アプデもうくる…！アッハのPV初見同時視聴！【 Vtuber/ 白亜リラ 】
```

The gaming page is mostly live streams, so `live_status` is `is_live` and
`views` counts the stream so far.

### Scrape a YouTube channel's videos

```python
from youtube_scraper import channel_videos

for row in channel_videos("https://www.youtube.com/@NASA/videos", 2):
    if "error" in row:
        print("error:", row["error_code"], row["error"])
    else:
        print(row["date_posted"][:10], row["title"][:60])
```

```
error: parse_error Parse error: ORIGINAL_LANGUAGE_TO_COUNTRY is not defined
error: parse_error Parse error: ORIGINAL_LANGUAGE_TO_COUNTRY is not defined
```

That output is real. On 9 Nov 2026 every channel tried, @NASA and @MrBeast,
five runs in all, returned only this error, after about nine minutes. The call
and the input match the live schema, and the weekly check runs this block, so
the badge will show when it comes back. Until then, `search` with the
channel's name, or `videos` on known URLs, gets the same records.

### Trigger now, fetch later

For anything bigger than a few searches, do not block a process for an hour.
Trigger, keep the snapshot id, fetch when ready. Snapshots stay downloadable
for 30 days.

```python
import time

from youtube_scraper import CHANNELS, fetch, status, trigger

snapshot = trigger(CHANNELS, [{"url": "https://www.youtube.com/@NASA/about"}])
print("snapshot:", snapshot)
while (state := status(snapshot)) not in ("ready", "failed"):
    time.sleep(10)
print("status:", state)
print("fetched:", fetch(snapshot)[0]["name"])
```

```
snapshot: sd_mw95rfbd114h5umqne
status: ready
fetched: NASA
```

`trigger` takes any dataset, `discover_by` and `limit_per_input`, so it reaches
every method in the table. Each input was accepted by the live API on
2026-11-09:

| method | dataset_id | discover_by | input |
| --- | --- | --- | --- |
| Video by URL | `gd_lk56epmy2i5g7lzu0k` | none | `{"url"}`, optional `{"country", "transcription_language"}` |
| Search | `gd_lk56epmy2i5g7lzu0k` | `keyword` | `{"keyword", "num_of_posts"}`, `num_of_posts` as text |
| Search with filters | `gd_lk56epmy2i5g7lzu0k` | `search_filters` | `{"keyword_search"}` plus filter labels |
| Hashtag | `gd_lk56epmy2i5g7lzu0k` | `hashtag` | `{"hashtag", "num_of_posts"}` |
| Channel videos | `gd_lk56epmy2i5g7lzu0k` | `url` | `{"url", "num_of_posts"}`, a `/videos` URL |
| Explore page | `gd_lk56epmy2i5g7lzu0k` | `explore` | `{"url"}`, optional `{"all_tabs"}` |
| Podcast | `gd_lk56epmy2i5g7lzu0k` | `podcast_url` | `{"url"}` |
| Channel by URL | `gd_lk538t2k2p1k3oos71` | none | `{"url"}` |
| Channels by keyword | `gd_lk538t2k2p1k3oos71` | `keyword` | `{"keyword"}` |
| Comments | `gd_lk9q0ew71spt1mxywf` | none | `{"url", "num_of_comments"}` |

`bdata pipelines info <dataset_id> <method>` prints the input fields the API
validates.

## YouTube video data fields (JSON)

The fields most people want from a video:

```
url  title  youtuber  views  likes  num_comments  date_posted  video_length  transcript  tags
```

The code hardcodes no field list. Whatever the API returns lands in each row,
and in the command's file.

<!-- fields:start -->
Regenerated every day from the published schema,
[scrapers-full.json](https://docs.brightdata.com/scrapers-full.json), so they cannot go stale. A record
carries the fields that apply to it, plus `timestamp` and `input`; the
sample file's first video has 51 keys.

<details>
<summary>All 49 video fields, <code>gd_lk56epmy2i5g7lzu0k</code></summary>

| field | type | description |
| --- | --- | --- |
| `url` | url | The full YouTube watch URL of the collected video |
| `title` | text | Title of the YouTube video |
| `youtuber` | text | The channel handle extracted from the channel's browse endpoint |
| `youtuber_md5` | text | MD5 hash of the youtuber field |
| `video_url` | url | Direct streaming URL of the video file, extracted from YouTube's adaptive formats or decoded from signatureCipher |
| `video_length` | number | Duration of the video in seconds |
| `likes` | number | Number of likes received by the video |
| `views` | number | Number of views the video has received |
| `date_posted` | date | Date when the video was published |
| `description` | text | Text description accompanying the video |
| `num_comments` | number | Number of comments on the video, as displayed by YouTube (includes both top-level comments and replies in YouTube's count) |
| `subscribers` | number | Number of subscribers to the YouTube channel |
| `music` | object | Information about the music used in the video. Only present when YouTube's Content ID system has identified music in the video |
| `video_id` | text | Unique identifier for the YouTube video |
| `channel_url` | url | URL-encoded URL of the YouTube channel, derived from the channel's canonical browse endpoint |
| `preview_image` | image | URL of the preview image for the video |
| `shortcode` | text | The unique short identifier of the video, identical to video_id, used across all YouTube video types including regular videos and Shorts |
| `verified` | boolean | Indicates whether the channel is verified |
| `handle_name` | text | The display name of the YouTube channel as shown on the video page |
| `avatar_img_channel` | url | The URL of the avatar image of the YouTube channel |
| `is_sponsored` | boolean | Indicates whether the video contains a paid content overlay as declared by YouTube |
| `related_videos` | array | List of URLs of videos shown in the sidebar alongside the current video |
| `license` | url | URL of the video's license as declared in YouTube's video metadata |
| `viewport_frames` | text | Resolution of the primary video stream format, derived from YouTube's streaming data |
| `current_optimal_res` | text | Current and optimal video resolution with frame rate, from YouTube's streaming format metadata |
| `codecs` | text | Video and audio codec strings formatted as video codec and audio codec, extracted from YouTube's adaptive streaming formats |
| `color` | text | Color primaries of the video stream, extracted from YouTube's adaptive format color info |
| `quality` | text | Quality identifier of the first adaptive streaming format as reported by YouTube |
| `quality_label` | text | Human-readable video quality label as reported by YouTube |
| `post_type` | text | Type of YouTube content inferred from the URL structure. Possible values: post for standard video, short for YouTube Short, or N/A |
| `youtuber_id` | text | YouTube's internal channel ID, distinct from the channel handle |
| `transcript` | text | Full plain-text transcript of the video, compiled from YouTube's caption tracks. English captions are preferred, falls back to the first available language if English is unavailable |
| `formatted_transcript` | array | Timestamped transcript segments from YouTube's caption tracks, each containing start time, end time, and duration in milliseconds, and the caption text |
| `hashtags` | array | List of hashtags found in the video title or description, each with the hashtag text and its YouTube search link |
| `tags` | array | Tags of the video |
| `next_recommended_videos` | array | Videos shown as end-screen cards during the final seconds of the video, including timing in milliseconds and display style |
| `recommended_videos` | array | Videos recommended by YouTube in the sidebar alongside the current video |
| `transcript_language` | array | List of caption and transcript languages available for this video on YouTube, including whether each track was auto-generated |
| `chapters` | array | List of chapter markers defined by the creator, each with a title, start time in milliseconds, and preview image |
| `transcription_language` | text | The language code requested by the caller for transcript retrieval, passed as an input parameter at collection time |
| `is_age_restricted` | boolean | Whether the video is age-restricted, inferred from a non-OK playability status combined with an age-related reason from YouTube |
| `channel_url_decoded` | text | Plain-text percent-decoded version of the channel URL |
| `category` | text | YouTube's content category assigned to the video, from YouTube's predefined category taxonomy |
| `audio_tracks` | array | audio Tracks |
| `made_for_kids` | boolean | Indicates whether the video is designated as made for kids, inferred from the YouTube miniplayer playback mode |
| `player_notification_text` | text | User-facing notification text shown inside the video player |
| `ai_content_label` | boolean | Indicates whether the video has been labeled as AI-generated or significantly AI-altered, either by the creator or auto-detected by YouTube. |
| `live_status` | text | Livestream status of the video, equivalent to yt-dlp's live_status. One of "is_live", "was_live", or "not_live", parsed from YouTube's info string (e.g. "Streamed live 29 minutes ago") or defaulted to "not_live" for regular videos |
| `comments` | array | 10 Most relevant comments of the video |

</details>

<details>
<summary>All 21 channel fields, <code>gd_lk538t2k2p1k3oos71</code></summary>

| field | type | description |
| --- | --- | --- |
| `url` | url | URL that link directly to the YouTube profile |
| `handle` | text | Unique to each user (e.g., @name) |
| `handle_md5` | text | This field stores the MD5 hash of the handle field. |
| `banner_img` | url | URL that links to the banner photo |
| `profile_image` | url | URL that link to the profile picture |
| `name` | text | Profile name |
| `subscribers` | number | How many subscribers the profile have |
| `Description` | text | Brief descriptions or statements that users write to introduce themselves or share their interests and passions on YouTube |
| `videos_count` | number | How many videos the profile have |
| `created_date` | date | The date the profile was created |
| `views` | number | How many views the profile have |
| `Details` | object | channel Details |
| `Links` | array | External websites that users may link to from their YouTube profiles |
| `identifier` | text | identifier |
| `discovery_input` | object | Discovery input value |
| `id` | text | channel id |
| `has_podcast` | boolean | has podcast indicator |
| `top_videos` | array | top videos |
| `featured_video` | url | Featured Video |
| `featured_channels` | array | featured channels |
| `collaborations` | array | Collaborations videos |

</details>

<details>
<summary>All 16 comment fields, <code>gd_lk9q0ew71spt1mxywf</code></summary>

| field | type | description |
| --- | --- | --- |
| `comment_id` | text | Unique identifier for each comment |
| `comment_text` | text | The text content of the comment |
| `likes` | number | Number of likes received by the comment |
| `replies` | number | Number of replies to the comment |
| `username` | text | Username of the commenter |
| `username_md5` | text | This field stores the MD5 hash of the username field. |
| `user_channel` | text | URL of the commenter's YouTube channel |
| `date` | text | Date when the comment was posted |
| `url` | url | Web address of the YouTube video where the comment was posted |
| `video_id` | text | Unique identifier for the YouTube video |
| `replies_value` | array | Array of reply objects associated with this comment |
| `replies_without_names` | array | Array of reply objects with personally identifiable information (usernames) removed, containing only MD5 hashed user identifiers |
| `user_id` | text | Unique identifier for the commenter's YouTube channel |
| `mentioned_timestamps_minutes` | array | Array of timestamps mentioned in the comment, formatted in minutes (e.g., '2:35') |
| `mentioned_timestamps_seconds` | array | Array of timestamps mentioned in the comment, converted to total seconds |
| `date_iso` | date | Date in ISO format |

</details>
<!-- fields:end -->

<details>
<summary>The start of a real output file, from <code>youtube-scraper "python tutorial" --limit 1</code></summary>

```json
{
  "generated_at": "2026-11-09T11:11:27.087936+00:00",
  "keywords": [
    {
      "keyword": "python tutorial",
      "videos": [
        {
          "url": "https://www.youtube.com/watch?v=ix9cRaBkVe0&pp=ygUPcHl0aG9uIHR1dG9yaWFs",
          "title": "Python Full Course for free 🐍",
          "youtuber": "@BroCodez",
          "youtuber_md5": "70d4b03c4bfb5ad224f20557ab307492",
          "video_url": "https://rr2---sn-gjo-w43s.googlevideo.com/videoplayback?expire=1794244154&ei=2qnxavSNINSRr9gP69bsuAg&ip=198.171.211.118&id=o-AEkMpU30iXwNtnvbnAON2eG7AttyInlAGwwG01pqa8vk&source=youtube&requiressl=yes&xpc=EgVo2aDSNQ%3D%3D&met=1794222554%2C&mh=Zm&mm=18%2C29&mn=sn-gjo-w43s%2Csn-qjp5q5-5c&ms=aub%2Crdu&mv=m&mvi=2&pl=20&rms=aub%2Caub&pcm2=no&initcwndbps=4588250&spc=mpRQ_yRcDVkz9LJzvmLderwqwDBiIUMpTYdAB7VfYGkrZ1qHmjDsEg04x0RuWVnOkP6pff4&svpuc=1&ns=J3JNrNRnfM1v_ggVbplpJE8Z&sabr=1&rqh=1&mt=1794222100&fvip=1&epbp=1&keepalive=yes&fexp=51565115%2C52250119%2C52323638&c=WEB&n=CEJtyzpbOfeJMl3fqr&sparams=expire%2Cei%2Cip%2Cid%2Csource%2Crequiressl%2Cxpc%2Cpcm2%2Cspc%2Csvpuc%2Cns%2Csabr%2Crqh&sig=AE0s2JYwRAIhAMhhV5p8KVeGw4he3AkzCNLLYPzPT4t486MJRurbxitQAh8iv4sOa7TLD6KtHYWPeneTG-0mmYQpfhE6P1dDN5LT&lsparams=met%2Cmh%2Cmm%2Cmn%2Cms%2Cmv%2Cmvi%2Cpl%2Crms%2Cinitcwndbps&lsig=APaTxxMwRQIgArVc0ZpH7fcKdlGNogRr8Klbk5W446L1nRcJnl4t5ccCIQD1KIwxicqzTiGivwMcCr0H0bipJUkyHA3pAPC6IRw2NA%3D%3D",
          "video_length": 43200,
          "likes": 377299,
          "views": 13396410,
          "date_posted": "2024-08-20T13:00:54.000Z",
          "description": "#python #tutorial #beginners \nPython tutorial for beginners' full course 2024\n\n*Learn Python in 1 HOUR* ⏱ : https://www.youtube.com/watch?v=8KCuHHeC_M0\n*My original Python 12 Hour course* 🐍 :  https://www.youtube.com/watch?v=XKHEtdqhLK8\n*Full Python playlist* 📃: https://www.youtube.com/watch?v=Sg4GMVMdOPo&list=PLZPZq0r_RZOOkUQbat8LyQii36cJf2SWT\n\n                           [⭐ = project]\n#1   (00:00:00) python tutorial for beginners 🐍\n#2   (00:05:49) variables ❎\n#3   (00:16:05) type casting 💱\n#4   (00:21:15) user input ⌨️\n#5   (00:32:42) ⭐ madlibs game 📖\n#6   (00:37:55) arithmetic & math 📐\n#7   (00:51:46) if statements 🤔\n#8   (01:00:06) ⭐ calculator program 🧮\n#9   (01:05:59) ⭐ weight conversion program 🏋️\n#10 (01:09:59) ⭐ temperature conversion program 🌡️\n#11 (01:13:58) logical operators 🌦️\n#12 (01:21:28) conditional expressions ❓\n#13 (01:27:03) string methods 〰️\n#14 (01:39:08) string indexing ✂️\n#15 (01:46:35) format specifiers 💬\n#16 (01:51:55) while loops ♾️\n#17 (01:58:53) ⭐ compound interest calculator 💵\n#18 (02:06:28) for loops 🔁\n#19 (02:11:33) ⭐ countdown timer program ⌛\n#20 (02:17:28) nested loops ➿\n#21 (02:23:03) lists, sets, and tuples 🍎\n#22 (02:38:08) ⭐ shopping cart program 🛒\n#23 (02:45:21) 2D collections ⬜\n#24 (02:53:59) ⭐ quiz game 💯\n#25 (03:03:27) dictionaries 📙\n#26 (03:11:33) ⭐ concession stand program 🍿\n#27 (03:19:42) random numbers 🎲\n#28 (03:24:16) ⭐ number guessing game 🔢\n#29 (03:32:37) ⭐ rock, paper, scissors game 🗿\n#30 (03:42:06) ⭐ dice roller program ⚂\n#31 (03:52:12) functions 📞\n#32 (04:02:50) default arguments 👍\n#33 (04:08:56) keyword arguments 🗝️\n#34 (04:15:40) *args & **kwargs 📦\n#35 (04:30:33) iterables 🔂\n#36 (04:37:04) membership operators 🔎\n#37 (04:45:56) list comprehensions 📃\n#38 (04:56:17) match-case statements 📆\n#39 (05:02:13) modules 📨\n#40 (05:08:51) scope resolution 🔬\n#41 (05:14:22) if name == 'main': 📥\n#42 (05:23:34) ⭐ banking program 💰\n#43 (05:38:34) ⭐ slot machine 🎰\n#44 (05:58:45) ⭐ encryption program 🔐\n#45 (06:07:26) ⭐ hangman game 🕺\n#46 (06:32:32) python object oriented programming 🚗\n#47 (06:44:50) class variables 🎓\n#48 (06:53:06) inheritance 👨‍👦‍👦\n#49 (07:00:02) multiple inheritance 🐟\n#50 (07:08:04) super() 🔴\n#51 (07:21:10) polymorphism 🎭\n#52 (07:29:15) duck typing 🦆\n#53 (07:33:34) static methods ⚡\n#54 (07:39:31) class methods 🏫\n#55 (07:46:16) magic methods 🌟\n#56 (07:59:51) @property ⚙️\n#57 (08:07:33) decorators 🎊\n#58 (08:14:57) exception handling 🚦\n#59 (08:20:46) file detection 🕵️‍♂️\n#60 (08:27:47) writing files ✍\n#61 (08:41:33) reading files 🔍\n#62 (08:48:29) dates & times 📅\n#63 (08:54:46) ⭐ alarm clock ⏰\n#64 (09:05:03) multithreading 🧵\n#65 (09:13:45) request API data ↩️\n#66 (09:22:19) PyQt5 GUI intro 🖥️\n#67 (09:31:27) PyQt5 labels 🏷️\n#68 (09:40:23) PyQt5 images 📷\n#69 (09:46:28) PyQt5 layout managers 🧲\n#70 (09:53:07) PyQt5 buttons 🛎️\n#71 (10:00:12) PyQt5 checkboxes ✅\n#72 (10:06:42) PyQt5 radio buttons 🔘\n#73 (10:15:55) PyQt5 line edits 💬\n#74 (10:21:55) PyQt5 CSS styles 🎨\n#75 (10:32:48) ⭐ digital clock program 🕒\n#76 (10:48:38) ⭐ stopwatch program ⏱\n#77 (11:06:05) ⭐ weather API app ☀️\n\nPython Interpreter: https://www.python.org/\nPyCharm IDE: https://www.jetbrains.com/pycharm/\n\n*Copyright Disclaimer*:\nThis video is the intellectual property of Bro Code. All rights reserved. No part of this video may be reproduced, distributed, or transmitted in any form or by any means, including but not limited to recording, uploading, or other electronic or mechanical methods, without my written permission, except in the case of brief quotations embodied in critical reviews and certain other noncommercial uses permitted by copyright law.",
          "subscribers": 3440000,
          "music": {
            "song": "Block Party",
  ...
```

The whole file, one video with every field, is
[examples/sample_output.json](examples/sample_output.json).

</details>

## YouTube scraper errors

| you see | what it means |
| --- | --- |
| `API token required but not found.` | Exit 2, before any request. Set the token, or run `bdata login`. |
| `failed  'keyword': Parse error: ...` | Exit 1. Every video in that search hit a parsing bug in the scraper. On 9 Nov 2026 it read `ORIGINAL_LANGUAGE_TO_COUNTRY is not defined`, once `Cannot read properties of undefined (reading 'runs')`. Run it again, or use a different keyword. |
| `got     'keyword': 1 videos, 1 error rows: Parse error: ...` | Exit 0. The same bug hit some of the videos; the rest are in the file. |
| `failed  'keyword': timeout: snapshot ... not ready after 900s` | Exit 1. Run it again, or fetch the snapshot later with `fetch()`. |
| `failed  'keyword': HTTP 401: ...` | The token is set but wrong. |

Any failure exits 1, so a run is safe to gate a script on.

From the functions, the same conditions look like this:

| you see | what it means |
| --- | --- |
| `TokenMissing` | No `BRIGHTDATA_API_TOKEN` and no `bdata login`. |
| `ApiError: HTTP 400: ...validation_error...` | An input the API does not accept, such as a filter label not on its list. The message names the field. |
| a row with an `error` key | The API's answer for one video or input: `parse_error`, or a dead page. The other rows are fine. |
| `TimeoutError` | The job outlived the 900-second wait. Pass `timeout=` to `run`, or use `trigger` and fetch later. |

## YouTube MCP server and Claude Code skill

No Python, nothing installed. Paste both lines; the first opens a browser
once, or use `bdata login --device` over SSH and in CI:

```bash
npx -p @brightdata/cli bdata login
npx -p @brightdata/cli bdata pipelines run gd_lk538t2k2p1k3oos71 collect_by_url "https://www.youtube.com/@NASA/about" --pretty
```

1 record, 20 fields, 35 seconds on 9 Nov 2026. The CLI leaves out fields that
are null.

The CLI runs a scraper by its dataset ID, every YouTube one included.
`bdata pipelines search youtube` lists their IDs and methods, and
`--limit-per-input N` caps a discovery, 10 by default.

`npx skills add brightdata/skills` teaches Claude Code, Cursor and Codex these
commands and the docs, so plain language works afterwards. Full guide:
[Bright Data for your coding agent](https://docs.brightdata.com/quickstart-coding-agent).

No terminal, for a hosted assistant? The
[Bright Data MCP server](https://github.com/brightdata/brightdata-mcp#which-tool-to-use)
runs any pre-built scraper, YouTube included, through `search_scrapers` and
`run_scraper` in its `scrapers` group:

    https://mcp.brightdata.com/mcp?token=YOUR_API_TOKEN&groups=scrapers

An agent can also open the account itself, no signup form:
[agent registration](https://brightdata.com/auth.md). Everything else Bright
Data connects to, from LangChain to Zapier and n8n:
[integrations](https://docs.brightdata.com/integrations/introduction).

<details>
<summary>YouTube commands for the CLI, each run on 9 Nov 2026</summary>

Prefix each command with `npx -p @brightdata/cli`, or install once with
`npm i -g @brightdata/cli`. Each prints JSON and is billed per record.

Three scrapers, each run with `bdata pipelines run <dataset_id> <method>`:
videos `gd_lk56epmy2i5g7lzu0k`, channels `gd_lk538t2k2p1k3oos71` and
comments `gd_lk9q0ew71spt1mxywf`.

```bash
bdata pipelines run gd_lk9q0ew71spt1mxywf collect_by_url --url "https://www.youtube.com/watch?v=jNQXAC9IVRw" --num_of_comments 3 --format csv -o comments.csv
```

3 comments, 24 columns, 37 seconds.

```bash
bdata pipelines run gd_lk56epmy2i5g7lzu0k discover_by_keyword --keyword "python tutorial" --num_of_posts 2 --limit-per-input 2 --timeout 900 --pretty
```

2 rows in 599 seconds: one video and one row with the parse error described
under [YouTube scraper errors](#youtube-scraper-errors). Discovery can pass the
CLI's 600-second default, so keep `--timeout 900`, or add `--async` and fetch
later with `bdata pipelines results <snapshot_id>`.

`bdata pipelines info <dataset_id> <method>` shows a scraper's input fields.
`bdata pipelines run --help` shows `--format json|csv|ndjson|jsonl`, `-o FILE`,
`--timeout` and `--async`.

</details>

## Is this YouTube scraper free?

New Bright Data accounts get
[5,000 free credits a month](https://docs.brightdata.com/general/account/billing-and-pricing/free-tier).
Every YouTube scraper bills per record: per video, channel or comment.
[Pricing](https://brightdata.com/pricing/web-scraper) lists the rates.

## Support

Bugs in this repo:
[open an issue](https://github.com/brightdata/youtube-scraper/issues), and
[CONTRIBUTING.md](CONTRIBUTING.md) says what to put in it.
Anything about the API, your account or your credits:
[Bright Data support](https://brightdata.zendesk.com/hc/en-us/requests/new).

## License

[Apache 2.0](LICENSE).

## YouTube scraper for Node.js

The same YouTube scraper is available for Node.js: [brightdata/youtube-scraper-node](https://github.com/brightdata/youtube-scraper-node).

## More open source scrapers from Bright Data

Other Python scrapers built the same way, with live-verified examples:

- [TikTok scraper for Python](https://github.com/brightdata/tiktok-scraper)
- [Instagram scraper for Python](https://github.com/brightdata/instagram-scraper)
- [ChatGPT scraper for Python](https://github.com/brightdata/chatgpt-scraper)
