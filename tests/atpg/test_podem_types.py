import pytest

from atpg.podem import PodemResult


def test_success_result_with_x_dont_cares():
    result = PodemResult(status="success", pattern=(1, None, 0, None, 1), backtracks=3)
    assert result.status == "success"
    assert result.pattern == (1, None, 0, None, 1)
    assert result.backtracks == 3


def test_untestable_result_has_no_pattern():
    result = PodemResult(status="untestable", backtracks=12)
    assert result.pattern is None
    assert result.backtracks == 12


def test_aborted_result_has_no_pattern():
    result = PodemResult(status="aborted", backtracks=500)
    assert result.pattern is None


def test_success_requires_pattern():
    with pytest.raises(ValueError, match="requires a pattern"):
        PodemResult(status="success")


def test_success_requires_at_least_one_care_bit():
    with pytest.raises(ValueError, match="at least one care bit"):
        PodemResult(status="success", pattern=(None, None, None))


def test_success_rejects_invalid_bits():
    with pytest.raises(ValueError, match="invalid pattern bit"):
        PodemResult(status="success", pattern=(1, 2))


def test_untestable_rejects_pattern():
    with pytest.raises(ValueError, match="must not include a pattern"):
        PodemResult(status="untestable", pattern=(1, 0))


def test_negative_backtracks_rejected():
    with pytest.raises(ValueError, match="backtracks must be non-negative"):
        PodemResult(status="untestable", backtracks=-1)
