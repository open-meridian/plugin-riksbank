"""The two pages under Manage, and their read tools."""

from __future__ import annotations

import asyncio
from pathlib import Path

import pytest
from meridian.suites import Recorder
from meridian.testing import PageClient

from riksbank import page as page_module
from riksbank.page import CONNECTION, DATASETS_PAGE, figures, hold, pages

from conftest import CURVES, HELD, INSTANCE, USD, feed, resolving, want


@pytest.fixture
def client(tmp_path: Path) -> PageClient:
    plugin = resolving(Recorder(INSTANCE), "Policy rate")
    work = feed(tmp_path, plugin)
    asyncio.run(work.check())
    asked = want("w-c", [HELD["SE GVB"]], day="2026-11-18", dataset=CURVES)
    plugin.answer("ObservationsWanted", lambda _: asked.message)
    asyncio.run(plugin.hear(work))
    hold(work)
    return PageClient(pages)


def test_each_page_is_managed_alone(client: PageClient) -> None:
    served = {(r.page.path, r.level): r.response.status for r in client.every_page()}
    assert served == {
        (CONNECTION, "admin"): 200,
        (CONNECTION, "write"): 403,
        (CONNECTION, "read"): 403,
        (DATASETS_PAGE, "admin"): 200,
        (DATASETS_PAGE, "write"): 403,
        (DATASETS_PAGE, "read"): 403,
    }
    client.assert_no_account_data("10.14101", "111.31230661", "1.884", "3.103")


def test_connection_and_its_sources(client: PageClient) -> None:
    text = client.get(CONNECTION, "admin").text
    assert "No key needed" in text and "Does not stream" in text and "1 record not held" in text
    sources = client.get(CONNECTION, "admin", tab="sources").text
    assert sources.count("<tr data-source=") == 3
    assert "Thu 19 Nov 2026" in sources and sources.count("None: served, not kept") == 1


def test_datasets_and_records(client: PageClient) -> None:
    text = client.get(DATASETS_PAGE, "admin").text
    keys = ("riksbank_rates", "riksbank_curves", "riksbank_fx")
    assert all(f"riksbank:{k}" in text for k in keys)
    assert "served, not kept" in text
    records = client.get(DATASETS_PAGE, "admin", tab="records").text
    assert 'data-code="SWESTR"' in records and 'data-code="USD"' in records
    assert 'data-code="SE TB"' in records and "Source: Sveriges Riksbank" in records
    searched = client.get(DATASETS_PAGE, "admin", q="SWESTR average").text
    assert searched.count("<tr data-code=") == 5


def test_the_tools_answer_what_the_pages_show(client: PageClient) -> None:
    data = client.call_tool("read_connection").data
    assert data["mode"] == "Sample data" and [s["dataset"] for s in data["sources"]] == [
        "riksbank:riksbank_rates", "riksbank:riksbank_curves", "riksbank:riksbank_fx",
    ]  # fmt: skip
    read = client.call_tool("read_datasets").data
    held = {r["code"]: r for r in read["records"]}
    assert held["SWESTR"]["instrument_id"] == HELD["SWESTR"]
    assert held["SWESTR"]["latest_day"] == "2026-11-18"
    assert held["Policy rate"]["miss"] == "not held: reported missing"
    assert held["USD"]["instrument_id"] == USD and held["USD"]["latest_day"] == "2026-11-19"
    assert held["SE GVB"]["latest_day"] == "2026-11-18"
    assert held["SE TB"]["miss"] == "not carried"


def test_before_the_first_check_and_not_reached(tmp_path: Path) -> None:
    page_module._held.clear()
    assert "Checking the Riksbank" in PageClient(pages).get(CONNECTION, "admin").text
    work = feed(tmp_path)
    work.status.sources["rates"].error = "https://api.riksbank.se/swestr/v1/SWESTR: URLError"
    hold(work)
    text = PageClient(pages).get(CONNECTION, "admin").text
    assert 'state="error"' in text and "Not answering" in text
    sources = PageClient(pages).get(CONNECTION, "admin", tab="sources").text
    assert sources.count("<td>Pulled when wanted") == 1


def test_the_figures_are_the_data_roles(client: PageClient) -> None:
    work = page_module._held["feed"]
    said = figures(work.status, work)
    assert [f.label for f in said][:3] == ["Connection", "Entitled at the vendor", "Stream"]
