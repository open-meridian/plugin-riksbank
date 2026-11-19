"""The typed records the pages answer, for a person's page and an agent's
tool alike (contract v12; spec/a-deployment-serves-its-mcp): the data role's
common records (`meridian.roles.data`, spec/plugin-pages-follow-their-role),
each extended with the Riksbank's own fields, as plugin-ecb's are: Connection's
**Sources**, and Datasets' **Records**. The Connection tab is
`read_connection`, the Datasets tab `read_datasets`, each answering what its
page shows, as data, under the role's names.

A data plugin's pages show its connection and its datasets, never a value
(plans/the-lake-prices-the-book, ruled 2026-10-03): rates and figures are
the reading roles'. So neither record holds a rate or a level; each says how
the Riksbank was reached and what the plugin serves of it.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from meridian.roles import data


@dataclass(frozen=True)
class SourceRead:
    """One source the plugin reads, as "Sources" lists it: its state, the
    latest period it published, the calls made of it, and its last error;
    where it reads, and how far its history reaches."""

    source: str
    dataset: str
    state: str
    #: Which of the plugin's sources: rates, curves or fx.
    kind: str = ""
    last_release: str = ""
    calls: int = 0
    last_error: str = ""
    reads: str = ""
    history: str = ""


@dataclass(frozen=True)
class ConnectionRead(data.ConnectionRead):
    """Connection's common fields, then the Riksbank's: the head's status and what
    it means, where it reads, the last check, each source as "Sources" lists
    it, and the answers kept."""

    #: The head's status: `ok`, `busy`, `warn` or `error`, and what it means.
    state: str = ""
    said: str = ""
    source: str = ""
    checked_at: str = ""
    sources: list[SourceRead] = field(default_factory=list)
    responses_kept: int = 0
    kept_for: str = ""


@dataclass(frozen=True)
class RecordRead:
    """One record or currency the plugin records, as "Records" lists it: its
    code (a record's symbol at `riksbank`, a currency's ISO code), its name, what
    it is recorded as and in which dataset, its convention, the deployment's
    instrument for it or why there is none, and the latest day recorded."""

    code: str
    name: str
    dataset: str
    recorded_as: str
    convention: str
    instrument_id: str
    miss: str
    latest_day: str = ""


@dataclass(frozen=True)
class DatasetsRead(data.DatasetsRead):
    """Datasets' common fields, then the Riksbank's: the attribution its terms ask
    for, each record and currency it reads ("Records"), and the lines it could not read.
    Its rows are the role's."""

    served: list[data.Served] = field(default_factory=list)
    wants: list[data.WantHeard] = field(default_factory=list)  # type: ignore[assignment]
    attribution: str = ""
    records: list[RecordRead] = field(default_factory=list)
    #: The answers' lines that named a value holding none that reads, each with
    #: how often seen.
    unread: list[str] = field(default_factory=list)
