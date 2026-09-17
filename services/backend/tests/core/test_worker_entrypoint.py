"""M2's concrete matcher is now merged; dependency failure must still stop startup."""

import builtins

import pytest

from scripts.run_worker import load_matcher


def test_loads_the_real_matcher():
    from app.modules.matching.scoring import Matcher

    assert isinstance(load_matcher(), Matcher)


def test_missing_matcher_stops_startup(monkeypatch):
    original = builtins.__import__

    def missing(name, *args, **kwargs):
        if name == "app.modules.matching.scoring":
            raise ImportError("synthetic missing module")
        return original(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", missing)
    with pytest.raises(SystemExit, match="No matcher is available"):
        load_matcher()
