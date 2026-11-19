# Setup

## Launching it

The Riksbank's data need no key and no account. Launch the plugin and approve
its one role, `data`. It reads the rates and the exchange rates at once, and
every hour after; the government bond yields only when the lake asks for a
day.

Its settings: the **Raw responses window** and **past the window** (the
SDK's), and on a deployment installed for development, **Sample data**: the
Riksbank's answers recorded on 19 November 2026, committed with the plugin.

## Its datasets

On the deployment's **Data sources** page (deployment admins), for each of
`<instance>:riksbank_rates`, `<instance>:riksbank_curves` and
`<instance>:riksbank_fx`:

1. **License it.** Each dataset describes the Riksbank's terms in words and
   declares no licence ([terms](terms.md)). `riksbank_rates` carries
   SWESTR's conditions: name Sveriges Riksbank as its administrator and
   source. `riksbank_curves` carries the clause "served, not kept": the
   Riksbank names Refinitiv as the bonds' source, so the plugin reads them
   only when wanted and keeps none of their answers; set its licence not to
   keep them unless your terms with Refinitiv allow it. Until a licence is
   set, the lake keeps the rows and reads every use right restrictively.
2. **Entitle** each plugin that reads it.
3. **Priority**, where another dataset states the same values.

## The records

SWESTR, its averages and index, the policy rate and the bonds' curve are
each about a record named by a code at `riksbank`: `riksbank:SWESTR`,
`riksbank:SWESTR average 1 week` (and `1 month`, `2 months`, `3 months`,
`6 months`), `riksbank:SWESTR index`, `riksbank:Policy rate`,
`riksbank:SE GVB`. The platform does not seed them yet, and the plugin never
makes one: the Datasets page's Records tab shows each as not held, and its
values wait until your deployment holds it. Each currency is found by its
ISO 4217 code.
