"""What this version declares beside its role, `data` (W8.1, W4.1; the
catalogue from contract v18), built from code and used twice: `__main__`
registers with it, and `meridian plugin upload` reads it from the built image
(pyproject.toml's `[tool.meridian] declaration`).

**The catalogue: three datasets** (the product owner, items 128, 129, 130,
132 and 143, 2026-11-19: Tier 1, one plugin for the Riksbank's SWEA and
SWESTR APIs; their keys proposed, the product owner's to approve):

- **`riksbank_rates`**: SWESTR with its volume and transactions, its 1-week
  and 1, 2, 3 and 6-month averages, the SWESTR index and the policy rate --
  rates, daily; pushed as the Riksbank publishes them and any past day
  pulled when the lake wants it;
- **`riksbank_curves`**: the 2, 5, 7 and 10-year Swedish government bonds'
  yields, `benchmark_yield` at each tenor on one record (ruling 130) --
  rates, daily;
- **`riksbank_fx`**: the daily exchange rates against the krona, each the
  price of a currency's cash instrument in kronor -- prices, daily; pushed
  as published and any past day pulled when wanted.

**Served, not kept** (rulings 132 and 143, as plugin-fred's
`fred_restricted` and plugin-riksbank's curves say it). The Riksbank's
own series list names Refinitiv as the government bonds' source
(https://api.riksbank.se/swea/v1/Series, `source`), and whether its grant
covers them is not stated. So `riksbank_curves` is pulled only, never
pushed, and its answers are never kept in the plugin's storage; the rows the
lake receives are recorded as any are. Whether a deployment keeps them is
its licence: "served, not kept" is the default the clause in its terms asks
the deployment admin to set (ruling 1032 retired `licence_default`, so the
plugin declares none). The exchange rates still published each name the
Riksbank itself as source: kept, as the rates are.

Each: `vendor` the Riksbank, no aggregator; `cadence` a day; its day
Stockholm's (the Riksbank's banking day), ending at midnight; no calendar
(the platform holds none for the krona yet); no venue; `history` 0, as each
series states; its terms and pricing (contract 30, ruling 1032) the
Riksbank's, in plain words, and no licence declared -- a deployment's
licence, set on the Data sources page, is the one enforced; a gap asked
again (`gap_recovery` `backfill`, W10.14).

**Storage:** the rates' and exchange rates' answers (raw.py), archivable,
ten years by default.
"""

from __future__ import annotations

from meridian import DatasetDeclaration
from meridian.declaration import RecordKind

from .raw import DEFAULT_WINDOW_DAYS, RESPONSES

RIKSBANK_RATES, RIKSBANK_CURVES, RIKSBANK_FX = "riksbank_rates", "riksbank_curves", "riksbank_fx"
KEYS = (RIKSBANK_RATES, RIKSBANK_CURVES, RIKSBANK_FX)
#: The datasets served when wanted and never kept here (ruling 132).
NOT_KEPT = (RIKSBANK_CURVES,)
VENDOR = "Sveriges Riksbank"
RATE = "meridian.v1.Rate"
PRICE = "meridian.v1.Price"
CADENCE = 86_400
DAY_TIME_ZONE = "Europe/Stockholm"
DAY_END_MINUTE = 0

#: The Riksbank's terms, in plain words (contract 30, ruling 1032), from its
#: API's FAQ and SWESTR's conditions for use, as the research read them on
#: 2026-11-19.
API_TERMS = (
    "The Riksbank's API for interest rates and exchange rates: free, no key or account needed "
    "(without a key, 5 calls a minute and 1,000 a day per address). Its data may be adapted "
    "and used without a particular permission or agreement; cite Sveriges Riksbank as the "
    "source, except for processed figures; claim no cooperation or partnership with the "
    "Riksbank "
    "(https://www.riksbank.se/en-gb/statistics/interest-rates-and-exchange-rates/"
    "retrieving-interest-rates-and-exchange-rates-via-api/faq--the-api-for-interest-rates-and-"
    "exchange-rates/)."
)
#: The clause the restricted dataset records for its deployment admin.
NOT_KEPT_CLAUSE = (
    " Its licence default is served, not kept (rulings 132 and 143): the plugin pulls it only "
    "when wanted and keeps none of its answers; whether the lake keeps its rows is the "
    "deployment admin's licence to set."
)
TERMS = {
    RIKSBANK_RATES: API_TERMS
    + (
        " SWESTR, its average rates and its index are free, with no licence fee: a re-publisher "
        "names Sveriges Riksbank as SWESTR's administrator and source, states its conditions, "
        "and keeps any figure it has processed distinguishable from the Riksbank's; they may be "
        "used in pricing tools "
        "(https://www.riksbank.se/en-gb/statistics/swestr/conditions-for-use-and-re-publishing/)."
    ),
    RIKSBANK_CURVES: API_TERMS
    + (
        " The government bonds' yields are Refinitiv's, as the Riksbank's series list states "
        "their source; whether the Riksbank's grant covers them is not stated. Using them "
        "beyond that may need Refinitiv's permission."
    )
    + NOT_KEPT_CLAUSE,
    RIKSBANK_FX: API_TERMS
    + (" The exchange rates are indicative, published for information, and not for transactions."),
}


def _dataset(key: str, data_types: list[str], modes: list[str]) -> DatasetDeclaration:
    return DatasetDeclaration(
        key=key,
        vendor=VENDOR,
        data_types=data_types,
        modes=modes,
        cadence=CADENCE,
        history=0,
        terms_and_pricing=TERMS[key],
        gap_recovery="backfill",
        day_time_zone=DAY_TIME_ZONE,
        day_end_minute=DAY_END_MINUTE,
    )


CATALOGUE = [
    _dataset(
        RIKSBANK_RATES,
        [RATE, "meridian.v1.Rate.volume", "meridian.v1.Rate.transaction_count"],
        ["push", "pull"],
    ),
    _dataset(RIKSBANK_CURVES, [RATE], ["pull"]),
    _dataset(RIKSBANK_FX, [PRICE], ["push", "pull"]),
]

RESPONSES_KIND = RecordKind(RESPONSES, "Raw responses", window_days=DEFAULT_WINDOW_DAYS)
