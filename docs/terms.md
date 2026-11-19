# Terms

A summary, not legal advice: read the Riksbank's own words before relying on
them. Terms change; these were read on 19 November 2026.

From the FAQ for the Riksbank's API
([riksbank.se](https://www.riksbank.se/en-gb/statistics/interest-rates-and-exchange-rates/retrieving-interest-rates-and-exchange-rates-via-api/faq--the-api-for-interest-rates-and-exchange-rates/))
and SWESTR's conditions for use
([riksbank.se](https://www.riksbank.se/en-gb/statistics/swestr/conditions-for-use-and-re-publishing/)):

- **The API.** Free; its data may be adapted and used without a particular
  permission or agreement. Cite Sveriges Riksbank as the source, except for
  figures you have processed. Claim no cooperation or partnership with the
  Riksbank. Without a key: 5 calls a minute and 1,000 a day per address.
- **Exchange rates.** Indicative, published for information, not for
  transactions.
- **SWESTR, its averages and index.** Free, no licence fee. A re-publisher
  names Sveriges Riksbank as SWESTR's administrator and source and states
  its conditions; processed figures are kept distinguishable. They may be
  used in pricing tools.
- **Government bond yields.** The Riksbank's own series list names
  Refinitiv as their source; whether the Riksbank's grant covers them is
  not stated.

**Served, not kept.** The government bond yields (`riksbank_curves`) are
read only when your lake wants a day, and the plugin keeps none of their
answers. Their terms carry the clause, and "served, not kept" is the
licence default it asks you to set.

Each dataset describes these terms in words, shown on the Data sources
page, and declares no licence. The licence a deployment admin sets there is
the one enforced; the plugin says nothing of whether your deployment meets
anyone's terms.

This project is not affiliated with or endorsed by Sveriges Riksbank.
