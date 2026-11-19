"""The plugin's pages, under Manage alone: the data role's common pages
(spec/plugin-pages-follow-their-role), Connection and Datasets, in its
order, each also a read tool for agents on the deployment's MCP under the
role's names (`read_connection`, `read_datasets`). Each record is the
role's (`meridian.roles.data`), extended with the Riksbank's fields;
each template is the role's, with the Riksbank's nuance at its blocks only, as
plugin-ecb's are.

A data plugin shows its connectivity, its data subscriptions and how its
entitlements resolve, and no market data (the product owner, 2026-10-03):

- **Connection** (`/`): "Key" -- the mode (Live or Sample data), "No key
  needed", what the Riksbank serves; "Limits and use" -- its limits without
  a key, the requests made, the last check and error; "Stream": it does not
  stream. Then a tab of its own (`?tab=sources`), **Sources**, one line per
  source -- the rates, the government bonds and the exchange rates: its
  state, the latest day read, its calls, its last error, and in its detail
  where it reads and whether its answers are kept.
- **Datasets** (`/datasets`): "Served", "Wants" and "Subjects", each with
  the three datasets; then a tab of its own (`?tab=records`), **Records**:
  each record and currency, with its convention and the deployment's
  instrument for it or why there is none -- one line a row, searched and paged
  by the kit's om-pager to fit one screen.

Neither shows a rate or a level: those are the reading roles' to show.
"""

from __future__ import annotations

from datetime import UTC, date, datetime
from pathlib import Path
from typing import Any

import meridian
from meridian.roles import data

from . import records
from .declared import CATALOGUE
from .feed import DATASETS, Feed, SourceStatus, Status
from .portal import BASE, CURVES, FX, RATES, SOURCES, SWEA, SWESTR_API
from .series import AVERAGE_RECORDS, BONDS_RECORD, INDEX_RECORD, NOT_CARRIED, POLICY_RECORD

TITLE = "Riksbank"
#: The kit these pages are built on: 0.12.0's "Facts" and "Next step".
KIT = "0.12.0"

pages = meridian.Pages(TITLE, templates=Path(__file__).parent / "templates", kit=KIT)

CONNECTION = "/"
DATASETS_PAGE = "/datasets"

MOST_QUERY = 100
CONNECTION_TABS = {"connection": "Connection", "sources": "Sources"}
TABS = {"served": "Served", "records": "Records"}
#: The attribution the Riksbank's terms ask for.
ATTRIBUTION = (
    "Source: Sveriges Riksbank. SWESTR is administered by Sveriges Riksbank. Government bond "
    "yields: Refinitiv, via the Riksbank."
)
SOURCE_NAMES = {
    RATES: "SWESTR, its averages and index, and the policy rate",
    CURVES: "Government bond yields",
    FX: "Exchange rates against the krona",
}
SHORT_NAMES = {RATES: "Rates", CURVES: "Bond yields", FX: "Exchange rates"}
PUBLISHED = {
    RATES: "SWESTR at 09:00 the next banking day, its averages and index at 09:05",
    CURVES: "the next banking day from about 09:10",
    FX: "each banking day at 16:15",
}
#: Whether a source's answers are kept, as Sources says it.
KEPT = {
    RATES: "Pushed as published; each answer kept",
    CURVES: "Read only when the lake wants a day; served, not kept: no answer kept",
    FX: "Pushed as published; each answer kept",
}
CONVENTIONS = {
    "rates": "actual/360, simple, as SWESTR's framework states it",
    "average": "actual/360, compounded over the period, as SWESTR's framework states it",
    "index": "an index level, based 1 September 2021 = 100, actual/360, as the Riksbank states",
    "policy": "actual/360, simple: the plugin's statement; the Riksbank states per cent",
    CURVES: "annual, 30E/360: the plugin's statement, the Debt Office's convention",
    FX: "kronor per unit of the currency, as the Riksbank states it",
}

_held: dict[str, Any] = {}


def hold(feed: Feed) -> None:
    """The feed the pages read, once the plugin has registered."""
    _held["feed"] = feed


def _status() -> tuple[Status, Feed | None]:
    feed: Feed | None = _held.get("feed")
    return (feed.status if feed is not None else Status(), feed)


def _iso(moment: datetime | None) -> str:
    return moment.astimezone(UTC).isoformat(timespec="seconds") if moment else ""


def _day(day: date | None) -> str:
    return day.isoformat() if day else ""


def _source_state(held: SourceStatus, mode: str) -> str:
    if held.error and held.read_at is None:
        return "Not answering"
    if held.read_at is None and held.source == CURVES:
        return "Pulled when wanted"
    if held.error:
        return "Answering"
    if held.read_at is None:
        return "Checking the Riksbank"
    return "Sample data" if mode == "synthetic" else "Answering"


def _state(status: Status) -> tuple[str, str, str]:
    """The head's status: its state, what it means, and its detail."""
    error = status.error
    if error and not status.read:
        return "error", "Not answering", error
    if error:
        return "warn", "Answering", error
    if not status.read:
        return "busy", "Checking the Riksbank", ""
    misses = [h.code for h in [*status.records.values(), *status.currencies.values()] if h.miss]
    if misses:
        plural = "record" if len(misses) == 1 else "records"
        more = ", …" if len(misses) > 6 else ""
        return "warn", f"{len(misses)} {plural} not held", ", ".join(sorted(misses)[:6]) + more
    if status.mode == "synthetic":
        return "ok", "Sample data", ""
    return "ok", "Answering", ""


def _source(source: str, status: Status, instance: str) -> records.SourceRead:
    held = status.sources[source]
    return records.SourceRead(
        source=SOURCE_NAMES[source],
        dataset=f"{instance}:{DATASETS[source]}",
        kind=source,
        state=_source_state(held, status.mode),
        last_release=_day(held.latest_day),
        calls=held.fetches,
        last_error=held.error,
        reads=(
            "The answer recorded on 2026-11-19, committed with the plugin"
            if status.mode == "synthetic"
            else BASE + (SWEA if source != RATES else f"{SWESTR_API} and {SWEA}")
        ),
        history=f"Published {PUBLISHED[source]}; {KEPT[source]}",
    )


def connection_read(status: Status, feed: Feed | None) -> records.ConnectionRead:
    state, said, _ = _state(status)
    kept = feed.raw.keys() if feed is not None else []
    window = ""
    if feed is not None and feed.raw.granted:
        window = "in the storage the deployment grants, as its responses settings say"
    elif feed is not None:
        window = "in a directory of the plugin's own: this deployment grants no storage"
    instance = feed.plugin.identity.instance_id if feed is not None else "riksbank"
    answered = status.read or status.mode == "synthetic"
    return records.ConnectionRead(
        mode="Sample data" if status.mode == "synthetic" else "Live",
        credentials=[],
        entitled_at_vendor=(
            "SWESTR, its averages and index, the policy rate, the government bond yields "
            "and the exchange rates: no key"
            if answered
            else ""
        ),
        limit=(
            "5 calls a minute and 1,000 a day without a key; the plugin asks one request at a "
            "time, at most one every 13 seconds, and checks every hour: some 216 a day"
        ),
        calls=status.fetches,
        last_call_at=_iso(status.checked_at),
        last_error=status.error,
        sessions=None,
        state=state,
        said=said,
        source=(
            "The answers recorded on 2026-11-19, committed with the plugin"
            if status.mode == "synthetic"
            else f"{BASE}: the SWESTR and SWEA APIs"
        ),
        checked_at=_iso(status.checked_at),
        sources=[_source(source, status, instance) for source in SOURCES],
        responses_kept=len(kept),
        kept_for=window,
    )


def _record_dataset(code: str) -> tuple[str, str, str]:
    """A record's dataset, what it is recorded as, and its convention."""
    if code == BONDS_RECORD.code:
        return DATASETS[CURVES], "benchmark yields at 2, 5, 7 and 10 years", CONVENTIONS[CURVES]
    if code == INDEX_RECORD.code:
        return DATASETS[RATES], "index levels", CONVENTIONS["index"]
    if code in {r.code for r in AVERAGE_RECORDS.values()}:
        return DATASETS[RATES], "averages", CONVENTIONS["average"]
    if code == POLICY_RECORD.code:
        return DATASETS[RATES], "fixings", CONVENTIONS["policy"]
    return DATASETS[RATES], "fixings, with volume and transactions", CONVENTIONS["rates"]


def datasets_read(status: Status, feed: Feed | None) -> records.DatasetsRead:
    instance = feed.plugin.identity.instance_id if feed is not None else "riksbank"
    answered = status.read or status.mode == "synthetic"
    served = data.served(
        CATALOGUE,
        instance,
        feed.wants if feed is not None else None,
        "Yes: no key needed" if answered else "Not asked yet",
    )
    rows = [
        records.RecordRead(
            code=h.code,
            name=h.name,
            dataset=_record_dataset(h.code)[0],
            recorded_as=_record_dataset(h.code)[1],
            convention=_record_dataset(h.code)[2],
            instrument_id=h.instrument_id,
            miss=h.miss,
            latest_day=_day(h.latest_day),
        )
        for h in status.records.values()
    ]
    rows += [
        records.RecordRead(
            code=h.code,
            name=h.name,
            dataset=DATASETS[FX],
            recorded_as="its price in SEK, a close",
            convention=CONVENTIONS[FX],
            instrument_id=h.instrument_id,
            miss=h.miss.replace("_", " "),
            latest_day=_day(h.latest_day),
        )
        for h in sorted(status.currencies.values(), key=lambda c: c.code)
    ]
    rows += [
        records.RecordRead(
            code=held,
            name=why,
            dataset=DATASETS[CURVES] if held == "SE TB" else DATASETS[RATES],
            recorded_as="not carried",
            convention="",
            instrument_id="",
            miss="not carried",
        )
        for held, why in NOT_CARRIED.items()
        if status.records
    ]
    return records.DatasetsRead(
        served=served,
        wants=list(data.want_rows(feed.wants)) if feed is not None else [],
        reads_instruments=True,
        attribution=ATTRIBUTION,
        records=rows,
        unread=[
            f"{line} ({n} reads)"
            for held in status.sources.values()
            for line, n in sorted(held.unread.items())
        ],
    )


def figures(status: Status, feed: Feed | None) -> list[meridian.Figure]:
    """The data role's figures, in its order (`meridian.roles.data`); the
    Riksbank's plugin reports none of its own."""
    state, said, why = _state(status)
    if status.mode == "synthetic" and state == "ok":
        connection: Any = "Sample data"
    elif said == "Not answering":
        connection = meridian.Figure("", said, state="error", why=why[:200])
    else:
        error = status.error
        connection = meridian.Figure(
            "", "Answering", state="warn" if error else None, why=error[:200]
        )
    last = feed.wants.counts.last_ns if feed is not None else 0
    return data.figures(
        connection=connection,
        entitled_at_vendor=f"{len(CATALOGUE)} of {len(CATALOGUE)} datasets",
        stream="Does not stream",
        last_recorded=(datetime.fromtimestamp(last / 10**9, UTC) if last else None),
    )


def _moment(value: str) -> str:
    """An ISO moment as a person reads it, to the minute in UTC."""
    if not value:
        return ""
    if len(value) == 10:
        return value
    return datetime.fromisoformat(value).astimezone(UTC).strftime("%Y-%m-%d %H:%M UTC")


def _weekday(value: str) -> str:
    return date.fromisoformat(value).strftime("%a %d %b %Y") if value else ""


def matching(query: str, *texts: str) -> bool:
    """Whether every word of a search is in one of `texts`, case aside."""
    words = query.lower().split()
    held = " ".join(texts).lower()
    return all(word in held for word in words)


pages.environment.filters["moment"] = _moment
pages.environment.filters["day"] = _weekday


@pages.page(
    CONNECTION,
    "Connection",
    levels="admin",
    answers=records.ConnectionRead,
    name="read_connection",
    description=(
        "How this plugin reaches the Riksbank's SWESTR and SWEA APIs, as every data plugin's "
        "Connection answers it: the mode (Live or Sample data), no key needed, what the "
        "Riksbank serves, its limits and the requests made, the last check and why it failed "
        "if it did; it does not stream. Then the Riksbank's own: each source -- the rates, "
        "the government bond yields and the exchange rates -- with its state, the latest day "
        "read, its calls and last error, and whether its answers are kept; and how many "
        "answers are kept. No rate."
    ),
)
async def connection(request: meridian.Request) -> meridian.Response:
    status, feed = _status()
    read = connection_read(status, feed)
    tab = request.query.get("tab", "connection")
    return pages.answer(
        "connection.html",
        read,
        detail=_state(status)[2],
        # Named apart from the SDK's own `tab` and `tabs` (0.32.3), which
        # would draw the data role's section row in their place.
        view=tab if tab in CONNECTION_TABS else "connection",
        views=CONNECTION_TABS,
        short=SHORT_NAMES,
    )


@pages.page(
    DATASETS_PAGE,
    "Datasets",
    levels="admin",
    answers=records.DatasetsRead,
    name="read_datasets",
    description=(
        "What this plugin serves the lake, as every data plugin's Datasets answers it: its "
        "three datasets as the catalogue declares them (SWESTR, its averages and index and "
        "the policy rate; the government bond yields, served, not kept; the exchange rates "
        "against the krona, prices), whether a deployment admin has licensed each, what it "
        "recorded and declined; the standing wants it keeps current and the wants it "
        "answered. Then the Riksbank's own: the attribution its terms ask for, and each "
        "record and currency with its convention and the deployment's instrument for it or "
        "why there is none. No rate."
    ),
)
async def datasets(request: meridian.Request) -> meridian.Response:
    status, feed = _status()
    read = datasets_read(status, feed)
    # A browser draws one tab, its search narrowing the records drawn; a
    # tool answers every tab.
    query = request.query.get("q", "").strip()[:MOST_QUERY]
    tab = request.query.get("tab", "served")
    tab = "records" if query else tab if tab in TABS else "served"
    shown = [r for r in read.records if matching(query, r.code, r.name, r.dataset)]
    return pages.answer(
        "datasets.html",
        read,
        query=query,
        tab=tab,
        tabs=TABS,
        shown=shown,
        state=_state(status),
        checked_at=_iso(status.checked_at),
    )
