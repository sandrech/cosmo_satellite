from __future__ import annotations

import json
from pathlib import Path

import pytest

from json_component import JsonObjectCodec, JsonStore, Ok, VersionedObjectCodec

FIXTURES = Path(__file__).parents[1] / "fixtures" / "cosmo_a"


@pytest.mark.parametrize("name", [
    "01_full_constellation.json",
    "02_first_launch.json",
    "03_satellite_outages.json",
    "04_link_range.json",
])
def test_case_fixture_structural_roundtrip(name: str):
    source = FIXTURES / name
    original = json.loads(source.read_text(encoding="utf-8"))

    store = JsonStore(VersionedObjectCodec(JsonObjectCodec(), "cosmo-A-1.0"))
    loaded = store.load(source)
    assert isinstance(loaded, Ok)

    rendered = store.dumps(loaded.value)
    assert isinstance(rendered, Ok)
    assert json.loads(rendered.value) == original
