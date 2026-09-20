from types import SimpleNamespace
from unittest.mock import Mock

import pytest

import window


def user32(monkeypatch, *, topmost=False, iconic=False):
    api = SimpleNamespace(
        GetWindowLongW=Mock(return_value=8 if topmost else 0),
        SetWindowPos=Mock(return_value=True),
        IsIconic=Mock(return_value=iconic),
        ShowWindow=Mock(), IsWindow=Mock(return_value=True),
    )
    monkeypatch.setattr(window.ctypes, "WinDLL", lambda *a, **k: api, raising=False)
    monkeypatch.setattr(window, "find_game_windows", lambda user32: [42])
    return api


def test_restores_topmost_after_task_exception(monkeypatch):
    api = user32(monkeypatch, iconic=True)
    with pytest.raises(RuntimeError, match="cancelled"):
        with window.game_on_top():
            raise RuntimeError("cancelled")
    api.ShowWindow.assert_called_once_with(42, 9)
    assert [call.args[1] for call in api.SetWindowPos.call_args_list] == [-1, -2]


def test_preserves_preexisting_topmost(monkeypatch):
    api = user32(monkeypatch, topmost=True)
    with window.game_on_top():
        pass
    assert [call.args[1] for call in api.SetWindowPos.call_args_list] == [-1]


def test_disabled_pin_does_not_inspect_or_change_windows(monkeypatch):
    find = Mock(side_effect=AssertionError("unexpected Windows call"))
    monkeypatch.setattr(window, "find_game_windows", find)
    with window.game_on_top(False):
        pass
    find.assert_not_called()


def test_multiple_game_windows_fail_without_choosing_one(monkeypatch):
    api = user32(monkeypatch)
    monkeypatch.setattr(window, "find_game_windows", lambda user32: [42, 43])
    with pytest.raises(RuntimeError, match="唯一"):
        with window.game_on_top():
            pass
    api.SetWindowPos.assert_not_called()
