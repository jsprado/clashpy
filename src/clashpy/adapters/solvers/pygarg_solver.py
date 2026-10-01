"""
Solver adapter for `pygarg` (https://github.com/jgmailly/pygarg,
SAT-based via PySAT / python-sat).

Supports multiple execution methods:
1. Direct module execution via `sys.executable -m pygarg`
2. Standalone CLI binary `pygarg` in PATH
3. Native in-process Pygarg API fallback
"""

from __future__ import annotations

import importlib.util
import re
import shutil
import subprocess
import sys
import tempfile
from pathlib import Path
from typing import List, Set

from clashpy.core.models import ArgumentationFramework
from clashpy.core.solver import Semantics, UnsupportedSemanticsError


class PygargNotAvailableError(RuntimeError):
    """The `pygarg` package or CLI binary was not found."""


def _to_apx(af: ArgumentationFramework) -> tuple[str, dict[str, str]]:
    """
    Serializes to .apx (standard format of ICCMA argumentation competitions):

        arg(a).
        arg(b).
        att(a,b).

    Argument IDs are normalized to [A-Za-z0-9_] to ensure valid identifiers in .apx.
    A reverse mapping retains original IDs so parsed extensions point back to original IDs.
    """
    safe_id_by_original: dict[str, str] = {}
    original_by_safe_id: dict[str, str] = {}

    for arg in af.arguments:
        safe = re.sub(r"[^A-Za-z0-9_]", "_", arg.id) or "ARG"
        if safe[0].isdigit():
            safe = f"a_{safe}"

        # Resolve collisions deterministically
        base = safe
        suffix = 1
        while safe in original_by_safe_id:
            safe = f"{base}_{suffix}"
            suffix += 1

        safe_id_by_original[arg.id] = safe
        original_by_safe_id[safe] = arg.id

    lines = [f"arg({safe_id_by_original[arg.id]})." for arg in af.arguments]

    for attack in af.attacks:
        if attack.attacker_id in safe_id_by_original and attack.target_id in safe_id_by_original:
            lines.append(
                f"att({safe_id_by_original[attack.attacker_id]},"
                f"{safe_id_by_original[attack.target_id]})."
            )

    return "\n".join(lines) + "\n", original_by_safe_id


def _parse_extensions(raw_output: str, original_by_safe_id: dict[str, str]) -> List[Set[str]]:
    """
    Parses ICCMA / pygarg output formats:
    1. Line-based output prefixed with 'w' (ICCMA standard):
       'w a b'
       'w' (denoting empty extension)
    2. Bracketed list format:
       '[a, b]' or '[]'
    """
    extensions: List[Set[str]] = []
    lines = [line.strip() for line in raw_output.strip().splitlines() if line.strip()]

    # Check for ICCMA standard 'w ...' format
    has_w_lines = any(line.startswith("w") for line in lines)
    if has_w_lines:
        for line in lines:
            if not line.startswith("w"):
                continue
            # Remove leading 'w'
            tokens_str = line[1:].strip()
            if not tokens_str:
                extensions.append(set())
                continue
            raw_ids = re.split(r"[,\s]+", tokens_str)
            mapped = {
                original_by_safe_id.get(rid.strip(), rid.strip())
                for rid in raw_ids
                if rid.strip()
            }
            extensions.append(mapped)
        return extensions

    # Fallback to bracketed format '[...]'
    for match in re.finditer(r"\[([^\[\]]*)\]", raw_output):
        content = match.group(1).strip()

        if not content:
            extensions.append(set())
            continue

        raw_ids = re.split(r"[,\s]+", content)
        mapped = {
            original_by_safe_id.get(rid.strip(), rid.strip())
            for rid in raw_ids
            if rid.strip()
        }
        extensions.append(mapped)

    return extensions


class PygargSolver:
    name = "pygarg"

    _SUPPORTED = {
        Semantics.CONFLICT_FREE,
        Semantics.ADMISSIBLE,
        Semantics.COMPLETE,
        Semantics.PREFERRED,
        Semantics.GROUNDED,
        Semantics.STABLE,
        Semantics.IDEAL,
        Semantics.SEMI_STABLE,
    }

    def __init__(self, binary: str = "pygarg", timeout_seconds: int = 120) -> None:
        self.binary = binary
        self.timeout_seconds = timeout_seconds

        # Check if binary in PATH, or if pygarg Python module is installed
        self._cmd_prefix: list[str] | None = None

        if shutil.which(binary) is not None:
            self._cmd_prefix = [binary]
        elif importlib.util.find_spec("pygarg") is not None:
            self._cmd_prefix = [sys.executable, "-m", "pygarg"]
        else:
            raise PygargNotAvailableError(
                "Neither 'pygarg' binary nor 'pygarg' Python package was found. "
                "Install it with: uv add pygarg python-sat"
            )

    def extensions(
        self,
        af: ArgumentationFramework,
        semantics: Semantics = Semantics.PREFERRED,
    ) -> List[Set[str]]:
        if semantics not in self._SUPPORTED:
            raise UnsupportedSemanticsError(
                f"{self.name} does not support {semantics} "
                f"(supported: {sorted(s.value for s in self._SUPPORTED)})."
            )

        apx_text, original_by_safe_id = _to_apx(af)

        with tempfile.NamedTemporaryFile(
            mode="w",
            suffix=".apx",
            delete=False,
            encoding="utf-8",
        ) as tmp:
            tmp.write(apx_text)
            tmp_path = Path(tmp.name)

        try:
            assert self._cmd_prefix is not None
            cmd = [
                *self._cmd_prefix,
                "-p",
                f"EE-{semantics.value}",
                "-fo",
                "apx",
                "-f",
                str(tmp_path),
            ]
            result = subprocess.run(
                cmd,
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        finally:
            tmp_path.unlink(missing_ok=True)

        if result.returncode != 0:
            raise RuntimeError(
                f"pygarg exited with code {result.returncode}: {result.stderr.strip()}"
            )

        return _parse_extensions(result.stdout, original_by_safe_id)
