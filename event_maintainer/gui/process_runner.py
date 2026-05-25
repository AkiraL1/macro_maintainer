"""Background subprocess runner with queue-based UI updates."""
from __future__ import annotations

import queue
import subprocess
import sys
import threading
from dataclasses import dataclass
from pathlib import Path
from typing import Callable, Literal

from event_maintainer.gui.encoding_utils import (
    build_subprocess_env,
    decode_subprocess_bytes,
    powershell_command,
)

JobKind = Literal["cli", "powershell"]


@dataclass(frozen=True)
class RunJob:
    kind: JobKind
    label: str
    cli_command: str | None = None
    ps_script: str | None = None
    ps_extra_args: tuple[str, ...] = ()


def cli_job(command: str, label: str | None = None) -> RunJob:
    return RunJob(kind="cli", label=label or command, cli_command=command)


def ps_job(script_rel: str, label: str | None = None, *extra: str) -> RunJob:
    return RunJob(
        kind="powershell",
        label=label or script_rel,
        ps_script=script_rel,
        ps_extra_args=extra,
    )


class ProcessRunner:
    def __init__(self, project_root: Path) -> None:
        self.project_root = project_root
        self._queue: queue.Queue[tuple[str, object]] = queue.Queue()
        self._process: subprocess.Popen[bytes] | None = None
        self._current_job_kind: JobKind = "cli"
        self._thread: threading.Thread | None = None
        self._running = False

    @property
    def is_running(self) -> bool:
        return self._running

    def run(self, job: RunJob) -> bool:
        if self._running:
            return False
        self._running = True
        self._queue.put(("started", job.label))
        self._thread = threading.Thread(target=self._worker, args=(job,), daemon=True)
        self._thread.start()
        return True

    def terminate(self) -> None:
        proc = self._process
        if proc is not None and proc.poll() is None:
            proc.terminate()

    def poll_queue(self, handler: Callable[[str, object], None]) -> None:
        while True:
            try:
                kind, payload = self._queue.get_nowait()
            except queue.Empty:
                break
            handler(kind, payload)

    def _worker(self, job: RunJob) -> None:
        env = build_subprocess_env()
        self._current_job_kind = job.kind
        try:
            if job.kind == "cli":
                cmd = [
                    sys.executable,
                    "-m",
                    "event_maintainer.main",
                    job.cli_command or "",
                ]
                self._run_process(cmd, env, job.kind)
            else:
                script = self.project_root / (job.ps_script or "")
                cmd = powershell_command(
                    str(script),
                    str(self.project_root),
                    job.ps_extra_args,
                )
                self._run_process(cmd, env, job.kind)
        except Exception as exc:
            self._queue.put(("line", f"[error] {exc}\n"))
            self._queue.put(("finished", 1))
        finally:
            self._running = False

    def _run_process(self, cmd: list[str], env: dict[str, str], job_kind: JobKind) -> None:
        self._queue.put(("line", f"$ {' '.join(cmd)}\n\n"))
        self._process = subprocess.Popen(
            cmd,
            cwd=self.project_root,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            bufsize=0,
        )
        assert self._process.stdout is not None
        while True:
            raw = self._process.stdout.readline()
            if not raw:
                break
            self._queue.put(("line", decode_subprocess_bytes(raw, job_kind)))
        code = self._process.wait()
        self._process = None
        self._queue.put(("finished", code))
