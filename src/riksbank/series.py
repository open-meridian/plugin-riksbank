"""The Riksbank's series this version carries, what each one is, and the
record it is recorded against: the plugin's series map.

**Rates** (`riksbank_rates`). From the SWESTR API: SWESTR (`SWESTR`), a
daily `fixing` with its volume and number of transactions; its compounded
averages over 1 week and 1, 2, 3 and 6 months (`SWESTRAVG1W` to
`SWESTRAVG6M`), each an `average` and its own record; and the SWESTR index
(`SWESTRINDEX`), an `index_level` based 1 September 2021 = 100. Each is in
per cent, actual/360 simple, as the Riksbank's framework states it:
"Transactions are reported with the daily calculation convention actual
number of days through 360", and "The 360-day convention is applied for the
calculation of the average interest rates and index"
(https://www.riksbank.se/globalassets/media/statistik/swestr/250605/framework-for-the-transaction-based-reference-rate-swestr.pdf,
https://www.riksbank.se/globalassets/media/statistik/swestr/publicering-210621/decision-annex-the-design-of-average-rates-and-index-based-on-swestr.pdf).
SWESTR's volume is stated in "SEK millions" (the framework, 4.3.1) and
recorded as the kronor it is, exactly (71691 is SEK 71,691,000,000). Its
12.5th and 87.5th percentiles are **not carried**: the contract's
percentile is a whole number. From the SWEA API, the policy rate
(`SECBREPOEFF`), a `fixing` in the same convention, the krona money
market's -- the plugin's statement; the Riksbank states "per cent".

**Government bond yields** (`riksbank_curves`, SWEA, group 7). The 2, 5, 7
and 10-year Swedish government bonds' yields (`SEGVB2YC` to `SEGVB10YC`),
each a `benchmark_yield` (ruling 130) at its tenor on one `rate_curve`
record. The Riksbank names each "Swedish Government Bond, maturity <n>
years", sourced from Refinitiv: a quoted bond's yield, not a fitted
constant-maturity point. Their convention, annual compounding on 30E/360, is
the Swedish bond market's, as the Debt Office's calculation example states
it ("Day-count convention: 30E/360", the yield compounding once a year;
https://www.riksgalden.se/globalassets/dokument_eng/debt/calculation/nominal-bonds-2023.pdf)
-- the plugin's statement; the Riksbank states "per cent". The Treasury
bills (group 6) are **not carried** in this version.

**FX** (`riksbank_fx`, SWEA group 130, "Currencies against Swedish
kronor"): each currency's daily mid rate, kronor per one unit of the
currency (the dollar 10.07354, the yen 0.06312), a `Price` of the
currency's cash instrument in Swedish kronor, never inverted. Only the
currencies the Riksbank still publishes, each stated "Sveriges Riksbank" as
its source; the closed series (the Nasdaq-sourced currencies before the
euro, and others) are not read.

Each record is asked of the deployment by its code proposed here as a
`symbol` at the source `riksbank`, a name **proposed** with this version for
the platform's seed; the platform seeds none yet, so until a deployment
holds a record its values wait, reported missing, never minted. Each
currency is resolved by its ISO 4217 code, as plugin-ecb resolves its.
"""

from __future__ import annotations

from dataclasses import dataclass

from meridian.operations import RateConvention

SOURCE = "riksbank"
INTEREST_RATE, INDEX, RATE_CURVE = "interest_rate", "index", "rate_curve"

#: The krona money market's convention, and the Swedish bond market's.
MONEY_MARKET_360 = RateConvention(day_count="act_360", compounding="simple")
BOND = RateConvention(day_count="thirty_e_360", compounding="compounded", periods_per_year=1)
SWESTR_INDEX_BASE = "2021-09-01=100"
#: SWESTR's volume is stated in millions of kronor.
VOLUME_SCALE = 6


@dataclass(frozen=True)
class Record:
    """A referential record, by the code proposed for it at `riksbank`."""

    code: str
    instrument_type: str
    description: str

    @property
    def identifier(self) -> tuple[str, str, str]:
        return ("symbol", self.code, SOURCE)


SWESTR = "SWESTR"
SWESTR_INDEX = "SWESTRINDEX"
POLICY_RATE = "SECBREPOEFF"
#: The averages, by the Riksbank's id, and the period each is over.
AVERAGES = {
    "SWESTRAVG1W": "1 week",
    "SWESTRAVG1M": "1 month",
    "SWESTRAVG2M": "2 months",
    "SWESTRAVG3M": "3 months",
    "SWESTRAVG6M": "6 months",
}

SWESTR_RECORD = Record("SWESTR", INTEREST_RATE, "Swedish krona Short Term Rate (SWESTR)")
INDEX_RECORD = Record("SWESTR index", INDEX, "SWESTR index")
POLICY_RECORD = Record("Policy rate", INTEREST_RATE, "Sveriges Riksbank policy rate")
AVERAGE_RECORDS = {
    series: Record(f"SWESTR average {period}", INTEREST_RATE, f"SWESTR average rate, {period}")
    for series, period in AVERAGES.items()
}
BONDS_RECORD = Record("SE GVB", RATE_CURVE, "Swedish Government Bonds (SE GVB) yields")

#: Each rate series: its record and kind, in the Riksbank's order.
RATE_KINDS: dict[str, tuple[Record, str]] = {
    SWESTR: (SWESTR_RECORD, "fixing"),
    **{series: (record, "average") for series, record in AVERAGE_RECORDS.items()},
    SWESTR_INDEX: (INDEX_RECORD, "index_level"),
    POLICY_RATE: (POLICY_RECORD, "fixing"),
}
RECORDS = (*(r for r, _ in RATE_KINDS.values()), BONDS_RECORD)

#: The government bonds carried, by SWEA series, and each one's tenor.
BONDS = {"SEGVB2YC": "2Y", "SEGVB5YC": "5Y", "SEGVB7YC": "7Y", "SEGVB10YC": "10Y"}
#: What the Riksbank publishes beside them and is not carried, and why.
NOT_CARRIED = {
    "SWESTR percentiles": "the 12.5th and 87.5th: the contract's percentile is a whole number",
    "SE TB": "Treasury bills (Refinitiv): not carried in this version",
    "STIBOR, SE MB, SE CP": "closed, or another administrator's rates: not carried",
    "KIX, TCW": "krona indices: a DerivedSeries, not carried in this version",
}

#: The currencies against kronor, by ISO 4217 code, as the Riksbank names
#: each; its series is `SEK<code>PMI`.
CURRENCIES = {
    "AUD": "Australian dollar",
    "BRL": "Brazilian real",
    "CAD": "Canadian dollar",
    "CHF": "Swiss franc",
    "CNY": "Chinese yuan",
    "CZK": "Czech koruna",
    "DKK": "Danish krone",
    "EUR": "Euro",
    "GBP": "British pound",
    "HKD": "Hong Kong dollar",
    "HUF": "Hungarian forint",
    "IDR": "Indonesian rupiah",
    "ILS": "Israeli shekel",
    "INR": "Indian rupee",
    "ISK": "Icelandic krona",
    "JPY": "Japanese yen",
    "KRW": "South Korean won",
    "MXN": "Mexican peso",
    "MYR": "Malaysian ringgit",
    "NOK": "Norwegian krone",
    "NZD": "New Zealand dollar",
    "PHP": "Philippine peso",
    "PLN": "Polish zloty",
    "RON": "Romanian leu",
    "SGD": "Singapore dollar",
    "THB": "Thai baht",
    "TRY": "Turkish lira",
    "USD": "US dollar",
    "ZAR": "South African rand",
}
#: The currency every rate is stated in.
KRONA = "SEK"
#: The SWEA group the exchange rates' latest are read by.
FX_GROUP = 130


def fx_series(code: str) -> str:
    """A currency's SWEA series: USD is `SEKUSDPMI`."""
    return f"SEK{code}PMI"


def fx_code(series: str) -> str:
    """A rate's currency: `SEKUSDPMI` is USD; empty for one not carried."""
    if series.startswith("SEK") and series.endswith("PMI") and len(series) == 9:
        code = series[3:6]
        return code if code in CURRENCIES else ""
    return ""
