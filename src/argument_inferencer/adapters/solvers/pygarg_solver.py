"""
Solver adapter for `pygarg` (https://github.com/jgmailly/pygarg,
SAT-based via PySAT).

Design decision: executed via the documented CLI
(`pygarg -p EE-<SEM> -fo apx -f <file>`) rather than internal Python APIs.
The CLI is fully documented, robust against internal breaking changes across
pygarg releases, and decouples solver subprocess management.
"""

from __future__ import annotations

import re
import shutil
import subprocess
import tempfile
from pathlib import Path
from typing import List, Set

from argument_inferencer.core.models import ArgumentationFramework
from argument_inferencer.core.solver import Semantics, UnsupportedSemanticsError


class PygargNotAvailableError(RuntimeError):
    """The `pygarg` CLI binary was not found in PATH."""


def _to_apx(af: ArgumentationFramework) -> str:
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

    valid_ids = set(safe_id_by_original)
    for attack in af.attacks:
        if attack.attacker_id in safe_id_by_original and attack.target_id in safe_id_by_original:
            lines.append(
                f"att({safe_id_by_original[attack.attacker_id]},"
                f"{safe_id_by_original[attack.target_id]})."
            )

    return "\n".join(lines) + "\n", original_by_safe_id


def _parse_extensions(raw_output: str, original_by_safe_id: dict) -> List[Set[str]]:
    """
    Parses output: extracts each "[...]" bracket as one extension and
    splits contents by comma or whitespace. Empty brackets ("[]") become empty extensions.
    """
    extensions: List[Set[str]] = []

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

        if shutil.which(binary) is None:
            raise PygargNotAvailableError(
                f"'{binary}' was not found in PATH. "
                f"Install it with: pip install pygarg"
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
            result = subprocess.run(
                [
                    self.binary,
                    "-p",
                    f"EE-{semantics.value}",
                    "-fo",
                    "apx",
                    "-f",
                    str(tmp_path),
                ],
                capture_output=True,
                text=True,
                timeout=self.timeout_seconds,
                check=False,
            )
        finally:
            tmp_path.unlink(missing_ok=True)

        if result.returncode != 0:
            raise RuntimeError(
                f"pygarg exited with code {result.returncode}: "
                f"{result.stderr.strip()}"
            )

        return _parse_extensions(result.stdout, original_by_safe_id)
