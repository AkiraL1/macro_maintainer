"""Subprocess stdout decoding for Windows (UTF-8 + locale fallback)."""
from __future__ import annotations

import locale
import os
import sys
from typing import Literal

JobKind = Literal["cli", "powershell"]


def build_subprocess_env(base: dict[str, str] | None = None) -> dict[str, str]:
    env = dict(base or os.environ)
    env["PYTHONIOENCODING"] = "utf-8"
    env["PYTHONUTF8"] = "1"
    return env


def preferred_fallback_encoding() -> str:
    if sys.platform == "win32":
        for name in ("gbk", "cp936"):
            try:
                "测".encode(name)
                return name
            except LookupError:
                continue
    return locale.getpreferredencoding(False) or "utf-8"


def decode_subprocess_bytes(raw: bytes, job_kind: JobKind) -> str:
    if not raw:
        return ""
    encodings: list[str]
    if job_kind == "cli":
        encodings = ["utf-8", preferred_fallback_encoding()]
    else:
        encodings = ["utf-8", preferred_fallback_encoding(), "gbk", "cp936"]
    seen: set[str] = set()
    for enc in encodings:
        if enc in seen:
            continue
        seen.add(enc)
        try:
            return raw.decode(enc)
        except (UnicodeDecodeError, LookupError):
            continue
    return raw.decode("utf-8", errors="replace")


def powershell_command(script: str, project_root: str, extra_args: tuple[str, ...]) -> list[str]:
    """Run a .ps1 script with UTF-8 console output on Windows."""
    arg_parts: list[str] = [
        "-WorkspaceRoot",
        _quote_ps(project_root),
        *[a if a.startswith("-") else _quote_ps(a) for a in extra_args],
    ]
    invoke_args = " ".join(arg_parts)
    script_escaped = script.replace("'", "''")
    ps = (
        "[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new($false); "
        "$OutputEncoding = [Console]::OutputEncoding; "
        f"& '{script_escaped}' {invoke_args}"
    )
    return [
        "powershell.exe",
        "-NoProfile",
        "-ExecutionPolicy",
        "Bypass",
        "-Command",
        ps,
    ]


def _quote_ps(value: str) -> str:
    if not value or value.startswith('"') and value.endswith('"'):
        return value
    escaped = value.replace("'", "''")
    return f"'{escaped}'"
