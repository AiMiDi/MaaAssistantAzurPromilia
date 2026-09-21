from types import SimpleNamespace
import pytest
from launcher import ensure_game, resolve_path


class Clock:
    value = 0
    def now(self):
        return self.value
    def sleep(self, value):
        self.value += value


def test_existing_window_skips_invalid_path_and_does_not_launch():
    assert ensure_game({"GameLaunchPath": {"path": "missing"}}, windows=lambda: [1]) == "existing"


def test_disabled_does_not_inspect_or_launch():
    assert ensure_game({"GameLaunch": "Off"}) == "disabled"


def test_launch_once_with_space_path_and_wait(tmp_path):
    folder = tmp_path / "game with spaces" / "0.6.2.2"
    folder.mkdir(parents=True)
    exe = folder / "launcher.exe"
    exe.touch()
    frames = iter([[], [], [4]])
    launched = []
    clock = Clock()
    def spawn(path):
        launched.append(path)
        return SimpleNamespace(poll=lambda: None)
    assert ensure_game({"GameLaunchPath": {"path": str(folder.parent)}},
                       windows=lambda: next(frames), running=lambda: False, spawn=spawn,
                       clock=clock.now, sleep=clock.sleep) == "ready"
    assert launched == [exe.resolve()]


def test_starting_process_is_not_launched_again_and_timeout_is_bounded():
    clock = Clock()
    with pytest.raises(TimeoutError):
        ensure_game({"GameLaunchTimeout": {"seconds": "10"}}, windows=lambda: [],
                    running=lambda: True, clock=clock.now, sleep=clock.sleep)
    assert clock.value == 10


def test_early_process_exit_is_reported(tmp_path):
    exe = tmp_path / "launcher.exe"
    exe.touch()
    with pytest.raises(RuntimeError, match="退出"):
        ensure_game({"GameLaunchPath": {"path": str(exe)}}, windows=lambda: [],
                    running=lambda: False, spawn=lambda p: SimpleNamespace(poll=lambda: 1))


def test_multiple_windows_and_bad_paths_fail():
    with pytest.raises(RuntimeError, match="多个"):
        ensure_game({}, windows=lambda: [1, 2])
    with pytest.raises(ValueError, match="未找到"):
        resolve_path("unrelated.exe")


def test_invalid_timeout_prevents_launch():
    with pytest.raises(ValueError, match="10～600"):
        ensure_game({"GameLaunchTimeout": {"seconds": "0"}}, windows=lambda: [])
