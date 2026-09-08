"""The worker must not start with a synthetic scorer."""

import pytest

from scripts.run_worker import load_matcher


def test_the_worker_refuses_to_start_without_m2s_matcher():
    with pytest.raises(SystemExit) as exit_error:
        load_matcher()
    assert "B-04/B-06" in str(exit_error.value)
    assert "must not be synthetic" in str(exit_error.value)
