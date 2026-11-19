"""The catalogue, from code, as the deployment approves it."""

from __future__ import annotations

from riksbank.declaration import DECLARATION


def test_three_datasets_rates_and_prices() -> None:
    keys = [d.key for d in DECLARATION.catalogue]
    assert keys == ["riksbank_rates", "riksbank_curves", "riksbank_fx"]
    kinds = {d.key: list(d.data_types)[0] for d in DECLARATION.catalogue}
    assert kinds["riksbank_fx"] == "meridian.v1.Price"
    assert kinds["riksbank_curves"] == "meridian.v1.Rate"
    for dataset in DECLARATION.catalogue:
        assert dataset.day_time_zone == "Europe/Stockholm"
        assert dataset.vendor == "Sveriges Riksbank"
        assert dataset.gap_recovery == "backfill" and not dataset.calendar_id
        said = dataset.terms_and_pricing
        assert "cite Sveriges Riksbank as the source" in said and "no key" in said
        assert len(said) <= 2000
    rates = DECLARATION.catalogue[0].terms_and_pricing
    assert "administrator" in rates and "no licence fee" in rates


def test_the_bonds_are_pulled_only_and_served_not_kept() -> None:
    modes = {d.key: list(d.modes) for d in DECLARATION.catalogue}
    # The catalogue holds each mode as its enum: push and pull for the rates.
    push, pull = modes["riksbank_rates"]
    assert push != pull and modes["riksbank_curves"] == [pull]
    assert modes["riksbank_fx"] == [push, pull]
    rates, curves, fx = DECLARATION.catalogue
    assert (
        "served, not kept" in curves.terms_and_pricing and "Refinitiv" in curves.terms_and_pricing
    )
    assert "served, not kept" not in rates.terms_and_pricing + fx.terms_and_pricing
    assert "not for transactions" in fx.terms_and_pricing


def test_the_answers_are_kept_in_storage() -> None:
    assert DECLARATION.storage is not None
    assert [k.name for k in DECLARATION.storage.kinds] == ["responses"]
