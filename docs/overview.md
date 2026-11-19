# Overview

Sveriges Riksbank publishes the rates this plugin puts into your
deployment's lake:

- **SWESTR, its averages and index, and the policy rate**
  (`<instance>:riksbank_rates`): SWESTR each banking day, with its volume
  and number of transactions; its 1-week and 1, 2, 3 and 6-month compounded
  averages; the SWESTR index, based 1 September 2021 = 100; and the policy
  rate.
- **Government bond yields** (`<instance>:riksbank_curves`): the 2, 5, 7
  and 10-year Swedish government bonds' yields, as the Riksbank publishes
  them from Refinitiv.
- **Exchange rates** (`<instance>:riksbank_fx`): each currency's daily rate
  against the krona, the price of one unit of that currency in kronor.

It reads the Riksbank's public APIs, SWESTR and SWEA: no key, no account.
It checks for new rates and exchange rates every hour. The government bond
yields are read only when your lake asks for a day (served, not kept:
[terms](terms.md)); any past day of any dataset is read when the lake asks
for it.

## What it records

- **Each value as the Riksbank writes it,** made an exact decimal from its
  text. A day the Riksbank states nothing for is no value, never a zero.
- **Conventions.** SWESTR, its averages and index are actual/360, as the
  Riksbank's SWESTR framework states it; the policy rate the same, the
  plugin's statement of the krona money market's. The bond yields are
  recorded annual on 30E/360, the Swedish bond market's convention as the
  Debt Office states it; the Riksbank states only per cent.
- **SWESTR's volume** is stated in SEK millions and recorded as the kronor
  it is. SWESTR, its averages and index carry the time the Riksbank
  published them.
- **Against your deployment's records.** SWESTR, each average, the index,
  the policy rate and the bonds' curve are each asked of your deployment by
  a code at `riksbank`; the plugin never makes a record: one your deployment
  does not hold is reported missing, and its values wait. Each currency is
  found by its ISO 4217 code.
- **Not carried:** SWESTR's 12.5th and 87.5th percentiles (the platform's
  percentile is a whole number), the Treasury bills, the closed market
  rates, and the KIX and TCW indices.

## What it never does

It records no trade and shows no value on its pages. It holds no account and
uses no key. Its exchange rates are never inverted, and it keeps no answer
of the government bonds'. It stays within the API's limit without a key.
