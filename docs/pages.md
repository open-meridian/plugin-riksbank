# Pages

Both pages are the data role's, under **Manage**, for the plugin's admins.
Neither shows a rate or a price. Each is also a read tool on the
deployment's MCP, answering what the page shows.

## Connection (`read_connection`)

The head's status; **Key** (the mode, "No key needed"); **Limits and use**
(5 calls a minute and 1,000 a day without a key; one request at a time, at
most one every 13 seconds, a check every hour; the requests made, the last
check and error); **Stream** (it does not stream); and **Sources**, a tab
of its own: the rates, the government bond yields and the exchange rates,
each with its state ("Pulled when wanted" for the bonds until the lake asks
for a day), latest day and calls, and in its details where it reads, when
the Riksbank publishes and whether its answers are kept.

## Datasets (`read_datasets`)

**Served**: its three datasets as declared, whether each is licensed, what
it recorded and declined, and the wants it answered; then **Records**, a
tab of its own: each record and currency, what it is recorded as, its
convention, and your deployment's instrument for it or why there is none,
searched and paged to fit one screen.
