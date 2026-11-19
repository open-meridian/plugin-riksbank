"""The plugin's settings, declared to the SDK, and what it makes of them.

The Riksbank's data need no key and no choice: the plugin reads its public
API without one. In the data role's order (spec/plugin-pages-follow-their-
role) it declares no `environment` and no credential ("No key needed"), only
the role's sample data, a developer's setting (`meridian.sample_data`):
the real answers committed under responses/ in place of the website, for the
e2e and for trying the plugin offline.

The SDK declares the storage's two settings from the declaration's kind
(declaration.py): `responses_window_days` and `responses_past_window`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass

import meridian

from .raw import DEFAULT_WINDOW_DAYS, RESPONSES

SAMPLE_DATA = "sample_data"
WINDOW = f"{RESPONSES}_window_days"
PAST_WINDOW = f"{RESPONSES}_past_window"


@meridian.settings
class Declared:
    """The settings as declared, in the data role's order."""

    sample_data: bool = meridian.sample_data(
        description=(
            "Serve the Riksbank's answers recorded on 2026-11-19, committed with the plugin, "
            "instead of reading its API: SWESTR, its averages and index, the policy rate, the "
            "government bond yields and the exchange rates from 3 August to 19 November 2026. "
            "Development deployments only."
        )
    )


DECLARED = Declared


@dataclass(frozen=True)
class Config:
    sample_data: bool = False
    window_days: int = DEFAULT_WINDOW_DAYS
    past_window: str = "kept"


def config_from(values: Mapping[str, object]) -> Config:
    """The configuration a delivery of the settings says."""
    window = values.get(WINDOW)
    past = values.get(PAST_WINDOW)
    return Config(
        sample_data=values.get(SAMPLE_DATA) is True,
        window_days=window if isinstance(window, int) and window > 0 else DEFAULT_WINDOW_DAYS,
        past_window=past if isinstance(past, str) and past else "kept",
    )
