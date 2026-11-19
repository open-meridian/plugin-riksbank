# Troubleshooting

| What you see | What it means | What to do |
|---|---|---|
| **Not answering** | No check has reached the Riksbank's API | Check the deployment's outbound access to api.riksbank.se; the plugin tries again within the hour |
| **Answering**, with a warning | An earlier check worked; the last did not | Nothing, usually: the next check runs within the hour. *answered 429* is the API's limit without a key: another client at the same address shares it |
| **N records not held** | Your deployment holds no record for SWESTR, an average, the index, the policy rate or the bonds' curve: the platform does not seed them yet | Nothing the plugin can do: it never makes a record. Their values are recorded once your deployment holds them |
| A currency not resolved | Its ISO 4217 code found no cash instrument, or two | Complete or merge the instrument at the Instruments page |
| A day declined, *source silent* | A weekend, a holiday, a day not published yet | Wait for the Riksbank's next publication |
| A subject declined, *not covered* | Not one of this plugin's records or currencies | Check the Records tab |
| Datasets: **Not licensed yet** | No deployment admin has licensed the dataset | Ask a deployment admin to license it on Data sources |
