"""The Riksbank's rates, government bond yields and exchange rates into the
lake: the rates and exchange rates recorded as the Riksbank publishes them,
and any day of any dataset recorded when the lake wants it (W10.4, W10.7),
through the SDK's rates helpers (`meridian.roles.data.rates`) and its
`Wants`.

**Push: the rates and the exchange rates.** At start and every hour, the
rates' current range -- ten days of SWESTR, its averages and index, and the
policy rate, one request a series -- and the exchange rates' latest, every
currency in one request, are read. An answer whose values read as the last
one this process recorded records nothing; any other is recorded whole, in
the lake's batches, and the lake answers each value it holds unchanged. A
value the Riksbank revises -- a SWESTR republished at noon -- is the same
row key's next version, its later published time said.

**Pull: the government bonds** (rulings 132 and 143, declared.py). They are
read only when the lake wants them, and their answers are never kept in the
plugin's storage: their rows name no raw record.

**Rows** (series.py says each): SWESTR a `fixing` with its volume and
transactions; each average an `average`; the index an `index_level`; the
policy rate a `fixing`; each bond's yield a `benchmark_yield` at its tenor
on the bonds' record; each exchange rate a `close` `Price` of the
currency's cash instrument in kronor. A value the Riksbank states nothing
for is no row, never a zero. Each is read from the Riksbank's text as a
`Decimal`, never a float.

**Published time.** SWESTR, its averages and index state theirs
(`publicationTime`), and their rows say it; the SWEA API states none, so
the policy rate's, the bonds' and the exchange rates' rows state none,
rather than a wrong one.

**Subjects.** Each record by its code at `riksbank` (series.py), each
currency by its ISO 4217 code, resolved once per process; one the
deployment does not hold is reported missing, and its values wait. The
plugin mints nothing.

**Wants.** A want of one of the three datasets, for subjects the plugin
records -- a business date, a range of at most a year, or the latest -- is
read from the Riksbank, only the series its subjects need, and recorded
against the want; a day the Riksbank states nothing for, or one not come
yet, is declined `source_silent`; any other subject, or another kind of
data, `not_covered`.
"""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Iterable
from dataclasses import dataclass, field
from datetime import date, datetime, time, timedelta
from decimal import Decimal
from typing import Any
from zoneinfo import ZoneInfo

import meridian
from meridian.operations import Money, ObservationMeta, Price, SubjectRef
from meridian.plugin.v1 import operations_pb2 as ops
from meridian.roles import data
from meridian.roles.data import rates

from .answers import NotRead, Observation, Observations, parse
from .declared import DAY_TIME_ZONE, KEYS, PRICE, RATE, RIKSBANK_CURVES, RIKSBANK_FX, RIKSBANK_RATES
from .portal import (
    CURVES,
    FX,
    LATEST,
    RATES,
    SOURCES,
    Fetched,
    Portal,
    PortalUnreachable,
    path_for,
    utc_now,
)
from .raw import RawStore
from .series import (
    BOND,
    BONDS,
    BONDS_RECORD,
    CURRENCIES,
    KRONA,
    MONEY_MARKET_360,
    RATE_KINDS,
    SOURCE,
    SWESTR,
    SWESTR_INDEX_BASE,
    VOLUME_SCALE,
    Record,
    fx_code,
    fx_series,
)

log = logging.getLogger("riksbank")

STOCKHOLM = ZoneInfo(DAY_TIME_ZONE)
#: Each source's dataset, and back.
DATASETS = {RATES: RIKSBANK_RATES, CURVES: RIKSBANK_CURVES, FX: RIKSBANK_FX}
SOURCES_OF = {RIKSBANK_RATES: RATES, RIKSBANK_CURVES: CURVES, RIKSBANK_FX: FX}
#: The sources read only when wanted, their answers never kept.
PULLED = (CURVES,)
#: Each source's series, in the order read.
SERIES = {
    RATES: tuple(RATE_KINDS),
    CURVES: tuple(BONDS),
    FX: tuple(fx_series(code) for code in CURRENCIES),
}
#: The most days one want is answered for: a year.
MOST_DAYS = 366
#: How far back "the latest" is looked for.
LATEST_DAYS = 10


def _ns(moment: datetime) -> int:
    return int(moment.timestamp() * 1_000_000) * 1000


def day_bounds(day: date) -> tuple[int, int]:
    start = datetime.combine(day, time(0, 0), STOCKHOLM)
    return _ns(start), _ns(datetime.combine(day + timedelta(days=1), time(0, 0), STOCKHOLM))


@dataclass(frozen=True)
class Outcome:
    recorded: int = 0
    restated: int = 0
    unchanged: int = 0
    unresolved: tuple[str, ...] = ()


@dataclass
class Held:
    """A record or a currency as the plugin last saw it: the deployment's
    instrument, or why there is none, and the latest day recorded."""

    code: str
    name: str = ""
    instrument_id: str = ""
    miss: str = ""
    latest_day: date | None = None


@dataclass
class SourceStatus:
    """What the plugin last did with one source, for its pages."""

    source: str
    checked_at: datetime | None = None
    read_at: datetime | None = None
    error: str = ""
    first_day: date | None = None
    latest_day: date | None = None
    fetches: int = 0
    unread: dict[str, int] = field(default_factory=dict)


@dataclass
class Status:
    """What the plugin last did, for its pages; lost on a restart."""

    mode: str = "live"
    started_at: datetime | None = None
    sources: dict[str, SourceStatus] = field(
        default_factory=lambda: {s: SourceStatus(s) for s in SOURCES}
    )
    records: dict[str, Held] = field(default_factory=dict)
    currencies: dict[str, Held] = field(default_factory=dict)

    @property
    def checked_at(self) -> datetime | None:
        stamps = [s.checked_at for s in self.sources.values() if s.checked_at]
        return max(stamps) if stamps else None

    @property
    def error(self) -> str:
        return next((s.error for s in self.sources.values() if s.error), "")

    @property
    def fetches(self) -> int:
        return sum(s.fetches for s in self.sources.values())

    @property
    def read(self) -> bool:
        return any(s.read_at for s in self.sources.values())


class Feed(data.Role):
    """The plugin's data role class, its acts made on itself -- registered
    with `meridian.run`, or bound to the suite's recorder in its tests."""

    def __init__(
        self, portal: Portal, raw: RawStore, now: Callable[[], datetime] = utc_now
    ) -> None:
        self.portal = portal
        self.raw = raw
        self.now = now
        self.wants = data.Wants(self, KEYS, clock_ns=lambda: _ns(self.now()))
        self.rates = rates.Feed(
            self, SOURCE, wants=self.wants, day_zone=DAY_TIME_ZONE, clock_ns=lambda: _ns(self.now())
        )
        self.status = Status(mode=portal.mode, started_at=now())
        self._recorded: dict[str, str] = {}

    def today(self) -> date:
        return self.now().astimezone(STOCKHOLM).date()

    def use(self, portal: Portal) -> None:
        """Read from `portal` from now on: sample data turned on or off."""
        if portal.mode != self.portal.mode:
            self.portal = portal
            self.status.mode = portal.mode
            self._recorded.clear()

    # ── Reading ─────────────────────────────────────────────────────────

    async def _get(self, source: str, path: str) -> tuple[Fetched, str]:
        """One answer, and its key in storage: empty for a source never
        kept. PortalUnreachable where it did not answer 200."""
        held = self.status.sources[source]
        fetched = await self.portal.get(path)
        held.fetches += 1
        key = self.raw.keep(fetched) if source not in PULLED else ""
        if fetched.status != 200:
            raise PortalUnreachable(f"{fetched.url[:120]} answered {fetched.status}")
        return fetched, key

    def _note_unread(self, source: str, read: Observations) -> None:
        held = self.status.sources[source]
        for line in read.unread:
            held.unread[line] = held.unread.get(line, 0) + 1

    async def read(
        self, source: str, start: date, end: date, series: Iterable[str] | None = None
    ) -> Observations:
        """`source`'s values from `start` to `end` -- of `series` where
        given, else of every series it carries -- one request a series.
        PortalUnreachable or NotRead otherwise."""
        read = Observations(source)
        for name in series if series is not None else SERIES[source]:
            fetched, key = await self._get(source, path_for(name, start, end))
            read.add(parse(fetched.text, source, name, key))
        self._note_unread(source, read)
        return read

    async def read_latest(self) -> Observations:
        """The exchange rates' latest, every currency in one request; the
        currencies not carried left out."""
        fetched, key = await self._get(FX, LATEST)
        read = parse(fetched.text, FX, "", key)
        read.observations = [o for o in read.observations if fx_code(o.series)]
        self._note_unread(FX, read)
        return read

    # ── Resolving ───────────────────────────────────────────────────────

    async def record_of(self, record: Record) -> str:
        """A record's instrument, by its code at `riksbank`; empty, reported
        missing, where the deployment holds none."""
        held = self.status.records.setdefault(record.code, Held(record.code, record.description))
        if held.instrument_id:
            return held.instrument_id
        found = await self.rates.subject(
            record.identifier,
            description=record.description,
            instrument_type=record.instrument_type,
        )
        held.instrument_id, held.miss = found, "" if found else "not held: reported missing"
        return found

    async def currency(self, code: str) -> str:
        """A currency's cash instrument by ISO 4217, resolved now where not
        yet; empty, reported missing with why, where none resolves."""
        held = self.status.currencies.setdefault(code, Held(code, CURRENCIES.get(code, "")))
        if held.instrument_id:
            return held.instrument_id
        if held.miss:
            return ""
        identifier = ops.Identifier(scheme="iso4217", value=code)
        found = await self.resolve_identifier(
            identifiers=[identifier],
            as_of_ns=_ns(self.now()),
            stated_asset_class="cash",
            stated_currency=code,
            stated_description=f"{code} cash",
        )
        if found.found and found.instrument_id:
            held.instrument_id, held.miss = found.instrument_id, ""
            return str(found.instrument_id)
        reason = found.miss_reason or ops.MISS_REASON_NOT_FOUND
        held.miss = ops.MissReason.Name(reason).removeprefix("MISS_REASON_").lower()
        await self.report_missing_instrument(
            source=SOURCE,
            asset_class="cash",
            identifiers=[identifier],
            reason=reason,
            as_of_ns=_ns(self.now()),
            observed_at_ns=_ns(self.now()),
        )
        return ""

    async def resolve_pulled(self) -> None:
        """The bonds' record, resolved so a want can name it."""
        await self.record_of(BONDS_RECORD)

    # ── Recording ───────────────────────────────────────────────────────

    def _first(self, name: str, day: date, key: str) -> str:
        return self.raw.noted(name, day, key)[0].key if key else ""

    def _note(self, held: Held, day: date) -> None:
        if held.latest_day is None or day > held.latest_day:
            held.latest_day = day

    async def _rate_rows(self, read: Observations) -> list[Any]:
        rows: list[Any] = []
        for seen in read.observations:
            record, kind = RATE_KINDS.get(seen.series, (None, ""))
            if record is None:
                continue
            subject = await self.record_of(record)
            if not subject:
                continue
            extra: dict[str, Any] = {}
            said = seen.text
            if seen.series == SWESTR:
                if seen.volume:
                    extra["volume"] = Money(_kronor(seen.volume), KRONA)
                if seen.transactions:
                    extra["transaction_count"] = int(seen.transactions)
                said += f"|{seen.volume}|{seen.transactions}"
            value = (
                rates.index_level(seen.text, SWESTR_INDEX_BASE)
                if kind == "index_level"
                else rates.percent(seen.text)
            )
            rows.append(
                self.rates.rate(
                    subject,
                    RIKSBANK_RATES,
                    kind,
                    value,
                    business_date=seen.day,
                    published_ns=seen.published_ns,
                    convention=MONEY_MARKET_360,
                    series=seen.series,
                    raw_key=self._first(
                        f"{seen.series}:{seen.day}={said}@{seen.published}", seen.day, seen.key
                    ),
                    **extra,
                )
            )
            self._note(self.status.records[record.code], seen.day)
        return rows

    async def _curve_rows(self, read: Observations) -> list[Any]:
        rows: list[Any] = []
        subject = await self.record_of(BONDS_RECORD)
        if not subject:
            return rows
        for seen in read.observations:
            tenor = BONDS.get(seen.series)
            if tenor is None:
                continue
            rows.append(
                self.rates.rate(
                    subject,
                    RIKSBANK_CURVES,
                    "benchmark_yield",
                    rates.percent(seen.text),
                    business_date=seen.day,
                    convention=BOND,
                    tenor=tenor,
                    series=BONDS_RECORD.code,
                )
            )
            self._note(self.status.records[BONDS_RECORD.code], seen.day)
        return rows

    async def _prices(
        self, read: Observations, subjects: set[str] | None
    ) -> tuple[list[Any], list[str]]:
        prices: list[Any] = []
        unresolved: dict[str, None] = {}
        dataset = self.wants.dataset(RIKSBANK_FX)
        for seen in read.observations:
            code = fx_code(seen.series)
            if not code:
                continue
            subject = await self.currency(code)
            if not subject:
                unresolved[code] = None
                continue
            if subjects is not None and subject not in subjects:
                continue
            start, end = day_bounds(seen.day)
            first = self._first(f"{code}:{seen.day}={seen.text}", seen.day, seen.key)
            prices.append(
                Price(
                    meta=ObservationMeta(
                        row_key=f"{code}{KRONA}:{seen.day.isoformat()}",
                        subjects=[SubjectRef(entity_id=subject)],
                        source=ops.Source(dataset=dataset),
                        valid_from_ns=start,
                        valid_until_ns=end,
                        business_date=seen.day.isoformat(),
                        raw=self.plugin.raw_record(first[:256]) if first else None,
                    ),
                    kind="close",
                    price=Money(seen.value, KRONA),
                    basis="per_unit",
                )
            )
            self._note(self.status.currencies[code], seen.day)
        return prices, list(unresolved)

    async def record(
        self,
        read: Observations,
        *,
        want_id: str = "",
        days: Iterable[date] | None = None,
        subjects: set[str] | None = None,
        latest: bool = False,
    ) -> tuple[Outcome, set[str]]:
        """Record `read` -- on `days`, or each series' last day where
        `latest`, and for `subjects` where given -- against `want_id` where
        given. What the lake answered, and the subjects a row was sent for."""
        source = read.source
        dataset = DATASETS[source]
        read = _narrowed(read, set(days) if days is not None else None, latest)
        unresolved: list[str] = []
        rows: list[Any]
        if source == FX:
            rows, unresolved = await self._prices(read, subjects)
        else:
            rows = await (self._rate_rows(read) if source == RATES else self._curve_rows(read))
            if subjects is not None:
                rows = [r for r in rows if r.meta.subjects[0].entity_id in subjects]
            unresolved = [h.code for h in self.status.records.values() if h.miss]
        self.raw.save_firsts()
        counts = self.wants.sent_to(dataset)
        before = (counts.recorded, counts.restated, counts.unchanged)
        if source == FX:
            await self.wants.record("prices", rows, dataset, want_id)
        else:
            await self.rates.record(dataset, rows, want_id)
        sent = {r.meta.subjects[0].entity_id for r in rows}
        outcome = Outcome(
            counts.recorded - before[0],
            counts.restated - before[1],
            counts.unchanged - before[2],
            tuple(unresolved),
        )
        return outcome, sent

    async def check(self) -> dict[str, Outcome]:
        """Read the rates' current range and the exchange rates' latest, and
        record each where this process has not recorded it as it reads now;
        resolve the bonds' record, so a want can name it."""
        done: dict[str, Outcome] = {}
        for source in (RATES, FX):
            held = self.status.sources[source]
            held.checked_at = self.now()
            try:
                if source == RATES:
                    start, end = self.portal.current(self.today())
                    read = await self.read(RATES, start, end)
                else:
                    read = await self.read_latest()
            except (PortalUnreachable, NotRead) as failed:
                held.error = str(failed)
                log.warning("%s was not read: %s", source, failed)
                continue
            held.error = ""
            held.read_at = self.now()
            if read.days:
                held.first_day = min(read.days[0], held.first_day or read.days[0])
                held.latest_day = max(read.days[-1], held.latest_day or read.days[-1])
            digest = digest_of(read)
            if digest == self._recorded.get(source):
                continue
            outcome, _ = await self.record(read)
            done[source] = outcome
            if not outcome.unresolved:
                self._recorded[source] = digest
            log.info(
                "%s of %s to %s: %d recorded, %d restated, %d unchanged%s",
                source,
                held.first_day,
                held.latest_day,
                outcome.recorded,
                outcome.restated,
                outcome.unchanged,
                f"; not held: {', '.join(outcome.unresolved)}" if outcome.unresolved else "",
            )
        if self.status.read:
            await self.resolve_pulled()
        return done

    # ── Wants ───────────────────────────────────────────────────────────

    async def on_observations_wanted(
        self, heard: meridian.Heard[ops.ObservationsWantedEvent]
    ) -> None:
        await self.wants.hear(heard, self.answer)

    async def on_want_withdrawn(self, heard: meridian.Heard[ops.WantWithdrawnEvent]) -> None:
        self.wants.withdraw(heard.message.want_id)
        log.info("standing want %s withdrawn", heard.message.want_id)

    def _days(self, want: ops.ObservationsWantedEvent) -> tuple[list[date], bool]:
        """The days a want asks, and whether it asks only the latest."""
        if want.business_date:
            return [date.fromisoformat(want.business_date)], False
        if want.valid_from_ns or want.valid_until_ns:
            start = datetime.fromtimestamp(want.valid_from_ns / 1e9, STOCKHOLM).date()
            until = want.valid_until_ns - 1 if want.valid_until_ns else _ns(self.now())
            end = datetime.fromtimestamp(until / 1e9, STOCKHOLM).date()
            return [start + timedelta(days=n) for n in range((end - start).days + 1)][
                -MOST_DAYS:
            ], False
        today = self.today()
        return [today - timedelta(days=n) for n in range(LATEST_DAYS, -1, -1)], True

    def _series_of(self, source: str, asked: list[str]) -> list[str]:
        """The series a want's subjects need read."""
        if source == CURVES:
            return list(BONDS)
        if source == FX:
            codes = {h.instrument_id: c for c, h in self.status.currencies.items()}
            return [fx_series(codes[s]) for s in asked if s in codes]
        ids = {h.instrument_id: c for c, h in self.status.records.items()}
        return [s for s, (r, _) in RATE_KINDS.items() if r.code in {ids.get(a) for a in asked}]

    def _held(self, source: str) -> set[str]:
        if source == FX:
            return {h.instrument_id for h in self.status.currencies.values() if h.instrument_id}
        codes = (
            [BONDS_RECORD.code] if source == CURVES else [r.code for r, _ in RATE_KINDS.values()]
        )
        return {
            h.instrument_id
            for c, h in self.status.records.items()
            if c in codes and h.instrument_id
        }

    async def answer(
        self,
        want: ops.ObservationsWantedEvent,
        key: str,
        subjects: list[str],
        kinds: tuple[int, ...],
    ) -> dict[str, str]:
        """One want answered from the Riksbank: its values recorded against
        it, and each subject declined, with why."""
        source = SOURCES_OF.get(key, "")
        serves = PRICE if key == RIKSBANK_FX else RATE
        if not source or want.data_type not in ("", serves):
            return {s: "not_covered" for s in subjects}
        if key == RIKSBANK_FX and kinds and ops.PRICE_KIND_CLOSE not in kinds:
            return {s: "not_covered" for s in subjects}
        if source in PULLED:
            await self.resolve_pulled()
        held = self._held(source)
        declined = {s: "not_covered" for s in subjects if s not in held}
        asked = [s for s in subjects if s in held]
        if not asked:
            return declined
        if want.standing:
            self.wants.stand(want, asked, kinds)
        days, latest = self._days(want)
        days = [d for d in days if d <= self.today()]
        sent: set[str] = set()
        if days:
            status = self.status.sources[source]
            status.checked_at = self.now()
            try:
                read = await self.read(source, min(days), max(days), self._series_of(source, asked))
                status.error, status.read_at = "", self.now()
                if read.days:
                    status.first_day = min(read.days[0], status.first_day or read.days[0])
                    status.latest_day = max(read.days[-1], status.latest_day or read.days[-1])
                _, sent = await self.record(
                    read,
                    want_id=want.want_id,
                    days=None if latest else days,
                    subjects=set(asked),
                    latest=latest,
                )
            except (PortalUnreachable, NotRead) as failed:
                status.error = str(failed)
                log.warning("want %s: %s was not read: %s", want.want_id, source, failed)
        for subject in asked:
            if subject not in sent:
                declined[subject] = "source_silent"
        return declined


def _kronor(millions: str) -> Decimal:
    """A volume stated in millions of kronor, as the kronor it is, exactly."""
    return Decimal(millions).scaleb(VOLUME_SCALE)


def _narrowed(read: Observations, days: set[date] | None, latest: bool) -> Observations:
    """`read` on `days` alone, or each series' last day alone where
    `latest`."""
    if days is None and not latest:
        return read
    last: dict[str, date] = {}
    for seen in read.observations:
        last[seen.series] = max(seen.day, last.get(seen.series, seen.day))
    kept: list[Observation] = [
        o
        for o in read.observations
        if (days is None or o.day in days) and (not latest or o.day == last[o.series])
    ]
    return Observations(read.source, kept, read.unread)


def digest_of(read: Observations) -> str:
    """What an answer states, as a short digest: its values alone."""
    stated = repr(
        [
            (o.series, o.day, o.text, o.volume, o.transactions, o.published)
            for o in read.observations
        ]
    ).encode()
    return hashlib.sha256(stated).hexdigest()[:16]
