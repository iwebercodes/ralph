"""No-sleep mode: prevent OS from entering sleep while Ralph is running.

Cross-platform sleep prevention mechanism. On Linux, uses systemd-inhibit
with a DBus fallback. On macOS, uses caffeinate -dims. On Windows, uses
SetThreadExecutionState via ctypes.

Sleep prevention is automatically released when the NoSleep instance is
deleted or when release() is called.

Note: the spec mentions `loginctl inhibit`, but that subcommand does not
exist in systemd's loginctl. The functionally equivalent binary is
`systemd-inhibit`, which is what this module uses. See
.ralph/handoffs/no-sleep-mode.spec-b57f52.md for the deviation rationale.
"""

from __future__ import annotations

import contextlib
import logging
import platform
import shutil
import subprocess  # nosec B404 - controlled internal usage
import time
from abc import ABC, abstractmethod
from typing import Any

logger = logging.getLogger(__name__)


class _SleepPreventionMechanism(ABC):
    """Abstract base for platform-specific sleep prevention mechanisms."""

    @abstractmethod
    def acquire(self) -> bool:
        """Attempt to acquire sleep prevention. Returns True on success."""

    @abstractmethod
    def release(self) -> None:
        """Release sleep prevention."""


class _LinuxMechanism(_SleepPreventionMechanism):
    """Linux sleep prevention via systemd-inhibit.

    Uses `systemd-inhibit` (systemd-logind) to wrap a long-running child
    command. systemd-logind holds the inhibitor for the lifetime of that
    child, so we keep a `sleep infinity` child alive and terminate it on
    release.

    Fallback chain (in order):
        1. `systemd-inhibit --what=sleep ... sleep infinity` — the only
           mechanism that actually holds the inhibitor for a CLI tool.
        2. `xdg-screensaver suspend WINDOWID` — spec-mandated fallback.
           This requires a WindowID, which Ralph (a CLI tool) does not
           have. The call is attempted for spec compliance but is expected
           to fail in CLI context.
        3. `busctl --system call org.freedesktop.login1 ... Inhibit ...` —
           direct DBus invocation. The Inhibit method returns a file
           descriptor whose lifetime owns the lock. busctl prints the FD
           and exits, immediately releasing the inhibitor. This path is
           attempted for spec compliance but cannot hold the inhibitor.
    """

    def __init__(self) -> None:
        self._inhibit_process: subprocess.Popen[bytes] | None = None
        self._dbus_inhibit_called = False

    def acquire(self) -> bool:
        # Priority 1: systemd-inhibit holding a long-running child process.
        if shutil.which("systemd-inhibit"):
            try:
                self._inhibit_process = subprocess.Popen(  # nosec B603 B607 - controlled args; binary verified via shutil.which
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
                # Give the child a brief moment to start, then check it's
                # still running. We must NOT wait() — that would block
                # until `sleep infinity` exits, which is the wrong
                # semantics. poll() is non-blocking.
                time.sleep(0.2)
                if self._inhibit_process.poll() is None:
                    logger.debug(
                        "Linux: systemd-inhibit running (PID %d)",
                        self._inhibit_process.pid,
                    )
                    return True
                else:
                    logger.warning(
                        "Linux: systemd-inhibit exited unexpectedly (exit %d). "
                        "The system may enter sleep during long runs.",
                        self._inhibit_process.returncode,
                    )
                    self._inhibit_process = None
            except OSError as e:
                logger.warning(
                    "Linux: systemd-inhibit error: %s. "
                    "The system may enter sleep during long runs.",
                    e,
                )
                self._inhibit_process = None

        # Priority 2: xdg-screensaver suspend. This requires a WindowID
        # argument that a CLI tool doesn't have, so it's expected to fail
        # in CLI context. We attempt it for spec compliance.
        if shutil.which("xdg-screensaver"):
            try:
                result = subprocess.run(  # nosec B603 B607 - controlled args; binary verified via shutil.which
                    ["xdg-screensaver", "suspend"],
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    logger.debug("Linux: xdg-screensaver suspend successful")
                    return True
                else:
                    logger.warning(
                        "Linux: xdg-screensaver suspend failed (exit %d). "
                        "This fallback requires a WindowID and cannot work for CLI tools.",
                        result.returncode,
                    )
            except (subprocess.TimeoutExpired, OSError) as e:
                logger.debug("Linux: xdg-screensaver suspend error: %s", e)

        # Priority 3: DBus org.freedesktop.login1.Manager.Inhibit via busctl.
        # The Inhibit method signature is `Inhibit(in s what, in s who,
        # in s why, in s mode)`. login1 lives on the SYSTEM bus, not the
        # user bus. Even with correct args, busctl prints the returned
        # FD and exits, which releases the inhibitor. This path is
        # attempted for spec compliance but cannot hold the inhibitor.
        try:
            if shutil.which("busctl"):
                result = subprocess.run(  # nosec B603 B607 - controlled args; binary verified via shutil.which
                    [
                        "busctl",
                        "--system",
                        "call",
                        "org.freedesktop.login1",
                        "/org/freedesktop/login1",
                        "org.freedesktop.login1.Manager",
                        "Inhibit",
                        "ssss",
                        "sleep",
                        "ralph",
                        "preventing sleep during Ralph run",
                        "block",
                    ],
                    capture_output=True,
                    timeout=10,
                )
                if result.returncode == 0:
                    self._dbus_inhibit_called = True
                    # NB: busctl prints the FD to stdout and exits, which
                    # releases the inhibitor immediately. The call
                    # succeeded but did not hold the lock. We do not
                    # claim true success here.
                    logger.warning(
                        "Linux: DBus login1.Inhibit returned a handle, but busctl "
                        "released it on exit (FD lifetime). This fallback cannot "
                        "hold an inhibitor; only systemd-inhibit can."
                    )
        except (subprocess.TimeoutExpired, OSError) as e:
            logger.debug("Linux: DBus login1.Inhibit not available: %s", e)

        logger.warning(
            "Linux: No effective sleep prevention mechanism available. "
            "(systemd-inhibit not found or failed, xdg-screensaver requires WindowID, "
            "DBus busctl cannot hold inhibitor). The system may enter sleep during long runs."
        )
        return False

    def release(self) -> None:
        if self._inhibit_process is not None:
            try:
                self._inhibit_process.terminate()
                self._inhibit_process.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                with contextlib.suppress(OSError):
                    self._inhibit_process.kill()
            self._inhibit_process = None
        if self._dbus_inhibit_called:
            # busctl already exited; the inhibitor was released on FD close.
            # No explicit unlock call is needed (and none is possible without
            # holding the FD).
            self._dbus_inhibit_called = False


class _MacOSMechanism(_SleepPreventionMechanism):
    """macOS sleep prevention via caffeinate."""

    def __init__(self) -> None:
        self._process: subprocess.Popen[bytes] | None = None

    def acquire(self) -> bool:
        if not shutil.which("caffeinate"):
            logger.warning(
                "macOS: caffeinate not found. The system may enter sleep during long runs."
            )
            return False
        try:
            self._process = subprocess.Popen(  # nosec B603 B607 - controlled args; binary verified via shutil.which
                ["caffeinate", "-dims"],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            logger.debug("macOS: caffeinate -dims started (PID %d)", self._process.pid)
            return True
        except OSError as e:
            logger.warning("macOS: caffeinate failed: %s", e)
            return False

    def release(self) -> None:
        if self._process is not None:
            try:
                self._process.terminate()
                self._process.wait(timeout=5)
            except (subprocess.TimeoutExpired, OSError):
                with contextlib.suppress(OSError):
                    self._process.kill()
            self._process = None


class _WindowsMechanism(_SleepPreventionMechanism):
    """Windows sleep prevention via SetThreadExecutionState."""

    # ES flags
    ES_CONTINUOUS = 0x80000000
    ES_SYSTEM_REQUIRED = 0x00000001
    ES_DISPLAY_REQUIRED = 0x00000002

    def __init__(self) -> None:
        self._kernel32: Any = None
        self._was_active = False

    def acquire(self) -> bool:
        try:
            import ctypes

            kernel32 = ctypes.windll.kernel32  # type: ignore[attr-defined, unused-ignore]
            result = kernel32.SetThreadExecutionState(
                self.ES_CONTINUOUS | self.ES_SYSTEM_REQUIRED | self.ES_DISPLAY_REQUIRED
            )
            if result != 0:
                self._kernel32 = kernel32
                self._was_active = True
                logger.debug("Windows: SetThreadExecutionState successful")
                return True
            else:
                logger.warning(
                    "Windows: SetThreadExecutionState returned 0 (error: %s)",
                    ctypes.get_last_error(),  # type: ignore[attr-defined, unused-ignore]
                )
                return False
        except (AttributeError, OSError) as e:
            logger.warning("Windows: SetThreadExecutionState failed: %s", e)
            return False

    def release(self) -> None:
        if self._was_active and self._kernel32 is not None:
            with contextlib.suppress(OSError):
                self._kernel32.SetThreadExecutionState(self.ES_CONTINUOUS)
            self._kernel32 = None
            self._was_active = False


class NoSleep:
    """Cross-platform sleep prevention for Ralph's main loop.

    Acquires sleep prevention on construction and releases it on cleanup.
    Works automatically — no configuration needed.

    Usage::

        with NoSleep():
            # Ralph runs here, OS stays awake
            run_loop(...)

    Or manually::

        ns = NoSleep()
        try:
            run_loop(...)
        finally:
            ns.release()
    """

    def __init__(self, *, debug_prompt: bool = False) -> None:
        """Initialize sleep prevention.

        Args:
            debug_prompt: If True, skip sleep prevention (debug mode doesn't
                          invoke agents or run the loop).
        """
        self._mechanism: _SleepPreventionMechanism | None = None
        self._acquired = False
        self._debug_prompt = debug_prompt

        if not debug_prompt:
            self._acquire()

    def _acquire(self) -> None:
        """Create and acquire the appropriate mechanism for this platform."""
        sys_name = platform.system()

        if sys_name == "Linux":
            self._mechanism = _LinuxMechanism()
        elif sys_name == "Darwin":
            self._mechanism = _MacOSMechanism()
        elif sys_name == "Windows":
            self._mechanism = _WindowsMechanism()
        else:
            logger.warning("Unknown platform '%s'. Sleep prevention not available.", sys_name)
            return

        if self._mechanism is not None:
            self._acquired = self._mechanism.acquire()
            if self._acquired:
                logger.info("Sleep prevention activated (OS will stay awake)")

    def release(self) -> None:
        """Release sleep prevention."""
        if self._mechanism is not None:
            self._mechanism.release()
            self._mechanism = None
        self._acquired = False

    def __enter__(self) -> NoSleep:
        return self

    def __exit__(self, *args: object) -> None:
        self.release()

    @property
    def is_active(self) -> bool:
        """True if sleep prevention is currently active."""
        return self._acquired and self._mechanism is not None
