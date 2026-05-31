"""
DOCKER MANAGER — Container Lifecycle Engine
Part of the Trishula Sovereign PaaS (Gap 1)

Handles:
    - Building Docker images from a Dockerfile
    - Running containers with dynamic port allocation
    - Health checking running containers
    - Stopping and removing containers
    - Port conflict detection and resolution

Uses the Docker SDK for Python (docker-py).
"""

import logging
import socket
import time
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

try:
    import docker
    from docker.errors import (
        APIError,
        BuildError,
        ContainerError,
        ImageNotFound,
        NotFound,
    )
    HAS_DOCKER = True
except ImportError:
    HAS_DOCKER = False

logger = logging.getLogger("Sovereign.Docker")


# ─── Data Models ─────────────────────────────────────────────────────────────

@dataclass
class ContainerInfo:
    """Information about a running container."""
    container_id: str
    image_tag: str
    app_name: str
    host_port: int
    container_port: int
    status: str


# ─── Port Allocator ─────────────────────────────────────────────────────────

class PortAllocator:
    """Finds available ports on the host machine."""

    # Range reserved for Sovereign PaaS deployments
    PORT_RANGE_START = 9000
    PORT_RANGE_END = 9999

    def __init__(self):
        self._allocated: set[int] = set()
        self.logger = logging.getLogger("Sovereign.Ports")

    def allocate(self, preferred: Optional[int] = None) -> int:
        """Find and allocate an available port.

        Args:
            preferred: Try this port first if specified

        Returns:
            An available port number
        """
        if preferred and self._is_available(preferred):
            self._allocated.add(preferred)
            return preferred

        for port in range(self.PORT_RANGE_START, self.PORT_RANGE_END + 1):
            if port not in self._allocated and self._is_available(port):
                self._allocated.add(port)
                self.logger.debug("Allocated port: %d", port)
                return port

        raise RuntimeError(
            f"No available ports in range {self.PORT_RANGE_START}-{self.PORT_RANGE_END}"
        )

    def release(self, port: int):
        """Release a previously allocated port."""
        self._allocated.discard(port)

    @staticmethod
    def _is_available(port: int) -> bool:
        """Check if a port is available on the host."""
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            try:
                sock.bind(("127.0.0.1", port))
                return True
            except OSError:
                return False


# ─── Docker Manager ──────────────────────────────────────────────────────────

class DockerManager:
    """
    Manages Docker images and containers for the Sovereign PaaS.
    """

    # Default container ports for common stacks
    DEFAULT_PORTS = {
        "python": 8000,
        "node": 3000,
        "go": 8080,
        "rust": 8080,
        "static": 80,
    }

    def __init__(self, lazy: bool = True):
        if not HAS_DOCKER:
            raise ImportError(
                "Docker SDK is not installed. Run: pip install docker"
            )
        self.logger = logging.getLogger("Sovereign.Docker")
        self.port_allocator = PortAllocator()
        self._client = None

        if not lazy:
            _ = self.client  # Force connection

    @property
    def client(self):
        """Lazy-connect to Docker daemon on first use."""
        if self._client is None:
            try:
                self._client = docker.from_env()
                self._client.ping()
                self.logger.debug("Docker daemon connected")
            except Exception as e:
                self.logger.error("Cannot connect to Docker daemon: %s", e)
                raise
        return self._client

    def build_image(self, repo_path: Path, tag: str) -> str:
        """Build a Docker image from a directory with a Dockerfile.

        Args:
            repo_path: Path to the directory containing the Dockerfile
            tag: Image tag (e.g., sovereign-myapp:latest)

        Returns:
            Image ID

        Raises:
            BuildError: If the build fails
        """
        self.logger.info("Building image '%s' from %s...", tag, repo_path)

        try:
            image, build_logs = self.client.images.build(
                path=str(repo_path),
                tag=tag,
                rm=True,            # Remove intermediate containers
                forcerm=True,       # Force remove on failure
                pull=False,         # Don't auto-pull base images (offline-friendly)
            )

            # Log build output
            for chunk in build_logs:
                if "stream" in chunk:
                    line = chunk["stream"].strip()
                    if line:
                        self.logger.debug("  build │ %s", line)
                elif "error" in chunk:
                    self.logger.error("  build │ ERROR: %s", chunk["error"])

            self.logger.info("Image built: %s (%s)", tag, image.short_id)
            return image.id

        except BuildError as e:
            self.logger.error("Build failed: %s", e)
            for log in e.build_log:
                if "error" in log:
                    self.logger.error("  build │ %s", log.get("error", ""))
            raise
        except APIError as e:
            self.logger.error("Docker API error during build: %s", e)
            raise

    def run_container(
        self,
        image_tag: str,
        app_name: str,
        port: Optional[int] = None,
        env_vars: Optional[dict] = None,
        container_port: int = 8000,
        cpus: Optional[str] = None,
    ) -> ContainerInfo:
        """Start a container from the given image.

        Args:
            image_tag: Image to run
            app_name: Application name (used as container name)
            port: Specific host port (auto-allocated if None)
            env_vars: Environment variables to set
            container_port: Port the app listens on inside the container
            cpus: CPU cores to pin to (e.g., "0-3", "0,1")

        Returns:
            ContainerInfo with the running container details
        """
        container_name = f"sovereign-{app_name}"

        # Remove existing container with the same name
        self._remove_existing(container_name)

        # Allocate host port
        host_port = self.port_allocator.allocate(preferred=port)

        # Detect container port from image EXPOSE directive
        try:
            image = self.client.images.get(image_tag)
            exposed = image.attrs.get("Config", {}).get("ExposedPorts", {})
            if exposed:
                # Take the first exposed port
                first_port = list(exposed.keys())[0]
                container_port = int(first_port.split("/")[0])
                self.logger.debug("Auto-detected container port: %d", container_port)
        except Exception:
            pass

        self.logger.info(
            "Starting container '%s' (port %d -> %d)%s...",
            container_name, host_port, container_port,
            f" on cores {cpus}" if cpus else "",
        )

        try:
            container = self.client.containers.run(
                image=image_tag,
                name=container_name,
                detach=True,
                ports={f"{container_port}/tcp": host_port},
                environment=env_vars or {},
                restart_policy={"Name": "unless-stopped"},
                cpuset_cpus=cpus,
                mem_limit="512m",        # [SOVEREIGN ISOLATION] Hard limit at 512MB
                memswap_limit="512m",    # Disable swap for absolute determinism
                labels={
                    "sovereign.app": app_name,
                    "sovereign.managed": "true",
                    "sovereign.port": str(host_port),
                },
            )

            self.logger.info(
                "Container started: %s (%s)",
                container.short_id, container_name,
            )

            return ContainerInfo(
                container_id=container.id,
                image_tag=image_tag,
                app_name=app_name,
                host_port=host_port,
                container_port=container_port,
                status="running",
            )

        except ContainerError as e:
            self.port_allocator.release(host_port)
            self.logger.error("Container error: %s", e)
            raise
        except APIError as e:
            self.port_allocator.release(host_port)
            self.logger.error("Docker API error: %s", e)
            raise

    def stop_container(self, container_id: str, timeout: int = 10):
        """Stop and remove a container.

        Args:
            container_id: Container ID or name
            timeout: Seconds to wait before killing
        """
        try:
            container = self.client.containers.get(container_id)
            container.stop(timeout=timeout)
            container.remove(force=True)
            self.logger.info("Container stopped and removed: %s", container_id[:12])
        except NotFound:
            self.logger.debug("Container not found: %s", container_id[:12])
        except APIError as e:
            self.logger.warning("Error stopping container %s: %s", container_id[:12], e)

    def health_check(
        self,
        container_id: str,
        retries: int = 5,
        interval: float = 2.0,
    ) -> bool:
        """Check if a container is running and healthy.

        Args:
            container_id: Container ID
            retries: Number of health check attempts
            interval: Seconds between attempts

        Returns:
            True if the container is running
        """
        for attempt in range(1, retries + 1):
            try:
                container = self.client.containers.get(container_id)
                status = container.status

                if status == "running":
                    self.logger.debug(
                        "Health check %d/%d: RUNNING", attempt, retries
                    )
                    return True
                elif status in ("exited", "dead"):
                    logs = container.logs(tail=10).decode("utf-8", errors="ignore")
                    self.logger.error(
                        "Container died (status=%s). Tail:\n%s", status, logs
                    )
                    return False
                else:
                    self.logger.debug(
                        "Health check %d/%d: status=%s, waiting...",
                        attempt, retries, status,
                    )

            except NotFound:
                self.logger.error("Container not found: %s", container_id[:12])
                return False

            time.sleep(interval)

        return False

    def list_containers(self) -> list[ContainerInfo]:
        """List all Sovereign-managed containers."""
        containers = self.client.containers.list(
            all=True,
            filters={"label": "sovereign.managed=true"},
        )
        results = []
        for c in containers:
            labels = c.labels
            ports = c.ports or {}
            host_port = 0
            for port_bindings in ports.values():
                if port_bindings:
                    host_port = int(port_bindings[0]["HostPort"])
                    break

            results.append(ContainerInfo(
                container_id=c.id,
                image_tag=c.image.tags[0] if c.image.tags else "",
                app_name=labels.get("sovereign.app", "unknown"),
                host_port=host_port,
                container_port=0,
                status=c.status,
            ))
        return results

    def _remove_existing(self, container_name: str):
        """Remove an existing container with the given name."""
        try:
            existing = self.client.containers.get(container_name)
            self.logger.debug("Removing existing container: %s", container_name)
            existing.stop(timeout=5)
            existing.remove(force=True)
        except NotFound:
            pass
        except APIError as e:
            self.logger.warning("Error removing container %s: %s", container_name, e)

    def get_logs(self, container_id: str, tail: int = 50) -> str:
        """Get container logs.

        Args:
            container_id: Container ID
            tail: Number of lines to return

        Returns:
            Log output as a string
        """
        try:
            container = self.client.containers.get(container_id)
            return container.logs(tail=tail).decode("utf-8", errors="ignore")
        except NotFound:
            return f"Container not found: {container_id}"
        except APIError as e:
            return f"Error getting logs: {e}"
