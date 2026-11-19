"""The pages on sample data, each printed as one HTML file:
for looking at them without a deployment.

    python -m riksbank.preview connection > preview/connection.html

The plugin's work runs on the SDK's suite recorder in place of a sidecar --
SWESTR's record, the bonds' and every currency resolved, every other record
to none (so the "not held" state shows), every batch recorded -- against
the answers committed under responses/, at 22:00 UTC on 19 November 2026:
the rates' current range and the exchange rates' latest read; wants for
SWESTR of 1 October and the bonds of 18 November answered, and one for a
Sunday declined. `connection-sources` and `datasets-records` are each
page's second tab; `connection-first` and `datasets-first` the pages before
the first check.
"""

from __future__ import annotations

import asyncio
import sys
from datetime import UTC, datetime

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.receive import Heard
from meridian.suites import Recorder
from meridian.testing import PageClient

from .feed import Feed
from .page import CONNECTION, DATASETS_PAGE, hold, pages
from .portal import SyntheticPortal
from .raw import RawStore

AT = datetime(2026, 11, 19, 22, 0, tzinfo=UTC)
PAGES = {
    "connection": CONNECTION,
    "connection-sources": CONNECTION,
    "datasets": DATASETS_PAGE,
    "datasets-records": DATASETS_PAGE,
    "datasets-search": DATASETS_PAGE,
    "connection-first": CONNECTION,
    "datasets-first": DATASETS_PAGE,
}
TABS = {"connection-sources": "sources", "datasets-records": "records"}
SEARCHED = "dollar"
SWESTR_ID, BONDS_ID = "LCL-SWESTR", "LCL-SEGVB"
HELD = {"SWESTR": SWESTR_ID, "SE GVB": BONDS_ID}


def _want(
    want_id: str, day: str, subject: str = SWESTR_ID, dataset: str = "riksbank_rates"
) -> Heard:  # type: ignore[type-arg]
    return Heard(
        row="ObservationsWanted",
        message=ops.ObservationsWantedEvent(
            want_id=want_id,
            dataset=f"riksbank:{dataset}",
            data_type="meridian.v1.Price" if dataset == "riksbank_fx" else "meridian.v1.Rate",
            subjects=[ops.SubjectRef(entity_id=subject)],
            business_date=day,
        ),
    )


def _feed() -> Feed:
    recorder = Recorder("riksbank")

    def resolved(params: ops.ResolveIdentifierParams) -> ops.ResolveIdentifierResult:
        named = params.identifiers[0]
        if named.scheme == "iso4217":
            return ops.ResolveIdentifierResult(found=True, instrument_id=f"LCL-{named.value}")
        if named.value in HELD:
            return ops.ResolveIdentifierResult(found=True, instrument_id=HELD[named.value])
        return ops.ResolveIdentifierResult(found=False, miss_reason=ops.MISS_REASON_NOT_FOUND)

    recorder.answer("ResolveIdentifier", resolved)
    return recorder.bind(Feed(SyntheticPortal(lambda: AT), RawStore(), now=lambda: AT))


async def synthetic_feed() -> Feed:
    feed = _feed()
    await feed.check()
    await feed.on_observations_wanted(_want("want-1001", "2026-10-01"))
    await feed.on_observations_wanted(_want("want-1004", "2026-10-04"))
    await feed.on_observations_wanted(_want("want-1118", "2026-11-18", BONDS_ID, "riksbank_curves"))
    return feed


def render(page: str) -> str:
    feed = _feed() if page.endswith("-first") else asyncio.run(synthetic_feed())
    hold(feed)
    query = {"q": SEARCHED} if page == "datasets-search" else {}
    if page in TABS:
        query = {"tab": TABS[page]}
    answer = PageClient(pages).get(PAGES[page], "admin", **query)
    if answer.status != 200:
        raise SystemExit(f"{page} answered {answer.status}: {answer.text[:200]}")
    return answer.text


def main() -> None:
    page = sys.argv[1] if len(sys.argv) > 1 else "connection"
    if page not in PAGES:
        raise SystemExit(f"no page {page!r}: {', '.join(PAGES)}")
    sys.stdout.write(render(page))


if __name__ == "__main__":
    main()
