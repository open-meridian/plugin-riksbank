"""The Riksbank's two public APIs, SWEA and SWESTR, at api.riksbank.se, and
their stand-in.

These requests are made, and nothing else, each one series:

- SWESTR, its averages and its index for a range of days --
  `/swestr/v1/SWESTR?fromDate=2026-11-09&toDate=2026-11-19`,
  `/swestr/v1/avg/SWESTRAVG1W?...`, `/swestr/v1/index/SWESTRINDEX?...`;
- the policy rate, a government bond's yield or a currency's rate for a
  range of days -- `/swea/v1/Observations/SECBREPOEFF/2026-11-09/2026-11-19`;
  the bonds' only when the lake wants them;
- the exchange rates' latest, every currency in one answer --
  `/swea/v1/Observations/Latest/ByGroup/130`.

Read from the Riksbank itself: no key, no account. Without a key the API
answers 5 calls a minute and 1,000 a day from one address (the Riksbank's
FAQ, docs/terms.md), so the plugin asks one request at a time, at most one
every 13 seconds, says who it is in its User-Agent, and checks hourly: the
rates' current range (eight requests) and the exchange rates' latest (one),
some 216 requests a day.

`SyntheticPortal` answers from the real responses committed under
responses/ (responses/index.json), recorded on 2026-11-19: each series'
answer from 3 August to 19 November 2026, and the exchange rates' latest. A
range is answered with the recorded days in it, each as the Riksbank wrote
it, and the rates' current range ends on its recording's last day whatever
the clock says, so the plugin's tests and its e2e run on it, offline, the
same on any day.
"""

from __future__ import annotations

import asyncio
import gzip
import json
import re
import time
import urllib.error
import urllib.request
from collections.abc import Callable
from dataclasses import dataclass
from datetime import UTC, date, datetime, timedelta
from importlib import resources
from typing import Protocol

from .series import AVERAGES, FX_GROUP, SWESTR, SWESTR_INDEX

BASE = "https://api.riksbank.se"
RATES, CURVES, FX = "rates", "curves", "fx"
SOURCES = (RATES, CURVES, FX)
#: Where each API is.
SWEA, SWESTR_API = "/swea/v1/", "/swestr/v1/"
LATEST = f"{SWEA}Observations/Latest/ByGroup/{FX_GROUP}"
USER_AGENT = "meridian-riksbank (+https://github.com/open-meridian/plugin-riksbank)"
#: Without a key, five calls a minute: one every 13 seconds.
SPACING = 13.0
TIMEOUT = 60.0
#: The most an answer may be: a year of one series is some 30 kB.
MOST_BYTES = 8 * 1024 * 1024
#: How far the rates' current range reaches back: ten days.
CURRENT_DAYS = 10

_OBSERVATIONS = re.compile(
    r"^/swea/v1/Observations/([A-Z0-9_]+)/(\d{4}-\d\d-\d\d)/(\d{4}-\d\d-\d\d)$"
)
_SWESTR = re.compile(
    r"^/swestr/v1/(?:avg/|index/)?([A-Z0-9]+)\?fromDate=(\d{4}-\d\d-\d\d)&toDate=(\d{4}-\d\d-\d\d)$"
)
_OBJECT = re.compile(r"\{[^{}]*\}")
_DATE = re.compile(r'"date":"(\d{4}-\d\d-\d\d)"')


def path_for(series: str, start: date, end: date) -> str:
    """The address of one series' values from `start` to `end`."""
    if series == SWESTR:
        return f"{SWESTR_API}{series}?fromDate={start}&toDate={end}"
    if series in AVERAGES:
        return f"{SWESTR_API}avg/{series}?fromDate={start}&toDate={end}"
    if series == SWESTR_INDEX:
        return f"{SWESTR_API}index/{series}?fromDate={start}&toDate={end}"
    return f"{SWEA}Observations/{series}/{start}/{end}"


def asked(path: str) -> tuple[str, date, date] | None:
    """The series and range an address asks, or None for the latest's or
    another's."""
    found = _OBSERVATIONS.match(path) or _SWESTR.match(path)
    if found is None:
        return None
    return found.group(1), date.fromisoformat(found.group(2)), date.fromisoformat(found.group(3))


class PortalUnreachable(Exception):  # noqa: N818 - what the Riksbank's API was
    """The API could not be asked: no answer, or not in time."""


@dataclass(frozen=True)
class Fetched:
    """One answer, as received."""

    path: str
    status: int
    body: bytes
    fetched_at: datetime
    date: str = ""

    @property
    def url(self) -> str:
        return BASE + self.path

    @property
    def text(self) -> str:
        return self.body.decode("utf-8", errors="replace")


class Portal(Protocol):
    mode: str

    def current(self, today: date) -> tuple[date, date]: ...

    async def get(self, path: str) -> Fetched: ...


def utc_now() -> datetime:
    return datetime.now(UTC)


class LivePortal:
    """The Riksbank's API itself."""

    mode = "live"

    def __init__(self, now: Callable[[], datetime] = utc_now) -> None:
        self._now = now
        self._lock = asyncio.Lock()
        self._last = 0.0

    def current(self, today: date) -> tuple[date, date]:
        return today - timedelta(days=CURRENT_DAYS), today

    async def get(self, path: str) -> Fetched:
        async with self._lock:
            wait = self._last + SPACING - time.monotonic()
            if wait > 0:
                await asyncio.sleep(wait)
            try:
                return await asyncio.to_thread(self._get, path)
            finally:
                self._last = time.monotonic()

    def _get(self, path: str) -> Fetched:
        request = urllib.request.Request(
            BASE + path, headers={"User-Agent": USER_AGENT, "Accept": "application/json"}
        )
        try:
            with urllib.request.urlopen(request, timeout=TIMEOUT) as answer:  # noqa: S310 - the Riksbank's https address
                body = answer.read(MOST_BYTES + 1)
                status = answer.status
                said = answer.headers
        except urllib.error.HTTPError as refused:
            body = refused.read(MOST_BYTES + 1) if refused.fp else b""
            status, said = refused.code, refused.headers
        except (urllib.error.URLError, TimeoutError, OSError) as failed:
            reason = getattr(failed, "reason", failed)
            raise PortalUnreachable(f"{BASE}{path[:80]}: {type(reason).__name__}") from failed
        if len(body) > MOST_BYTES:
            raise PortalUnreachable(f"{BASE}{path[:80]}: answered more than {MOST_BYTES} bytes")
        return Fetched(path, status, body, self._now(), date=said.get("Date", "") if said else "")


@dataclass(frozen=True)
class Recording:
    """One source's recorded answers, each series' as the Riksbank wrote it,
    under its Date, and the recording's last day."""

    answers: dict[str, str]
    said: str
    last_day: date


class SyntheticPortal:
    """The responses committed under responses/: each range answered with
    the recorded days in it, under its recording's Date."""

    mode = "synthetic"

    def __init__(self, now: Callable[[], datetime] = utc_now) -> None:
        self._now = now
        held = resources.files(__package__).joinpath("responses")
        index = json.loads(held.joinpath("index.json").read_text(encoding="utf-8"))
        self.recordings: dict[str, Recording] = {}
        for source in SOURCES:
            answers = json.loads(gzip.decompress(held.joinpath(index[source]["file"]).read_bytes()))
            self.recordings[source] = Recording(
                {str(k): str(v) for k, v in answers.items()},
                str(index[source]["date"]),
                date.fromisoformat(index[source]["last_day"]),
            )
        self.asked: list[str] = []

    def current(self, today: date) -> tuple[date, date]:
        last = self.recordings[RATES].last_day
        return last - timedelta(days=CURRENT_DAYS), last

    async def get(self, path: str) -> Fetched:
        self.asked.append(path)
        if path == LATEST:
            recording = self.recordings[FX]
            return Fetched(
                path, 200, recording.answers["latest"].encode(), self._now(), recording.said
            )
        found = asked(path)
        held = next((r for r in self.recordings.values() if found and found[0] in r.answers), None)
        if found is None or held is None:
            return Fetched(path, 404, b"Resource not found", self._now())
        series, start, end = found
        body = within(held.answers[series], start, end)
        return Fetched(path, 200, body.encode(), self._now(), held.said)


def within(text: str, start: date, end: date) -> str:
    """A recorded answer's days from `start` to `end`, each object as the
    Riksbank wrote it."""
    kept = []
    for one in _OBJECT.findall(text):
        day = _DATE.search(one)
        if day and start <= date.fromisoformat(day.group(1)) <= end:
            kept.append(one)
    return "[" + ",".join(kept) + "]"


def portal(synthetic: bool, now: Callable[[], datetime] = utc_now) -> Portal:
    return SyntheticPortal(now) if synthetic else LivePortal(now)
