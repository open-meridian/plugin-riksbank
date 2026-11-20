# meridian-riksbank

The Riksbank's public rates for [Open Meridian](https://open-meridian.com): an
Open Meridian plugin that puts SWESTR, its averages and index, the policy
rate, the Swedish government bond yields and the daily exchange rates against
the krona into a deployment's lake. It reads the Riksbank's two public APIs,
SWESTR and SWEA, and holds the `data` role, a data plugin. This is release
0.1.0, a draft for the product owner. How to set it up and use it is in
[docs/](docs/README.md).

It is built on the SDK it pins, `open-meridian==0.37.0` (contract 30).

## What it records

- **`<instance>:riksbank_rates`** (pushed as published, and pulled): SWESTR,
  each day's `fixing` with its volume (stated in SEK millions, recorded as
  the kronor it is) and number of transactions; its 1-week and 1, 2, 3 and
  6-month compounded averages, each an `average` and its own record; the
  SWESTR index, an index level based 1 September 2021 = 100; and the policy
  rate, a `fixing`. In per cent, actual/360: SWESTR's, its averages' and its
  index's as the Riksbank's SWESTR framework states it; the policy rate's
  the plugin's statement of the krona money market's, since the Riksbank
  states only per cent. SWESTR, its averages and index carry their
  published time.
- **`<instance>:riksbank_curves`** (pulled only, served, not kept): the 2, 5,
  7 and 10-year Swedish government bonds' yields, each a `benchmark_yield`
  at its tenor on one curve record, annual compounding on 30E/360 (the
  Swedish bond market's convention, as the Debt Office states it; the
  plugin's statement, since the Riksbank states only per cent).
- **`<instance>:riksbank_fx`** (pushed as published, and pulled): each
  currency's daily rate against the krona, kronor per unit of the currency,
  the price of the currency's cash instrument in kronor, never inverted.
- **Records:** SWESTR, its averages and index, the policy rate and the bonds'
  curve are each asked of the deployment by a code at `riksbank`
  (`riksbank:SWESTR`); the platform seeds none yet, so each is reported
  missing, never minted, and its rates wait. Each currency resolves by its
  ISO 4217 code.
- **Not presented:** SWESTR's 12.5th and 87.5th percentiles (the contract's
  percentile is a whole number); the Treasury bills; STIBOR and the other
  closed or third-party market rates; the KIX and TCW indices; the closed
  currencies.

## Served, not kept

The Riksbank's series list names Refinitiv as the government bonds' source,
and whether its grant covers them is not stated. So `riksbank_curves` is
read only when the lake wants a day, and the plugin keeps none of its
answers. Its terms carry the clause for the deployment admin, whose licence
says whether the lake keeps its rows: "served, not kept" is the default the
clause asks for. The exchange rates still published each name the Riksbank
itself as source, and are kept as the rates are.

## Deploying it

On a deployment, with the `meridian` CLI connected (`meridian connect`):

    meridian plugin upload                   # from this directory
    meridian plugin launch riksbank          # a deployment admin approves its one role, data

No key and no account. A deployment admin then licenses its three datasets
and entitles the plugins that read them on the Data sources page
([docs/setup.md](docs/setup.md)).

## Checking it

    make ci-local                  # lint, tests, plugin check, image, e2e: the pre-push gate
    make preview SHOTS=<dir>       # each page in a browser with the kit, at 375, 582 and 1280 px

`tests/test_suite.py` runs the SDK's data suite on the plugin's own
conversion, and it passes; a case about what the Riksbank never states here
is not presented, with why.

## The terms, summarised

Not legal advice; read the Riksbank's own words
([the API's FAQ](https://www.riksbank.se/en-gb/statistics/interest-rates-and-exchange-rates/retrieving-interest-rates-and-exchange-rates-via-api/faq--the-api-for-interest-rates-and-exchange-rates/),
[SWESTR's conditions](https://www.riksbank.se/en-gb/statistics/swestr/conditions-for-use-and-re-publishing/))
before relying on them. The API is free, and its data may be adapted and
used without a particular permission, citing Sveriges Riksbank as the
source; the exchange rates are indicative and not for transactions; SWESTR
is administered by Sveriges Riksbank, free with no licence fee, a
re-publisher keeping processed figures distinguishable; the government
bonds' yields are Refinitiv's. Without a key the API answers 5 calls a
minute and 1,000 a day. Each dataset says so in words, and declares no
licence: the deployment admin's licence is the one enforced. This project
is not affiliated with or endorsed by Sveriges Riksbank.

## Licence

Apache-2.0 (LICENSE, NOTICE). The Riksbank's answers under
`src/riksbank/responses/` are as received on 2026-11-19.
