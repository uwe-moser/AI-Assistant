"""Docker-sandboxed Python REPL.

Executes user-supplied Python code inside an ephemeral Docker container
so the host machine is never exposed to arbitrary code execution.
"""

import os
import logging
import docker
from docker.errors import ContainerError, ImageNotFound, APIError

from langchain_core.tools import BaseTool

logger = logging.getLogger(__name__)

# Defaults (overridable via env vars)
_IMAGE_NAME = os.getenv("REPL_DOCKER_IMAGE", "apexflow-python-sandbox")
_DOCKERFILE = os.getenv(
    "REPL_DOCKERFILE",
    os.path.join(os.path.dirname(os.path.dirname(__file__)), "Dockerfile.python-sandbox"),
)
_TIMEOUT = int(os.getenv("REPL_TIMEOUT", "30"))  # seconds
_MEM_LIMIT = os.getenv("REPL_MEM_LIMIT", "256m")


def _ensure_image(client: docker.DockerClient, image: str, dockerfile: str) -> None:
    """Build the sandbox image if it doesn't already exist."""
    try:
        client.images.get(image)
    except ImageNotFound:
        logger.info("Building sandbox image '%s' from %s …", image, dockerfile)
        build_dir = os.path.dirname(dockerfile)
        client.images.build(
            path=build_dir,
            dockerfile=os.path.basename(dockerfile),
            tag=image,
            rm=True,
        )


class DockerPythonREPL(BaseTool):
    """A Python REPL that runs code inside a Docker container.

    The container is ephemeral: created for each execution and removed
    immediately afterwards.  Resource limits (memory, CPU, timeout) are
    enforced so that runaway code cannot affect the host.
    """

    name: str = "Python_REPL"
    description: str = (
        "A Python shell. Use this to execute python commands. "
        "Input should be a valid python command. "
        "If you want to see the output of a value, you should print it out with `print(...)`."
    )

    image: str = _IMAGE_NAME
    dockerfile: str = _DOCKERFILE
    timeout: int = _TIMEOUT
    mem_limit: str = _MEM_LIMIT
    sandbox_dir: str = ""

    _client: docker.DockerClient | None = None

    class Config:
        arbitrary_types_allowed = True

    # -- helpers --------------------------------------------------------

    def _get_client(self) -> docker.DockerClient:
        if self._client is None:
            object.__setattr__(self, "_client", docker.from_env())
        return self._client

    def _run_in_container(self, code: str) -> str:
        client = self._get_client()
        _ensure_image(client, self.image, self.dockerfile)

        volumes = {}
        if self.sandbox_dir:
            abs_sandbox = os.path.abspath(self.sandbox_dir)
            volumes[abs_sandbox] = {"bind": "/home/sandbox/data", "mode": "rw"}

        try:
            output = client.containers.run(
                image=self.image,
                command=["python3", "-u", "-c", code],
                stdin_open=False,
                stdout=True,
                stderr=True,
                remove=True,
                network_disabled=True,
                mem_limit=self.mem_limit,
                nano_cpus=int(1e9),  # 1 CPU core
                pids_limit=64,
                volumes=volumes,
                timeout=self.timeout,
            )
            return output.decode("utf-8", errors="replace").strip()
        except ContainerError as exc:
            # stderr from a non-zero exit code
            stderr = exc.stderr
            if isinstance(stderr, bytes):
                stderr = stderr.decode("utf-8", errors="replace")
            return stderr.strip()
        except APIError as exc:
            return f"Error: Docker API error — {exc.explanation}"
        except Exception as exc:
            return f"Error: {exc}"

    # -- LangChain interface -------------------------------------------

    def _run(self, query: str) -> str:
        """Execute *query* as Python code inside a Docker container."""
        return self._run_in_container(query)
