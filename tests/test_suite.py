"""The data suite (meridian.suites), each case the Riksbank's series present
mapped to the plugin's own conversion of the Riksbank's recorded answers,
the whole suite passing.

Presented: the exchange rates' price cases (each a close of the currency's
cash instrument in kronor, exact, a correction the same row's next version,
a currency resolving to two records, a want recorded against and a subject
declined); SWESTR's `a-same-day-revision` (republished at noon) and
`an-index-level` (the SWESTR index); the
government bonds' `a-tenor-not-published`, through a want; the wants and
licences cases.

Not presented, each with why: every case about a kind of data the Riksbank
never publishes here (bars, trades, quotes, venues, crypto, outcomes,
chains, filings, holdings, dividends, ratings, pools, derived series); the
calendar cases (no calendar declared); `two-conventions-one-tenor` (no bill
carried), `a-curve-point-from-another-source`, `a-curve-for-a-date` (it asks
for par yields; the bonds' here are benchmark yields); `a-daily-close` and
`reports-its-feed-delay` (the exchange rates state no published time);
`a-rate-fixing` (it asks for percentiles, and SWESTR's 12.5th and 87.5th
are not whole numbers); `records-a-datasets-liveness`.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from pathlib import Path
from typing import Any

from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import ANSWERED_BY_SDK, Recorder, run, suite

from riksbank.portal import LATEST, Fetched, SyntheticPortal

from conftest import AT, CURVES, FX, HELD, INSTANCE, RATES, feed, resolving, want

NEVER = {
    "bars": "the Riksbank states one rate a day: no open, high, low or volume",
    "a crypto asset's price": "the Riksbank rates currencies: no token",
    "prices on a venue": "the Riksbank's rates are its own, no venue's",
    "a security's price": "the Riksbank rates currencies: no security another source named",
    "trades": "the Riksbank states one rate a day: no trades",
    "quotes": "the Riksbank states one rate a day: no quotes",
    "settlement dates": "records each value as published; never computes a settlement date",
    "outcomes": "the Riksbank publishes no event contract, so no outcome",
    "disputed outcomes": "the Riksbank publishes no event contract, so no outcome disputed",
    "streams": "it polls the Riksbank hourly; it streams nothing",
    "option chains": "the Riksbank publishes no option chain",
    "filings": "the Riksbank publishes rates: no company's filings",
    "holdings": "the Riksbank publishes rates: no holdings report",
    "corporate actions": "the Riksbank publishes rates: no declared dividend",
    "ratings": "the Riksbank publishes rates: no rating",
    "derived series": "values are recorded as published: no series derived from them",
    "factors": "the Riksbank publishes rates: no pool, so no pool's factor",
    "calendars": "its datasets declare no calendar: the platform holds none for the krona yet",
    "publication times": "the exchange rates state no published time",
}
NOT_PRESENTED = {
    **{c.name: NEVER[c.about] for c in suite("data").cases if c.about in NEVER},
    "two-conventions-one-tenor": "no bill is carried here: one convention a point",
    "a-curve-point-from-another-source": "it publishes no curve point another source does",
    "queries-the-lake-within-bounds": "it records no trades",
    "a-daily-close": "the exchange rates state no published time",
    "a-curve-for-a-date": "the bonds' here are benchmark yields: no par yield",
    "a-rate-fixing": (
        "it asks for percentiles: SWESTR's are the 12.5th and 87.5th, which the contract's "
        "whole-number percentile cannot hold"
    ),
}


class Changed(SyntheticPortal):
    """The Riksbank, read twice: as recorded, then with SWESTR of 17 November
    republished and the dollar's latest rate corrected."""

    def __init__(self) -> None:
        super().__init__(lambda: AT)
        self.reads: dict[str, int] = {}

    async def get(self, path: str) -> Fetched:
        got = await super().get(path)
        source = (
            "rates" if path.startswith("/swestr/v1/SWESTR?") else "fx" if path == LATEST else ""
        )
        self.reads[source] = self.reads.get(source, 0) + 1
        if not source or self.reads[source] == 1:
            return got
        text = got.text
        if source == "rates":
            text = text.replace(
                '"rate":1.878,"date":"2026-11-17"', '"rate":1.880,"date":"2026-11-17"'
            ).replace(
                '"publicationTime":"2026-11-18T08:00:00Z"',
                '"publicationTime":"2026-11-18T11:00:00Z"',
            )
        else:
            text = text.replace(
                '{"seriesId":"SEKUSDPMI","date":"2026-11-19","value":10.14101}',
                '{"seriesId":"SEKUSDPMI","date":"2026-11-19","value":10.15}',
            )
        assert text != got.text
        return Fetched(path, 200, text.encode(), got.fetched_at, got.date)


class Gap(SyntheticPortal):
    """The Riksbank, the 10-year bond's yield stating nothing."""

    async def get(self, path: str) -> Fetched:
        if "SEGVB10YC" in path:
            self.asked.append(path)
            return Fetched(path, 200, b"[]", AT)
        return await super().get(path)


def producers(tmp: Path) -> dict[str, Callable[[Recorder], Awaitable[None]]]:
    async def read(recorder: Recorder) -> None:
        resolving(recorder)
        await feed(tmp, recorder).check()

    async def changed(recorder: Recorder) -> None:
        resolving(recorder)
        work = feed(tmp, recorder, portal=Changed())
        await work.check()
        await work.check()

    async def two_records(recorder: Recorder) -> None:
        resolving(recorder, ambiguous="GBP")
        await feed(tmp, recorder).check()

    async def gap(recorder: Recorder) -> None:
        resolving(recorder)
        work = feed(tmp, recorder, portal=Gap(lambda: AT))
        await work.check()
        recorder.answer(
            "ObservationsWanted",
            lambda _: want("w-g", [HELD["SE GVB"]], day="2026-11-18", dataset=CURVES).message,
        )
        await recorder.hear(work)
        sent = [r for b in recorder.on("RecordRates") for r in b.rates]
        on_18th = {
            (r.tenor.count, r.tenor.unit)
            for r in sent
            if r.meta.business_date == "2026-11-18" and r.kind == ops.RATE_KIND_BENCHMARK_YIELD
        }
        assert on_18th and (10, ops.TENOR_UNIT_YEAR) not in on_18th

    def wanted(message: Any) -> Callable[[Recorder], Awaitable[None]]:
        async def produce(recorder: Recorder) -> None:
            resolving(recorder)
            work = feed(tmp, recorder)
            await work.check()
            recorder.answer("ObservationsWanted", lambda _: message)
            await recorder.hear(work)

        return produce

    async def licences(recorder: Recorder) -> None:
        recorder.answer(
            "ListDatasets",
            lambda _: ops.ListDatasetsResult(licences=[ops.DatasetLicence(dataset=FX)]),
        )
        work = feed(tmp, recorder)
        await work.wants.read_licences()
        assert work.wants.licensed == {FX}

    async def withdrawn(recorder: Recorder) -> None:
        resolving(recorder)
        work = feed(tmp, recorder)
        recorder.answer(
            "WantWithdrawn", lambda _: ops.WantWithdrawnEvent(want_id="w-s", dataset=RATES)
        )
        await recorder.hear(work)

    close = (ops.PRICE_KIND_CLOSE,)
    return {
        "the-forming-day-restated": changed,
        "an-exact-price": read,
        "an-fx-rate": read,
        "an-asset-that-does-not-resolve": two_records,
        "a-want-recorded-against": wanted(
            want(
                "w-1",
                ["LCL-USD"],
                day="2026-10-01",
                dataset=FX,
                data_type="meridian.v1.Price",
                kinds=close,
            ).message
        ),  # fmt: skip
        "a-subject-declined": wanted(
            want(
                "w-2",
                ["LCL-SEK"],
                day="2026-10-01",
                dataset=FX,
                data_type="meridian.v1.Price",
                kinds=close,
            ).message
        ),  # fmt: skip
        "a-standing-want-withdrawn": withdrawn,
        "reads-its-datasets-licences": licences,
        "a-same-day-revision": changed,
        "an-index-level": read,
        "a-tenor-not-published": gap,
    }


def test_the_data_suite_passes(tmp_path: Path) -> None:
    report = run("data", producers(tmp_path), not_presented=NOT_PRESENTED, instance_id=INSTANCE)
    assert report.passed, report.failures
    assert sorted(report.not_presented) == sorted(NOT_PRESENTED)
    assert len(report.passed_cases) == 11 + len(ANSWERED_BY_SDK)
    assert HELD and CURVES
