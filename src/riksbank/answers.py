"""The Riksbank's answers, read as the Riksbank wrote them.

Both its APIs answer JSON, a list of objects, one a day:

- **SWESTR** (`/swestr/v1/SWESTR`): `rate`, `date` (the day the rate is
  for), `volume` (SEK millions), `numberOfTransactions`, `publicationTime`
  (UTC), and more not read here;
- **its averages** (`/swestr/v1/avg/<id>`): `rate`, `date`, `startDate`,
  `publicationTime`;
- **its index** (`/swestr/v1/index/<id>`): `value`, `date`,
  `publicationTime`;
- **SWEA's observations** (`/swea/v1/Observations/<series>/...`): `date` and
  `value`; and its latest by group (`/swea/v1/Observations/Latest/ByGroup/
  <group>`) each with its `seriesId` too.

A number is read as the text the Riksbank wrote -- the JSON parsed with each
number kept as its text -- and as a `Decimal` from it, never a float. A
value that is null or missing is no value, never a zero; one that does not
read is kept as not read, and never recorded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from datetime import date, datetime
from decimal import Decimal, InvalidOperation
from typing import Any


class NotRead(Exception):  # noqa: N818 - what the answer was not
    """An answer that is not what was asked for."""


@dataclass(frozen=True)
class Observation:
    """One value as the Riksbank stated it: its series, day and text; when it
    was published, its volume and its number of transactions where stated;
    and the key in storage of the answer it was read from."""

    series: str
    day: date
    text: str
    published: str = ""
    volume: str = ""
    transactions: str = ""
    key: str = ""

    @property
    def value(self) -> Decimal:
        return Decimal(self.text)

    @property
    def published_ns(self) -> int:
        """Its publication time in nanoseconds, 0 where none is stated."""
        if not self.published:
            return 0
        try:
            moment = datetime.fromisoformat(self.published.replace("Z", "+00:00"))
        except ValueError:
            return 0
        if moment.tzinfo is None:
            return 0
        return int(moment.timestamp()) * 1_000_000_000


@dataclass
class Observations:
    """An answer, or several, read: its values in order, and the values that
    did not read."""

    source: str
    observations: list[Observation] = field(default_factory=list)
    unread: list[str] = field(default_factory=list)

    @property
    def days(self) -> list[date]:
        return sorted({o.day for o in self.observations})

    def on(self, day: date) -> dict[str, Observation]:
        return {o.series: o for o in self.observations if o.day == day}

    def add(self, other: Observations) -> None:
        self.observations += other.observations
        self.unread += other.unread
        self.observations.sort(key=lambda o: (o.series, o.day))


def _number(text: str) -> bool:
    try:
        return Decimal(text).is_finite()
    except InvalidOperation:
        return False


def _text(value: Any) -> str:
    return value.strip() if isinstance(value, str) else ""


def parse(text: str, source: str, series: str = "", key: str = "") -> Observations:
    """One answer of either API, read; its series `series`, or each object's
    `seriesId` where it names one. NotRead where it is not a list of days."""
    read = Observations(source)
    if not text.strip():
        return read
    try:
        held = json.loads(text, parse_float=str, parse_int=str)
    except ValueError as failed:
        raise NotRead(f"the answer is not the Riksbank's JSON: {text[:80]!r}") from failed
    if not isinstance(held, list):
        raise NotRead(f"the answer is not a list of days: {text[:80]!r}")
    for item in held:
        if not isinstance(item, dict):
            read.unread.append(f"{series or source}: an item {str(item)[:40]!r}")
            continue
        name = _text(item.get("seriesId")) or series
        try:
            day = date.fromisoformat(_text(item.get("date")))
        except ValueError:
            read.unread.append(f"{name}: a day {str(item.get('date'))[:20]!r}")
            continue
        said = item.get("rate", item.get("value"))
        if said is None:
            continue
        stated = _text(said)
        if not _number(stated):
            read.unread.append(f"{name} {day}: {str(said)[:40]!r}")
            continue
        volume = _text(item.get("volume"))
        transactions = _text(item.get("numberOfTransactions"))
        read.observations.append(
            Observation(
                name,
                day,
                stated,
                published=_text(item.get("publicationTime")),
                volume=volume if _number(volume) else "",
                transactions=transactions if transactions.isdigit() else "",
                key=key,
            )
        )
    read.observations.sort(key=lambda o: (o.series, o.day))
    return read
