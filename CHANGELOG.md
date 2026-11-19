# Changelog

## 0.1.0

On open-meridian 0.36.0, contract 30, on core aae501d's harness. The
product owner's items 128, 129, 130, 132 and 143 (2026-11-19): Tier 1, one
plugin for the Riksbank's SWEA and SWESTR APIs. The dataset keys, the
records' codes and the source `riksbank` are proposed here, the product
owner's to approve.

- **`riksbank_rates`** (push and pull): SWESTR, a daily `fixing` with its
  volume (SEK millions, recorded as kronor) and transactions, and its
  published time; its 1-week and 1, 2, 3 and 6-month averages, each an
  `average`; the SWESTR index, an `index_level` based 1 September 2021 =
  100; the policy rate, a `fixing`. Actual/360 simple, as SWESTR's
  framework states it; the policy rate's the plugin's statement. SWESTR's
  12.5th and 87.5th percentiles are not carried: the contract's percentile
  is a whole number.
- **`riksbank_curves`** (pull only, served, not kept): the 2, 5, 7 and
  10-year government bonds' yields, `benchmark_yield` points (ruling 130),
  annual on 30E/360, the plugin's statement of the Debt Office's
  convention. Refinitiv-sourced (ruling 132, 143): their answers are never
  kept in the plugin's storage, their rows name no raw record, and the
  dataset's terms carry the clause for the deployment admin's licence.
- **`riksbank_fx`** (push and pull): the daily rates against the krona,
  each the `close` price of the currency's cash instrument in kronor. The
  push reads every currency's latest in one request; a want reads only the
  currencies it names.
- **Within the API's anonymous limit:** one request at a time, 13 seconds
  apart, some 216 a day on the hourly check.
- **No record minted.**
- **Terms in words** (`declared.TERMS`), SWESTR's conditions among them.
- **Pages:** the data role's Connection (with Sources) and Datasets (with
  Records).
- **Sample data:** the Riksbank's answers as received on 2026-11-19.
