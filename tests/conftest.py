import pytest


@pytest.fixture
def in_tmp_path(tmp_path, monkeypatch):
    """Runs a test in a temporary directory provided by the tmp_path fixture"""
    monkeypatch.chdir(tmp_path)
    return tmp_path
