"""The Riksbank's SWESTR, its averages and index, the policy rate,
government bond yields and exchange rates as an Open Meridian data plugin
(the product owner, items 128, 129, 130, 132 and 143, 2026-11-19: Tier 1,
one plugin for the Riksbank's SWEA and SWESTR APIs).

It runs its data role class, `Lake` (feed.py's `Feed`, with its lifecycle
here), with `meridian.run` on the sidecar it is launched beside, declaring
its catalogue, its storage and its one setting (declaration.py). It reads the
rates' current range and the exchange rates' latest at start and every hour,
and the government bond yields only when the lake wants them, recording
what it has not recorded in this process (feed.py). What the Riksbank
answered is kept in the storage the deployment grants (raw.py), the bonds'
answers aside. It reads which of its datasets a deployment admin has
licensed, on start and every minute. It holds nothing else: a restart reads
the Riksbank again, and the lake answers what it recorded before unchanged.
"""

from __future__ import annotations

import asyncio
import contextlib
import logging
from typing import Any

import meridian

from .declaration import DECLARATION, PORT
from .feed import Feed
from .page import figures, hold, pages
from .portal import portal
from .raw import RawStore
from .settings import Config, config_from

log = logging.getLogger("riksbank")

#: How often the rates and exchange rates are checked, in seconds: hourly.
CHECK_SECONDS = 3600
#: How often storage is tended past its window, in seconds: daily.
TEND_SECONDS = 86_400
#: How often the datasets' licences are read again.
LICENCES_SECONDS = 60


class Lake(Feed):
    """The data role's class with its lifecycle (open-meridian 0.35, rulings
    1004, 1005, 1009 to 1023): `meridian.run` delivers each settings to
    `on_settings` -- the first before anything is heard -- and starts `run`,
    again after a backoff should it fail."""

    def __init__(self, *args: Any, **kwargs: Any) -> None:
        super().__init__(*args, **kwargs)
        self.config = Config()
        self.wake = asyncio.Event()

    async def on_settings(self, delivered: Any) -> None:
        """Apply each delivery of the settings: sample data on or off, and the
        answers' window, tended at once."""
        config = config_from(delivered.values)
        self.config = config
        self.use(portal(config.sample_data))
        self.wake.set()
        await self.raw.tend(self.plugin, config.window_days, config.past_window, self.now())

    async def on_start(self) -> None:
        """Its storage read once registered: on an instance run as shards or
        with a standby pod, the shard's own folder (open-meridian 0.37.0)."""
        await super().on_start()
        self.raw.open()

    async def on_stop(self) -> None:
        """Its storage forgotten: registered again, it is read afresh."""
        self.raw.close()
        await super().on_stop()

    async def run(self) -> None:
        """The rates' current range checked, storage tended, the licences read."""
        await asyncio.gather(self._check(), self._tend(), self._licences())

    async def _check(self) -> None:
        """Read the rates' current range at once, then hourly, or at once
        when the settings change."""
        while True:
            self.wake.clear()
            try:
                await self.check()
            except meridian.MeridianError as failed:
                # The sidecar refused something a recording needed; say so
                # and keep the schedule rather than spin.
                for held in self.status.sources.values():
                    held.error = f"the deployment refused a recording: {failed}"
                log.warning("this check stopped: %s", failed)
            with contextlib.suppress(TimeoutError):
                await asyncio.wait_for(self.wake.wait(), timeout=CHECK_SECONDS)

    async def _tend(self) -> None:
        while True:
            await asyncio.sleep(TEND_SECONDS)
            config = self.config
            await self.raw.tend(self.plugin, config.window_days, config.past_window, self.now())

    async def _licences(self) -> None:
        """Its own declared datasets' licences (contract v20, W10.9), read on
        start and every minute, for the Datasets page."""
        while True:
            try:
                await self.wants.read_licences()
            except meridian.MeridianError as failed:
                log.warning("the datasets' licences were not read this time: %s", failed)
            await asyncio.sleep(LICENCES_SECONDS)


def main() -> None:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s"
    )
    lake = Lake(portal(False), RawStore())
    hold(lake)
    # The version's whole declaration (declaration.py): its settings, its
    # pages with the levels each serves and their tools, and its
    # documentation. A version registers exactly what it was uploaded with
    # (contract v25).
    meridian.run(
        declaration=DECLARATION,
        roles=[lake],
        pages=pages,
        port=PORT,
        on_settings=lake.on_settings,
        figures=lambda: figures(lake.status, lake),
    )


if __name__ == "__main__":
    main()
