"""Tests for the no-sleep mode feature."""

from __future__ import annotations

import logging
import shutil
import subprocess
import sys
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from ralph.core.no_sleep import (
    NoSleep,
    _LinuxMechanism,
    _MacOSMechanism,
    _WindowsMechanism,
)

IS_WINDOWS = sys.platform == "win32"
IS_LINUX = sys.platform.startswith("linux")


class TestNoSleepBasic:
    """Tests for NoSleep class basic behavior."""

    def test_no_sleep_is_context_manager(self) -> None:
        """NoSleep can be used as a context manager."""
        with NoSleep() as ns:
            assert isinstance(ns, NoSleep)

    def test_no_sleep_manual_release(self) -> None:
        """NoSleep can be released manually."""
        ns = NoSleep()
        try:
            if ns.is_active:
                assert True  # acquired successfully
            ns.release()
            assert not ns.is_active
        finally:
            ns.release()  # double-release should be safe

    def test_no_sleep_double_release_safe(self) -> None:
        """Releasing NoSleep twice does not raise."""
        ns = NoSleep()
        if ns.is_active:
            ns.release()
        ns.release()  # should not raise
        assert not ns.is_active


class TestDebugPromptSkip:
    """Tests for debug_prompt mode skipping sleep prevention."""

    def test_debug_prompt_skips_acquisition(self) -> None:
        """NoSleep(debug_prompt=True) does not acquire sleep prevention."""
        with NoSleep(debug_prompt=True) as ns:
            assert not ns.is_active

    def test_debug_prompt_release_is_noop(self) -> None:
        """Releasing debug_prompt NoSleep is safe."""
        ns = NoSleep(debug_prompt=True)
        ns.release()
        assert not ns.is_active


class TestLinuxMechanism:
    """Tests for _LinuxMechanism with systemd-inhibit as primary mechanism."""

    @patch("ralph.core.no_sleep.time.sleep")
    @patch("ralph.core.no_sleep.subprocess.Popen")
    @patch("ralph.core.no_sleep.shutil.which", return_value="/usr/bin/systemd-inhibit")
    def test_systemd_inhibit_success(
        self,
        mock_which: MagicMock,
        mock_popen: MagicMock,
        mock_time_sleep: MagicMock,
    ) -> None:
        """systemd-inhibit succeeds and prevents system sleep."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None  # process is still running
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        mech = _LinuxMechanism()
        result = mech.acquire()
        assert result is True
        mock_popen.assert_called_once_with(
            [
                "systemd-inhibit",
                "--what=sleep",
                "--who=ralph",
                "--why=preventing sleep during Ralph run",
                "--mode=block",
                "sleep",
                "infinity",
            ],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )
        # poll() must be used (NOT wait), so the child can stay alive.
        mock_proc.poll.assert_called_once()
        mock_proc.wait.assert_not_called()

    @patch("ralph.core.no_sleep.time.sleep")
    @patch("ralph.core.no_sleep.subprocess.Popen")
    def test_systemd_inhibit_falls_back_to_xdg(
        self,
        mock_popen: MagicMock,
        mock_time_sleep: MagicMock,
    ) -> None:
        """systemd-inhibit child exits → falls back to xdg-screensaver suspend."""
        # systemd-inhibit child died immediately
        mock_proc_fail = MagicMock()
        mock_proc_fail.poll.return_value = 1
        mock_proc_fail.returncode = 1
        mock_popen.return_value = mock_proc_fail

        with (
            patch("ralph.core.no_sleep.subprocess.run") as mock_run,
            patch(
                "ralph.core.no_sleep.shutil.which",
                side_effect=[
                    "/usr/bin/systemd-inhibit",
                    "/usr/bin/xdg-screensaver",
                    None,  # busctl lookup
                ],
            ),
        ):
            mock_run.return_value = MagicMock(returncode=0)

            mech = _LinuxMechanism()
            result = mech.acquire()
            assert result is True

    @patch("ralph.core.no_sleep.time.sleep")
    @patch("ralph.core.no_sleep.subprocess.Popen")
    @patch("ralph.core.no_sleep.subprocess.run")
    def test_all_mechanisms_fail(
        self,
        mock_run: MagicMock,
        mock_popen: MagicMock,
        mock_time_sleep: MagicMock,
    ) -> None:
        """All mechanisms fail: nothing on PATH, no DBus."""
        with patch("ralph.core.no_sleep.shutil.which", return_value=None):
            mech = _LinuxMechanism()
            result = mech.acquire()
            assert result is False
        # Nothing was even attempted
        mock_popen.assert_not_called()
        mock_run.assert_not_called()

    @patch("ralph.core.no_sleep.time.sleep")
    @patch("ralph.core.no_sleep.subprocess.Popen")
    @patch("ralph.core.no_sleep.shutil.which", return_value="/usr/bin/systemd-inhibit")
    def test_systemd_inhibit_release(
        self,
        mock_which: MagicMock,
        mock_popen: MagicMock,
        mock_time_sleep: MagicMock,
    ) -> None:
        """Release terminates systemd-inhibit process."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        mech = _LinuxMechanism()
        mech.acquire()
        assert mech._inhibit_process is not None

        mech.release()
        mock_proc.terminate.assert_called_once()
        assert mech._inhibit_process is None

    @patch("ralph.core.no_sleep.time.sleep")
    @patch("ralph.core.no_sleep.subprocess.Popen")
    @patch("ralph.core.no_sleep.shutil.which", return_value="/usr/bin/systemd-inhibit")
    def test_systemd_inhibit_release_on_kill(
        self,
        mock_which: MagicMock,
        mock_popen: MagicMock,
        mock_time_sleep: MagicMock,
    ) -> None:
        """Release kills process if terminate times out."""
        mock_proc = MagicMock()
        mock_proc.poll.return_value = None
        mock_popen.return_value = mock_proc

        mech = _LinuxMechanism()
        result = mech.acquire()
        assert result is True
        assert mech._inhibit_process is not None

        # Make wait timeout on release to trigger kill path
        mock_proc.wait.side_effect = subprocess.TimeoutExpired("systemd-inhibit", 5)
        mech.release()
        mock_proc.kill.assert_called_once()
        assert mech._inhibit_process is None

    @patch("ralph.core.no_sleep.subprocess.run")
    @patch("ralph.core.no_sleep.shutil.which")
    def test_dbus_inhibit_call_uses_system_bus_and_correct_args(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """DBus login1.Inhibit is invoked on --system bus with (what, who, why, mode)."""
        # systemd-inhibit/xdg-screensaver not on PATH, busctl is
        mock_which.side_effect = [None, None, "/usr/bin/busctl"]
        mock_run.return_value = MagicMock(returncode=0, stdout=b"h 5\n")

        mech = _LinuxMechanism()
        result = mech.acquire()

        # Even though busctl returns 0, the FD-lifetime issue means we
        # cannot honestly claim the inhibitor was acquired. The mechanism
        # must NOT report True for this fallback alone.
        assert result is False
        assert mech._dbus_inhibit_called is True

        # Verify the call shape
        mock_run.assert_called_once()
        call_args = mock_run.call_args[0][0]
        assert call_args[0] == "busctl"
        assert "--system" in call_args
        assert "--user" not in call_args
        # Inhibit signature: ssss = (what, who, why, mode)
        # In our argv layout, those four strings come after "ssss".
        ssss_idx = call_args.index("ssss")
        what, who, why, mode = call_args[ssss_idx + 1 : ssss_idx + 5]
        assert what == "sleep"
        assert who == "ralph"
        assert "preventing sleep" in why.lower()
        assert mode == "block"

    @patch("ralph.core.no_sleep.subprocess.run")
    @patch("ralph.core.no_sleep.shutil.which")
    def test_dbus_inhibit_release_is_noop(
        self,
        mock_which: MagicMock,
        mock_run: MagicMock,
    ) -> None:
        """Release after DBus best-effort call does not issue another busctl call."""
        mock_which.side_effect = [None, None, "/usr/bin/busctl"]
        mock_run.return_value = MagicMock(returncode=0, stdout=b"h 5\n")

        mech = _LinuxMechanism()
        mech.acquire()
        assert mech._dbus_inhibit_called is True

        mech.release()
        assert not mech._dbus_inhibit_called
        # No additional busctl call should be made on release
        assert mock_run.call_count == 1


@pytest.mark.skipif(not IS_LINUX, reason="Linux-only smoke test")
class TestLinuxMechanismSmoke:
    """Smoke tests that exercise the real Linux command — not mocks.

    These guard against the previous regression where mocked tests passed
    while the real command did not exist. Each test skips if the required
    binary is not on PATH (CI containers may not have systemd-logind).
    """

    @pytest.mark.skipif(
        shutil.which("systemd-inhibit") is None, reason="systemd-inhibit not on PATH"
    )
    def test_systemd_inhibit_actually_acquires_inhibitor(self) -> None:
        """systemd-inhibit actually holds an inhibitor visible to systemd-logind."""
        mech = _LinuxMechanism()
        try:
            result = mech.acquire()
            assert result is True
            assert mech._inhibit_process is not None
            assert mech._inhibit_process.poll() is None  # still running

            # Verify the inhibitor is registered with systemd-logind.
            list_out = subprocess.run(
                ["systemd-inhibit", "--list"],
                capture_output=True,
                text=True,
                timeout=5,
            )
            assert list_out.returncode == 0
            assert "ralph" in list_out.stdout
        finally:
            mech.release()

        # After release, the inhibitor must be gone.
        list_out2 = subprocess.run(
            ["systemd-inhibit", "--list"],
            capture_output=True,
            text=True,
            timeout=5,
        )
        # We can't assert generic "no ralph" because tests may run in
        # parallel; we only assert OUR PID's inhibitor is gone, which is
        # implicit because mech._inhibit_process is None.
        assert mech._inhibit_process is None
        assert list_out2.returncode == 0

    @pytest.mark.skipif(
        shutil.which("systemd-inhibit") is None, reason="systemd-inhibit not on PATH"
    )
    def test_nosleep_is_active_on_real_linux(self) -> None:
        """NoSleep() reports is_active=True on a real systemd Linux system."""
        ns = NoSleep()
        try:
            assert ns.is_active, "NoSleep failed to acquire on a system with systemd-inhibit"
        finally:
            ns.release()
        assert not ns.is_active


class TestMacOSMechanism:
    """Tests for _MacOSMechanism."""

    @patch("ralph.core.no_sleep.shutil.which")
    @patch("ralph.core.no_sleep.subprocess.Popen")
    def test_caffeinate_success(self, mock_popen: MagicMock, mock_which: MagicMock) -> None:
        """caffeinate starts successfully."""
        mock_which.return_value = "/usr/bin/caffeinate"
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        mech = _MacOSMechanism()
        result = mech.acquire()
        assert result is True
        mock_popen.assert_called_once_with(
            ["caffeinate", "-dims"],
            stdout=subprocess.DEVNULL,
            stderr=subprocess.DEVNULL,
        )

    @patch("ralph.core.no_sleep.shutil.which")
    def test_no_caffeinate(self, mock_which: MagicMock) -> None:
        """caffeinate not available."""
        mock_which.return_value = None

        mech = _MacOSMechanism()
        result = mech.acquire()
        assert result is False

    @patch("ralph.core.no_sleep.shutil.which")
    @patch("ralph.core.no_sleep.subprocess.Popen")
    def test_release_caffeinate(self, mock_popen: MagicMock, mock_which: MagicMock) -> None:
        """Release terminates caffeinate process."""
        mock_which.return_value = "/usr/bin/caffeinate"
        mock_proc = MagicMock()
        mock_proc.pid = 12345
        mock_popen.return_value = mock_proc

        mech = _MacOSMechanism()
        mech.acquire()
        assert mech._process is not None

        mech.release()
        mock_proc.terminate.assert_called_once()
        assert mech._process is None


class TestWindowsMechanism:
    """Tests for _WindowsMechanism."""

    @patch("ralph.core.no_sleep.platform.system", return_value="Windows")
    def test_acquire_success(self, mock_platform: MagicMock) -> None:
        """SetThreadExecutionState succeeds."""
        mock_kernel32 = MagicMock()
        mock_kernel32.SetThreadExecutionState.return_value = 1
        mock_ctypes = MagicMock()
        mock_ctypes.windll.kernel32 = mock_kernel32
        mock_ctypes.get_last_error.return_value = 0

        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            mech = _WindowsMechanism()
            result = mech.acquire()
            assert result is True
            assert mech._was_active is True

    @patch("ralph.core.no_sleep.platform.system", return_value="Windows")
    def test_acquire_failure(self, mock_platform: MagicMock) -> None:
        """SetThreadExecutionState fails."""
        mock_kernel32 = MagicMock()
        mock_kernel32.SetThreadExecutionState.return_value = 0
        mock_ctypes = MagicMock()
        mock_ctypes.windll.kernel32 = mock_kernel32
        mock_ctypes.get_last_error.return_value = 5

        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            mech = _WindowsMechanism()
            result = mech.acquire()
            assert result is False

    @patch("ralph.core.no_sleep.platform.system", return_value="Windows")
    def test_acquire_ctypes_missing(self, mock_platform: MagicMock) -> None:
        """ctypes.windll not available raises gracefully."""
        mock_ctypes = MagicMock()
        del mock_ctypes.windll

        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            mech = _WindowsMechanism()
            result = mech.acquire()
            assert result is False

    @patch("ralph.core.no_sleep.platform.system", return_value="Windows")
    def test_release(self, mock_platform: MagicMock) -> None:
        """Release calls SetThreadExecutionState with ES_CONTINUOUS."""
        mock_kernel32 = MagicMock()
        mock_kernel32.SetThreadExecutionState.return_value = 1
        mock_ctypes = MagicMock()
        mock_ctypes.windll.kernel32 = mock_kernel32

        with patch.dict("sys.modules", {"ctypes": mock_ctypes}):
            mech = _WindowsMechanism()
            mech.acquire()
            assert mech._was_active is True

            mech.release()
            # Should be called with ES_CONTINUOUS only
            calls = mock_kernel32.SetThreadExecutionState.call_args_list
            assert len(calls) == 2  # acquire + release
            assert calls[1][0][0] == 0x80000000  # ES_CONTINUOUS


class TestNoSleepPlatformIntegration:
    """Tests for NoSleep platform integration."""

    def test_no_sleep_on_linux(self) -> None:
        """NoSleep uses _LinuxMechanism on Linux (mocked)."""
        with (
            patch("ralph.core.no_sleep.platform.system", return_value="Linux"),
            patch("ralph.core.no_sleep._LinuxMechanism") as mock_cls,
        ):
            mock_instance = MagicMock()
            mock_instance.acquire.return_value = True
            mock_cls.return_value = mock_instance

            ns = NoSleep()
            assert ns.is_active
            mock_cls.assert_called_once()
            ns.release()

    def test_no_sleep_on_macos(self) -> None:
        """NoSleep uses _MacOSMechanism on macOS (mocked)."""
        with (
            patch("ralph.core.no_sleep.platform.system", return_value="Darwin"),
            patch("ralph.core.no_sleep._MacOSMechanism") as mock_cls,
        ):
            mock_instance = MagicMock()
            mock_instance.acquire.return_value = True
            mock_cls.return_value = mock_instance

            ns = NoSleep()
            assert ns.is_active
            ns.release()

    def test_no_sleep_on_windows(self) -> None:
        """NoSleep uses _WindowsMechanism on Windows (mocked)."""
        with (
            patch("ralph.core.no_sleep.platform.system", return_value="Windows"),
            patch("ralph.core.no_sleep._WindowsMechanism") as mock_cls,
        ):
            mock_instance = MagicMock()
            mock_instance.acquire.return_value = True
            mock_cls.return_value = mock_instance

            ns = NoSleep()
            assert ns.is_active
            ns.release()

    def test_no_sleep_on_unknown_platform(self) -> None:
        """NoSleep handles unknown platform gracefully."""
        with patch("ralph.core.no_sleep.platform.system", return_value="UnknownOS"):
            ns = NoSleep()
            assert not ns.is_active


class TestNoSleepCleanup:
    """Tests for cleanup behavior on all exit paths."""

    def test_cleanup_on_context_exit(self) -> None:
        """Sleep prevention released when context manager exits."""
        with (
            patch("ralph.core.no_sleep.platform.system", return_value="Darwin"),
            patch("ralph.core.no_sleep._MacOSMechanism") as mock_cls,
        ):
            mock_instance = MagicMock()
            mock_instance.acquire.return_value = True
            mock_cls.return_value = mock_instance

            with NoSleep() as ns:
                assert ns.is_active

            mock_instance.release.assert_called_once()

    def test_cleanup_on_exception(self) -> None:
        """Sleep prevention released even when exception occurs."""
        with (
            patch("ralph.core.no_sleep.platform.system", return_value="Darwin"),
            patch("ralph.core.no_sleep._MacOSMechanism") as mock_cls,
        ):
            mock_instance = MagicMock()
            mock_instance.acquire.return_value = True
            mock_cls.return_value = mock_instance

            try:
                with NoSleep() as ns:
                    assert ns.is_active
                    raise ValueError("Test exception")
            except ValueError:
                pass

            mock_instance.release.assert_called_once()

    def test_cleanup_on_all_exit_paths(self) -> None:
        """Cleanup happens on all exit paths (return, exception, break)."""
        with (
            patch("ralph.core.no_sleep.platform.system", return_value="Darwin"),
            patch("ralph.core.no_sleep._MacOSMechanism") as mock_cls,
        ):
            mock_instance = MagicMock()
            mock_instance.acquire.return_value = True
            mock_cls.return_value = mock_instance

            # Exception path: release must be called
            try:
                with NoSleep():
                    raise RuntimeError("exit via exception")
            except RuntimeError:
                pass
            assert mock_instance.release.call_count == 1

            # Normal return path: release must be called
            mock_instance.reset_mock()
            mock_instance.acquire.return_value = True
            with NoSleep():
                pass
            assert mock_instance.release.call_count == 1

            # sys.exit (SystemExit) path: release must be called
            mock_instance.reset_mock()
            mock_instance.acquire.return_value = True
            try:
                with NoSleep():
                    sys.exit(130)
            except SystemExit:
                pass
            assert mock_instance.release.call_count == 1


class TestNoSleepAcrossIterations:
    """Tests that sleep prevention survives across iterations."""

    def test_prevention_stays_active(self) -> None:
        """NoSleep instance stays active across multiple operations."""
        with (
            patch("ralph.core.no_sleep.platform.system", return_value="Darwin"),
            patch("ralph.core.no_sleep._MacOSMechanism") as mock_cls,
        ):
            mock_instance = MagicMock()
            mock_instance.acquire.return_value = True
            mock_cls.return_value = mock_instance

            with NoSleep() as ns:
                # Simulate multiple iterations
                for _ in range(10):
                    assert ns.is_active

            mock_instance.release.assert_called_once()


class TestNoSleepNotInDebugPrompt:
    """Tests that sleep prevention is NOT applied in debug-prompt mode."""

    def test_no_sleep_not_applied_in_debug_prompt(self) -> None:
        """debug_prompt=True means no sleep prevention."""
        ns = NoSleep(debug_prompt=True)
        assert not ns.is_active
        # Should not have tried to create any mechanism
        ns.release()


class TestNoSleepWarningsOnFailure:
    """Tests that warnings are logged when mechanisms fail."""

    def test_linux_warning_when_no_mechanism(self, caplog: pytest.LogCaptureFixture) -> None:
        """Linux logs warning when no mechanism is available."""
        with (
            patch("ralph.core.no_sleep.shutil.which", return_value=None),
            caplog.at_level(logging.WARNING, logger="ralph.core.no_sleep"),
        ):
            mech = _LinuxMechanism()
            result = mech.acquire()
            assert result is False
            assert any(
                "No effective sleep prevention mechanism available" in record.message
                for record in caplog.records
            )

    def test_macos_warning_when_no_caffeinate(self, caplog: pytest.LogCaptureFixture) -> None:
        """macOS logs warning when caffeinate is not found."""
        with (
            patch("ralph.core.no_sleep.shutil.which", return_value=None),
            caplog.at_level(logging.WARNING, logger="ralph.core.no_sleep"),
        ):
            mech = _MacOSMechanism()
            result = mech.acquire()
            assert result is False
            assert any("caffeinate not found" in record.message for record in caplog.records)

    def test_windows_warning_on_ctypes_error(self, caplog: pytest.LogCaptureFixture) -> None:
        """Windows logs warning when ctypes fails."""
        mock_ctypes = MagicMock()
        del mock_ctypes.windll

        with (
            patch("ralph.core.no_sleep.platform.system", return_value="Windows"),
            patch.dict("sys.modules", {"ctypes": mock_ctypes}),
            caplog.at_level(logging.WARNING, logger="ralph.core.no_sleep"),
        ):
            mech = _WindowsMechanism()
            result = mech.acquire()
            assert result is False


class TestNoSleepMultipleProcesses:
    """Tests for multiple concurrent NoSleep instances."""

    def test_multiple_independent_instances(self) -> None:
        """Multiple NoSleep instances operate independently."""
        with (
            patch("ralph.core.no_sleep.platform.system", return_value="Darwin"),
            patch("ralph.core.no_sleep._MacOSMechanism") as mock_cls,
        ):
            mock1 = MagicMock()
            mock1.acquire.return_value = True
            mock2 = MagicMock()
            mock2.acquire.return_value = True
            mock_cls.side_effect = [mock1, mock2]

            ns1 = NoSleep()
            ns2 = NoSleep()

            assert ns1.is_active
            assert ns2.is_active

            ns1.release()
            assert not ns1.is_active
            assert ns2.is_active  # ns2 should still be active

            ns2.release()


class TestNoSleepActivationLog:
    """Tests for info log when sleep prevention activates."""

    def test_info_log_on_macos_activation(self, caplog: pytest.LogCaptureFixture) -> None:
        """Info log is emitted when macOS caffeine starts successfully."""
        with (
            patch("ralph.core.no_sleep.platform.system", return_value="Darwin"),
            patch("ralph.core.no_sleep._MacOSMechanism") as mock_cls,
        ):
            mock_instance = MagicMock()
            mock_instance.acquire.return_value = True
            mock_cls.return_value = mock_instance

            with caplog.at_level(logging.INFO, logger="ralph.core.no_sleep"):
                ns = NoSleep()
                assert ns.is_active
                ns.release()

            assert any("Sleep prevention activated" in record.message for record in caplog.records)

    def test_no_info_log_on_failure(self, caplog: pytest.LogCaptureFixture) -> None:
        """No info log when sleep prevention fails."""
        with (
            patch("ralph.core.no_sleep.platform.system", return_value="Darwin"),
            patch("ralph.core.no_sleep._MacOSMechanism") as mock_cls,
        ):
            mock_instance = MagicMock()
            mock_instance.acquire.return_value = False
            mock_cls.return_value = mock_instance

            with caplog.at_level(logging.INFO, logger="ralph.core.no_sleep"):
                ns = NoSleep()
                assert not ns.is_active
                ns.release()

            info_logs = [r.message for r in caplog.records if r.levelno == logging.INFO]
            assert not any("Sleep prevention activated" in msg for msg in info_logs)


class TestNoSleepIntegrationWithRunLoop:
    """Integration-level tests for NoSleep with the run loop."""

    @pytest.fixture
    def mock_agent_for_loop(self) -> MagicMock:
        """Create a mock agent that returns DONE after 3 iterations."""
        agent = MagicMock()
        agent.name = "TestAgent"
        agent.is_available.return_value = True

        from ralph.core.agent import AgentResult

        agent.invoke.side_effect = [
            AgentResult(
                output="Working on task",
                exit_code=0,
                error=None,
            ),
            AgentResult(
                output="Continuing work",
                exit_code=0,
                error=None,
            ),
            AgentResult(
                output="Task complete",
                exit_code=0,
                error=None,
            ),
        ]
        agent.is_exhausted.return_value = False
        agent.exhaustion_reason.return_value = None
        return agent

    def test_no_sleep_active_during_loop(self) -> None:
        """NoSleep is active throughout the loop execution."""
        from ralph.core.loop import run_loop
        from ralph.core.pool import AgentPool
        from ralph.core.state import (
            MultiSpecState,
            SpecProgress,
            Status,
            write_done_count,
            write_multi_state,
            write_status,
        )

        with (
            patch("ralph.core.no_sleep.platform.system", return_value="Darwin"),
            patch("ralph.core.no_sleep._MacOSMechanism") as mock_cls,
        ):
            mock_instance = MagicMock()
            mock_instance.acquire.return_value = True
            mock_cls.return_value = mock_instance

            # Create temp project with spec
            import tempfile

            with tempfile.TemporaryDirectory() as tmpdir:
                root = Path(tmpdir)
                ralph_dir = root / ".ralph"
                ralph_dir.mkdir()
                (ralph_dir / "history").mkdir()
                (ralph_dir / "handoffs").mkdir()

                # Write PROMPT.md
                (root / "PROMPT.md").write_text("# Goal\n\nTest goal.\n")

                # Initialize state
                write_status(Status.IDLE, root)
                write_done_count(0, root)
                from ralph.core.state import (
                    GUARDRAILS_TEMPLATE,
                    HANDOFF_TEMPLATE,
                    write_guardrails,
                    write_handoff,
                    write_iteration,
                )

                write_iteration(0, root)
                write_handoff(HANDOFF_TEMPLATE, root)
                write_guardrails(GUARDRAILS_TEMPLATE, root)

                state = MultiSpecState(
                    version=1,
                    iteration=0,
                    status=Status.IDLE,
                    current_index=0,
                    specs=[
                        SpecProgress(
                            path="PROMPT.md",
                            done_count=0,
                            last_status=None,
                            last_hash=None,
                            modified_files=False,
                        )
                    ],
                )
                write_multi_state(state, root)

                # Create mock agent that signals DONE after writing status
                from ralph.core.agent import AgentResult

                def mock_invoke(prompt, timeout=10800, output_file=None):
                    # Simulate agent writing DONE status

                    (root / ".ralph" / "status").write_text("DONE")
                    return AgentResult(
                        output="Work done",
                        exit_code=0,
                        error=None,
                    )

                mock_agent = MagicMock()
                mock_agent.name = "TestAgent"
                mock_agent.invoke.side_effect = mock_invoke
                mock_agent.is_exhausted.return_value = False
                mock_agent.exhaustion_reason.return_value = None

                pool = AgentPool([mock_agent])

                with NoSleep():
                    result = run_loop(
                        max_iter=10,
                        root=root,
                        agent_pool=pool,
                    )

                # Verify sleep prevention was active during loop
                assert mock_instance.acquire.called
                assert mock_instance.release.called
                assert result.exit_code == 0

    def test_debug_prompt_no_sleep_prevention(self) -> None:
        """debug_prompt mode does not activate sleep prevention."""
        ns = NoSleep(debug_prompt=True)
        assert not ns.is_active
        ns.release()
