"""Docker sandbox executor — where the Engineer agent's generated code runs.

Isolation: no network, a memory/CPU cap, a wall-clock timeout, and only the run's workdir
mounted at /work. The image digest is returned so it can be recorded in the run's
reproducibility manifest. If Docker or the image is unavailable, callers get a clear
`SandboxUnavailable` rather than a silent fallback (never fake execution).
"""

from __future__ import annotations

import os
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

SANDBOX_IMAGE = os.getenv("LABORATREE_SANDBOX_IMAGE", "laboratree-sandbox:latest")


class SandboxUnavailable(RuntimeError):
    pass


@dataclass
class SandboxResult:
    exit_code: int
    stdout: str
    image_digest: str
    artifacts: list[str] = field(default_factory=list)  # filenames written to /work

    @property
    def ok(self) -> bool:
        return self.exit_code == 0


def is_available() -> bool:
    try:
        import docker

        client = docker.from_env()
        client.ping()
        client.images.get(SANDBOX_IMAGE)
        return True
    except Exception:
        return False


def run_code(
    code: str,
    *,
    timeout: int = 120,
    mem_limit: str = "512m",
    nano_cpus: int = 1_000_000_000,  # 1 CPU
    input_files: dict[str, bytes] | None = None,
) -> SandboxResult:
    try:
        import docker
        from docker.errors import ImageNotFound
    except ImportError as exc:  # pragma: no cover
        raise SandboxUnavailable("docker SDK not installed") from exc

    try:
        client = docker.from_env()
        client.ping()
    except Exception as exc:
        raise SandboxUnavailable(f"docker daemon unreachable: {exc}") from exc

    try:
        image = client.images.get(SANDBOX_IMAGE)
    except ImageNotFound as exc:
        raise SandboxUnavailable(
            f"sandbox image '{SANDBOX_IMAGE}' not built — "
            f"run: docker build -t {SANDBOX_IMAGE} -f infra/sandbox.Dockerfile ."
        ) from exc

    with tempfile.TemporaryDirectory(prefix="sandbox-") as tmp:
        work = Path(tmp)
        (work / "main.py").write_text(code, encoding="utf-8")
        for name, data in (input_files or {}).items():
            (work / name).write_bytes(data)

        container = client.containers.run(
            SANDBOX_IMAGE,
            command=["python", "/work/main.py"],
            volumes={str(work): {"bind": "/work", "mode": "rw"}},
            working_dir="/work",
            network_disabled=True,
            mem_limit=mem_limit,
            nano_cpus=nano_cpus,
            detach=True,
        )
        try:
            result = container.wait(timeout=timeout)
            exit_code = int(result.get("StatusCode", 1))
            logs = container.logs().decode(errors="replace")
        except Exception as exc:
            try:
                container.kill()
            except Exception:
                pass
            raise SandboxUnavailable(f"sandbox run failed/timed out: {exc}") from exc
        finally:
            try:
                container.remove(force=True)
            except Exception:
                pass

        produced = sorted(
            p.name for p in work.iterdir() if p.is_file() and p.name != "main.py"
        )

    digest = image.id if isinstance(image.id, str) else ""
    return SandboxResult(exit_code=exit_code, stdout=logs, image_digest=digest, artifacts=produced)
