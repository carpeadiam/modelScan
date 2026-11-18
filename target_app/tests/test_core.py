import pytest

from target_app.src import core


def test_add():
    assert core.add(2, 3) == 5


def test_moving_average():
    assert core.moving_average([1, 2, 3, 4], 2) == [1.5, 2.5, 3.5]


def test_moving_average_invalid_window():
    with pytest.raises(ValueError):
        core.moving_average([1], 0)


def test_normalize_version():
    assert core.normalize_version("v1.2.3") == (1, 2, 3)
