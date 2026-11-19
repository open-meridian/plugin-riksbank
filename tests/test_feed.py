"""The plugin's own conversion of the Riksbank's recorded answers."""

from __future__ import annotations

import asyncio
from datetime import date
from pathlib import Path

from meridian.operations import as_decimal
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.suites import Recorder

from riksbank.answers import NotRead, parse
from riksbank.portal import LATEST, SyntheticPortal, asked, path_for, within
from riksbank.series import fx_code

from conftest import CURVES, HELD, INSTANCE, USD, feed, fx_want, resolving, want


def checked(tmp: Path, *left_out: str) -> Recorder:
    plugin = resolving(Recorder(INSTANCE), *left_out)
    asyncio.run(feed(tmp, plugin).check())
    return plugin


def rates_of(plugin: Recorder, subject: str) -> list[ops.Rate]:
    return [
        r
        for b in plugin.on("RecordRates")
        for r in b.rates
        if r.meta.subjects[0].entity_id == subject
    ]


def heard(tmp: Path, *asked_for: object, plugin: Recorder | None = None) -> Recorder:
    """The rates checked, then each want heard."""
    held = plugin or resolving(Recorder(INSTANCE))
    work = feed(tmp, held)
    asyncio.run(work.check())
    for one in asked_for:
        held.answer("ObservationsWanted", lambda _, w=one: w.message)  # type: ignore[misc]
        asyncio.run(held.hear(work))
    return held


def test_swestr_a_fixing_act_360_with_volume_transactions_and_its_time(tmp_path: Path) -> None:
    swestr = rates_of(checked(tmp_path), HELD["SWESTR"])
    day = next(r for r in swestr if r.meta.business_date == "2026-11-18")
    assert day.kind == ops.RATE_KIND_FIXING and str(as_decimal(day.value.value)) == "1.884"
    assert day.convention.day_count == ops.DAY_COUNT_ACT_360
    assert day.convention.compounding == ops.COMPOUNDING_SIMPLE
    assert str(as_decimal(day.volume.amount)) == "71691000000"
    assert day.volume.currency_code == "SEK" and day.transaction_count == 254
    assert not day.percentiles
    (published,) = day.meta.source_times
    assert published.kind == ops.SOURCE_TIME_KIND_PUBLISHED
    assert published.at_ns == 1_795_075_200 * 10**9
    assert day.meta.raw.key.startswith("responses/") and "SWESTR-" in day.meta.raw.key
    assert {r.meta.business_date for r in swestr} >= {"2026-11-10", "2026-11-17"}


def test_the_averages_index_and_policy_rate(tmp_path: Path) -> None:
    plugin = checked(tmp_path)
    week = {r.meta.business_date: r for r in rates_of(plugin, HELD["SWESTR average 1 week"])}
    assert week["2026-11-19"].kind == ops.RATE_KIND_AVERAGE
    assert str(as_decimal(week["2026-11-19"].value.value)) == "1.87997"
    assert week["2026-11-19"].convention.day_count == ops.DAY_COUNT_ACT_360
    index = {r.meta.business_date: r for r in rates_of(plugin, HELD["SWESTR index"])}
    assert index["2026-11-19"].kind == ops.RATE_KIND_INDEX_LEVEL
    assert index["2026-11-19"].value.index_base == "2021-09-01=100"
    assert str(as_decimal(index["2026-11-19"].value.value)) == "111.31230661"
    policy = {r.meta.business_date: r for r in rates_of(plugin, HELD["Policy rate"])}
    assert policy["2026-11-19"].kind == ops.RATE_KIND_FIXING
    assert str(as_decimal(policy["2026-11-19"].value.value)) == "2"
    assert not policy["2026-11-19"].meta.source_times


def test_the_rates_and_exchange_rates_alone_are_pushed(tmp_path: Path) -> None:
    plugin = checked(tmp_path)
    assert not rates_of(plugin, HELD["SE GVB"])
    datasets = {r.meta.source.dataset for b in plugin.on("RecordRates") for r in b.rates}
    assert datasets == {f"{INSTANCE}:riksbank_rates"}
    prices = [p for b in plugin.on("RecordPrices") for p in b.prices]
    assert len(prices) == 29 and {p.meta.business_date for p in prices} == {"2026-11-19"}
    dollar = next(p for p in prices if p.meta.row_key == "USDSEK:2026-11-19")
    assert dollar.meta.subjects[0].entity_id == USD and dollar.kind == ops.PRICE_KIND_CLOSE
    assert str(as_decimal(dollar.price.amount)) == "10.14101"
    assert dollar.price.currency_code == "SEK" and dollar.meta.raw.key.endswith(
        "latest-130.json.gz"
    )


def test_the_bonds_wanted_benchmark_yields_never_kept(tmp_path: Path) -> None:
    plugin = heard(tmp_path, want("w-1", [HELD["SE GVB"]], day="2026-11-18", dataset=CURVES))
    bonds = {r.tenor.count: r for r in rates_of(plugin, HELD["SE GVB"])}
    assert sorted(bonds) == [2, 5, 7, 10]
    ten = bonds[10]
    assert ten.kind == ops.RATE_KIND_BENCHMARK_YIELD and ten.tenor.unit == ops.TENOR_UNIT_YEAR
    assert str(as_decimal(ten.value.value)) == "3.103"
    assert ten.convention.day_count == ops.DAY_COUNT_THIRTY_E_360
    assert ten.convention.compounding == ops.COMPOUNDING_COMPOUNDED
    assert ten.convention.periods_per_year == 1
    assert ten.meta.source.dataset == CURVES and not ten.meta.HasField("raw")
    against = {
        b.want_id for b in plugin.on("RecordRates") if b.rates[0].meta.source.dataset == CURVES
    }
    assert against == {"w-1"}


def test_the_bonds_answers_are_never_kept(tmp_path: Path) -> None:
    work = feed(tmp_path)
    asyncio.run(work.check())
    kept = len(work.raw.keys())
    heard(tmp_path, want("w-c", [HELD["SE GVB"]], day="2026-11-17", dataset=CURVES))
    # The second check's answers at the same moment replace the first's.
    assert kept == 9 and len(feed(tmp_path).raw.keys()) == 9
    assert not any("SEGVB" in k for k in feed(tmp_path).raw.keys())  # noqa: SIM118 - RawStore.keys


def test_a_currency_wanted_reads_its_series_alone(tmp_path: Path) -> None:
    plugin = resolving(Recorder(INSTANCE))
    portal = SyntheticPortal()
    work = feed(tmp_path, plugin, portal=portal)
    asyncio.run(work.check())
    plugin.answer("ObservationsWanted", lambda _: fx_want("w-fx", "2026-10-01").message)
    asyncio.run(plugin.hear(work))
    assert portal.asked[-1] == path_for("SEKUSDPMI", date(2026, 10, 1), date(2026, 10, 1))
    prices = [p for b in plugin.on("RecordPrices") if b.want_id == "w-fx" for p in b.prices]
    assert [p.meta.row_key for p in prices] == ["USDSEK:2026-10-01"]


def test_a_record_not_held_is_reported_missing_and_waits(tmp_path: Path) -> None:
    plugin = checked(tmp_path, "Policy rate", "SWESTR index")
    missed = {i.value for p in plugin.on("ReportMissingInstrument") for i in p.identifiers}
    assert {"Policy rate", "SWESTR index"} <= missed
    assert not rates_of(plugin, HELD["Policy rate"])


def test_wants_declined(tmp_path: Path) -> None:
    plugin = heard(
        tmp_path,
        want("w-1", [HELD["SWESTR"]], day="2026-10-01"),
        want("w-2", ["INS-ELSE"], day="2026-10-01"),
        want("w-3", [HELD["SWESTR"]], day="2026-10-04"),
        fx_want("w-4", "2026-11-15"),
        want("w-5", [HELD["SE GVB"]], day="2026-10-03", dataset=CURVES),
    )
    against = [b for b in plugin.on("RecordRates") if b.want_id == "w-1"]
    assert against and {r.meta.business_date for r in against[0].rates} == {"2026-10-01"}
    assert {r.meta.subjects[0].entity_id for r in against[0].rates} == {HELD["SWESTR"]}
    reasons = [ops.UnansweredReason.Name(d.reason) for d in plugin.on("DeclineWant")]
    assert reasons == ["UNANSWERED_REASON_NOT_COVERED"] + ["UNANSWERED_REASON_SOURCE_SILENT"] * 3


def test_the_latest_wanted_each_series_last_day(tmp_path: Path) -> None:
    plugin = heard(tmp_path, want("w-l", [HELD["SWESTR"], HELD["SWESTR index"]]))
    against = [r for b in plugin.on("RecordRates") if b.want_id == "w-l" for r in b.rates]
    days = {r.meta.subjects[0].entity_id: r.meta.business_date for r in against}
    assert days == {HELD["SWESTR"]: "2026-11-18", HELD["SWESTR index"]: "2026-11-19"}


def test_nothing_recorded_twice_in_a_process(tmp_path: Path) -> None:
    plugin = resolving(Recorder(INSTANCE))
    work = feed(tmp_path, plugin)
    asyncio.run(work.check())
    before = (len(plugin.on("RecordRates")), len(plugin.on("RecordPrices")))
    asyncio.run(work.check())
    assert (len(plugin.on("RecordRates")), len(plugin.on("RecordPrices"))) == before


def test_answers_read_as_written() -> None:
    read = parse(
        '[{"date":"2026-11-18","value":1.90},{"date":"2026-11-19","value":null}]', "x", "S"
    )
    assert [o.text for o in read.observations] == ["1.90"]
    assert parse("", "x", "S").observations == []
    assert parse('[{"date":"x","value":1}]', "x", "S").unread == ["S: a day 'x'"]
    try:
        parse('{"statusCode": 404}', "x", "S")
    except NotRead:
        pass
    else:  # pragma: no cover
        raise AssertionError("an object is not a list of days")
    assert (
        within(
            '[{"date":"2026-11-18","value":1.90},{"date":"2026-11-19","value":2}]',
            date(2026, 11, 19),
            date(2026, 11, 19),
        )
        == '[{"date":"2026-11-19","value":2}]'
    )
    assert asked(LATEST) is None and asked(
        "/swestr/v1/avg/SWESTRAVG1M?fromDate=2026-01-01&toDate=2026-01-02"
    ) == ("SWESTRAVG1M", date(2026, 1, 1), date(2026, 1, 2))
    assert fx_code("SEKUSDPMI") == "USD" and fx_code("SEKDEMPMI") == "" and fx_code("SEKETT") == ""
