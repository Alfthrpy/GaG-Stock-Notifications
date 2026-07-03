import pytest

from fisch_tracker.config import FISCH_PLACE_ID_ENV, get_place_id


def test_get_place_id_reads_env_var(monkeypatch):
    monkeypatch.setenv(FISCH_PLACE_ID_ENV, "1234567")

    assert get_place_id() == 1234567


def test_get_place_id_raises_when_missing(monkeypatch):
    monkeypatch.delenv(FISCH_PLACE_ID_ENV, raising=False)

    with pytest.raises(RuntimeError):
        get_place_id()


def test_get_place_id_raises_when_not_numeric(monkeypatch):
    monkeypatch.setenv(FISCH_PLACE_ID_ENV, "not-a-number")

    with pytest.raises(ValueError):
        get_place_id()
