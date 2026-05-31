"""
DEPLOY CORE — The Sovereign PaaS Orchestrator
Part of the Trishula Sovereign PaaS (Gap 1: The Heroku-Killer)

The main deployment engine. Takes a Git repository, detects the stack,
generates a Dockerfile if needed, builds a container, assigns a port,
and wires up the reverse proxy — zero configuration required.

Usage:
    python deploy_core.py --repo ../my-app
    python deploy_core.py --repo ../my-app --name my-app --domain my-app.example.com
    python deploy_core.py --repo ../my-app --dry-run
    python deploy_core.py --list
    python deploy_core.py --teardown my-app

Deployment Pipeline:
    1. DETECT  — Identify language/framework from repo contents
    2. PREPARE — Generate Dockerfile if none exists
    3. BUILD   — Build Docker image from the repo
    4. DEPLOY  — Spin up container with dynamic port allocation
    5. ROUTE   — Write Caddy reverse-proxy rule + auto-SSL
    6. VERIFY  — Health check the running service
"""

import argparse
import hashlib
import json
import logging
import re
import sys
import time
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from pathlib import Path
from typing import Optional

from docker_manager import DockerManager, ContainerInfo
from proxy_manager import ProxyManager

# ─── Configuration ───────────────────────────────────────────────────────────

LOG_FORMAT = "%(asctime)s │ %(levelname)-8s │ %(name)-22s │ %(message)s"
LOG_DATE_FORMAT = "%H:%M:%S"
DEPLOY_LOG = "sovereign_deploy.log"
MANIFEST_FILE = ".sovereign-manifest.json"


class StackType(Enum):
    PYTHON = "python"
    NODE = "node"
    GO = "go"
    RUST = "rust"
    STATIC = "static"
    DOCKER = "docker"       # User-provided Dockerfile
    UNKNOWN = "unknown"


@dataclass
class StackDetection:
    """Result of stack detection."""
    stack: StackType
    version: Optional[str] = None
    framework: Optional[str] = None
    entry_point: Optional[str] = None
    confidence: float = 0.0
    signals: list[str] = field(default_factory=list)


@dataclass
class DeployConfig:
    """Configuration for a deployment."""
    repo_path: Path
    app_name: str
    domain: Optional[str] = None
    port: Optional[int] = None
    cpus: Optional[str] = None
    env_vars: dict = field(default_factory=dict)
    dry_run: bool = False
    force_rebuild: bool = False


@dataclass
class DeployResult:
    """Result of a deployment."""
    success: bool
    app_name: str
    stack: str
    container_id: Optional[str] = None
    port: Optional[int] = None
    url: Optional[str] = None
    domain: Optional[str] = None
    duration_ms: int = 0
    error: Optional[str] = None


# ─── Stack Detector ──────────────────────────────────────────────────────────

class StackDetector:
    """Detects the language/framework of a repository."""

    def __init__(self):
        self.logger = logging.getLogger("Sovereign.Detect")

    def detect(self, repo_path: Path) -> StackDetection:
        """Analyze a repository and detect its stack."""
        self.logger.info("Scanning repository: %s", repo_path)

        # Priority 1: User-provided Dockerfile
        if (repo_path / "Dockerfile").exists():
            return StackDetection(
                stack=StackType.DOCKER,
                confidence=1.0,
                signals=["Dockerfile found"],
            )

        # Priority 2: Language-specific detection
        detectors = [
            self._detect_python,
            self._detect_node,
            self._detect_go,
            self._detect_rust,
            self._detect_static,
        ]

        best: Optional[StackDetection] = None
        for detector in detectors:
            result = detector(repo_path)
            if result and (best is None or result.confidence > best.confidence):
                best = result

        if best:
            self.logger.info(
                "Detected: %s (%s) [%.0f%% confidence] — %s",
                best.stack.value, best.framework or "generic",
                best.confidence * 100, ", ".join(best.signals),
            )
            return best

        return StackDetection(
            stack=StackType.UNKNOWN,
            confidence=0.0,
            signals=["No known stack markers found"],
        )

    def _detect_python(self, repo_path: Path) -> Optional[StackDetection]:
        signals = []
        framework = None
        entry_point = None
        version = "3.11"

        if (repo_path / "requirements.txt").exists():
            signals.append("requirements.txt")
            reqs = (repo_path / "requirements.txt").read_text(errors="ignore").lower()
            if "flask" in reqs:
                framework = "flask"
                signals.append("Flask dependency")
            elif "django" in reqs:
                framework = "django"
                signals.append("Django dependency")
            elif "fastapi" in reqs:
                framework = "fastapi"
                signals.append("FastAPI dependency")
            elif "streamlit" in reqs:
                framework = "streamlit"
                signals.append("Streamlit dependency")

        if (repo_path / "pyproject.toml").exists():
            signals.append("pyproject.toml")

        if (repo_path / "Pipfile").exists():
            signals.append("Pipfile")

        # Detect entry points
        for candidate in ["app.py", "main.py", "server.py", "wsgi.py", "manage.py"]:
            if (repo_path / candidate).exists():
                entry_point = candidate
                signals.append(f"Entry: {candidate}")
                break

        if not signals:
            return None

        return StackDetection(
            stack=StackType.PYTHON,
            version=version,
            framework=framework,
            entry_point=entry_point,
            confidence=min(0.5 + len(signals) * 0.15, 1.0),
            signals=signals,
        )

    def _detect_node(self, repo_path: Path) -> Optional[StackDetection]:
        signals = []
        framework = None
        entry_point = "index.js"

        if (repo_path / "package.json").exists():
            signals.append("package.json")
            try:
                pkg = json.loads((repo_path / "package.json").read_text(errors="ignore"))
                deps = {**pkg.get("dependencies", {}), **pkg.get("devDependencies", {})}
                if "next" in deps:
                    framework = "nextjs"
                    signals.append("Next.js")
                elif "express" in deps:
                    framework = "express"
                    signals.append("Express")
                elif "react" in deps:
                    framework = "react"
                    signals.append("React (SPA)")
                elif "vue" in deps:
                    framework = "vue"
                    signals.append("Vue")
                elif "astro" in deps:
                    framework = "astro"
                    signals.append("Astro")

                if "main" in pkg:
                    entry_point = pkg["main"]
                    signals.append(f"Entry: {entry_point}")

                scripts = pkg.get("scripts", {})
                if "start" in scripts:
                    signals.append("start script defined")
            except (json.JSONDecodeError, KeyError):
                pass

        if (repo_path / "yarn.lock").exists():
            signals.append("yarn.lock")
        if (repo_path / "pnpm-lock.yaml").exists():
            signals.append("pnpm-lock.yaml")

        if not signals:
            return None

        return StackDetection(
            stack=StackType.NODE,
            version="20",
            framework=framework,
            entry_point=entry_point,
            confidence=min(0.5 + len(signals) * 0.15, 1.0),
            signals=signals,
        )

    def _detect_go(self, repo_path: Path) -> Optional[StackDetection]:
        signals = []
        if (repo_path / "go.mod").exists():
            signals.append("go.mod")
        if (repo_path / "go.sum").exists():
            signals.append("go.sum")
        if (repo_path / "main.go").exists():
            signals.append("main.go")

        if not signals:
            return None

        return StackDetection(
            stack=StackType.GO,
            version="1.22",
            entry_point="main.go",
            confidence=min(0.5 + len(signals) * 0.2, 1.0),
            signals=signals,
        )

    def _detect_rust(self, repo_path: Path) -> Optional[StackDetection]:
        signals = []
        if (repo_path / "Cargo.toml").exists():
            signals.append("Cargo.toml")
        if (repo_path / "Cargo.lock").exists():
            signals.append("Cargo.lock")

        if not signals:
            return None

        return StackDetection(
            stack=StackType.RUST,
            version="1.77",
            confidence=min(0.6 + len(signals) * 0.2, 1.0),
            signals=signals,
        )

    def _detect_static(self, repo_path: Path) -> Optional[StackDetection]:
        signals = []
        if (repo_path / "index.html").exists():
            signals.append("index.html")
        html_files = list(repo_path.glob("*.html"))
        if len(html_files) > 1:
            signals.append(f"{len(html_files)} HTML files")

        if not signals:
            return None

        return StackDetection(
            stack=StackType.STATIC,
            framework="nginx",
            confidence=0.4 + len(signals) * 0.1,
            signals=signals,
        )


# ─── Dockerfile Generator ───────────────────────────────────────────────────

class DockerfileGenerator:
    """Generates optimized Dockerfiles based on detected stack."""

    def __init__(self):
        self.logger = logging.getLogger("Sovereign.Dockerfile")

    def generate(self, detection: StackDetection, repo_path: Path) -> str:
        """Generate a Dockerfile for the detected stack."""
        generators = {
            StackType.PYTHON: self._gen_python,
            StackType.NODE: self._gen_node,
            StackType.GO: self._gen_go,
            StackType.RUST: self._gen_rust,
            StackType.STATIC: self._gen_static,
        }

        generator = generators.get(detection.stack)
        if not generator:
            raise ValueError(f"Cannot generate Dockerfile for stack: {detection.stack}")

        dockerfile = generator(detection, repo_path)
        self.logger.info("Generated Dockerfile for %s (%s)", detection.stack.value, detection.framework or "generic")
        return dockerfile

    def _gen_python(self, det: StackDetection, repo: Path) -> str:
        version = det.version or "3.11"
        framework = det.framework or "generic"
        entry = det.entry_point or "app.py"

        # Determine the run command
        if framework == "django":
            cmd = 'CMD ["python", "manage.py", "runserver", "0.0.0.0:8000"]'
            expose = "EXPOSE 8000"
        elif framework == "fastapi":
            module = entry.replace(".py", "")
            cmd = f'CMD ["uvicorn", "{module}:app", "--host", "0.0.0.0", "--port", "8000"]'
            expose = "EXPOSE 8000"
        elif framework == "streamlit":
            cmd = f'CMD ["streamlit", "run", "{entry}", "--server.port=8501", "--server.address=0.0.0.0"]'
            expose = "EXPOSE 8501"
        elif framework == "flask":
            module = entry.replace(".py", "")
            cmd = f'CMD ["gunicorn", "--bind", "0.0.0.0:8000", "{module}:app"]'
            expose = "EXPOSE 8000"
        else:
            cmd = f'CMD ["python", "{entry}"]'
            expose = "EXPOSE 8000"

        return f"""# Auto-generated by Sovereign PaaS
FROM python:{version}-slim

WORKDIR /app

# Install system deps for common Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \\
    gcc libpq-dev && \\
    rm -rf /var/lib/apt/lists/*

# Install Python deps first (cache layer)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt{chr(10) + 'RUN pip install --no-cache-dir gunicorn' if framework == 'flask' else ''}
{chr(10) + 'RUN pip install --no-cache-dir uvicorn[standard]' if framework == 'fastapi' else ''}
# Copy application code
COPY . .

{expose}

{cmd}
"""

    def _gen_node(self, det: StackDetection, repo: Path) -> str:
        version = det.version or "20"
        framework = det.framework or "generic"

        if framework in ("react", "vue", "astro"):
            # SPA / static build → multi-stage
            return f"""# Auto-generated by Sovereign PaaS
FROM node:{version}-alpine AS build
WORKDIR /app
COPY package*.json ./
RUN npm ci --production=false
COPY . .
RUN npm run build

FROM nginx:alpine
COPY --from=build /app/dist /usr/share/nginx/html
COPY --from=build /app/build /usr/share/nginx/html 2>/dev/null || true
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
"""
        elif framework == "nextjs":
            return f"""# Auto-generated by Sovereign PaaS
FROM node:{version}-alpine AS deps
WORKDIR /app
COPY package*.json ./
RUN npm ci

FROM node:{version}-alpine AS build
WORKDIR /app
COPY --from=deps /app/node_modules ./node_modules
COPY . .
RUN npm run build

FROM node:{version}-alpine
WORKDIR /app
ENV NODE_ENV=production
COPY --from=build /app/.next ./.next
COPY --from=build /app/public ./public
COPY --from=build /app/package*.json ./
COPY --from=build /app/node_modules ./node_modules
EXPOSE 3000
CMD ["npm", "start"]
"""
        else:
            # Express or generic Node server
            return f"""# Auto-generated by Sovereign PaaS
FROM node:{version}-alpine
WORKDIR /app
COPY package*.json ./
RUN npm ci --production
COPY . .
EXPOSE 3000
CMD ["npm", "start"]
"""

    def _gen_go(self, det: StackDetection, repo: Path) -> str:
        version = det.version or "1.22"
        return f"""# Auto-generated by Sovereign PaaS
FROM golang:{version}-alpine AS build
WORKDIR /app
COPY go.mod go.sum ./
RUN go mod download
COPY . .
RUN CGO_ENABLED=0 GOOS=linux go build -o /server .

FROM alpine:3.19
RUN apk --no-cache add ca-certificates
COPY --from=build /server /server
EXPOSE 8080
CMD ["/server"]
"""

    def _gen_rust(self, det: StackDetection, repo: Path) -> str:
        return """# Auto-generated by Sovereign PaaS
FROM rust:1.77-slim AS build
WORKDIR /app
COPY Cargo.toml Cargo.lock ./
RUN mkdir src && echo 'fn main() {}' > src/main.rs && cargo build --release && rm -rf src
COPY . .
RUN cargo build --release

FROM debian:bookworm-slim
RUN apt-get update && apt-get install -y --no-install-recommends ca-certificates && rm -rf /var/lib/apt/lists/*
COPY --from=build /app/target/release/app /usr/local/bin/app
EXPOSE 8080
CMD ["app"]
"""

    def _gen_static(self, det: StackDetection, repo: Path) -> str:
        return """# Auto-generated by Sovereign PaaS
FROM nginx:alpine
COPY . /usr/share/nginx/html
EXPOSE 80
CMD ["nginx", "-g", "daemon off;"]
"""


# ─── Deployment Manifest ────────────────────────────────────────────────────

class DeployManifest:
    """Tracks all active deployments."""

    def __init__(self, manifest_dir: Path):
        self.manifest_path = manifest_dir / MANIFEST_FILE
        self._apps: dict = {}
        self._load()

    def _load(self):
        if self.manifest_path.exists():
            try:
                self._apps = json.loads(self.manifest_path.read_text())
            except json.JSONDecodeError:
                self._apps = {}

    def _save(self):
        self.manifest_path.parent.mkdir(parents=True, exist_ok=True)
        self.manifest_path.write_text(json.dumps(self._apps, indent=2, default=str))

    def register(self, result: DeployResult):
        self._apps[result.app_name] = {
            "stack": result.stack,
            "container_id": result.container_id,
            "port": result.port,
            "url": result.url,
            "domain": result.domain,
            "deployed_at": datetime.now(timezone.utc).isoformat(),
        }
        self._save()

    def unregister(self, app_name: str):
        self._apps.pop(app_name, None)
        self._save()

    def list_apps(self) -> dict:
        return dict(self._apps)

    def get(self, app_name: str) -> Optional[dict]:
        return self._apps.get(app_name)


# ─── The Sovereign Deployer ─────────────────────────────────────────────────

class SovereignDeployer:
    """
    The core deployment engine.

    Pipeline: DETECT → PREPARE → BUILD → DEPLOY → ROUTE → VERIFY
    """

    def __init__(self, paas_root: Optional[Path] = None):
        self.logger = logging.getLogger("Sovereign.Core")
        self.paas_root = paas_root or Path(__file__).parent
        self.detector = StackDetector()
        self.dockerfile_gen = DockerfileGenerator()
        self.docker = DockerManager()
        self.proxy = ProxyManager(self.paas_root / "caddy")
        self.manifest = DeployManifest(self.paas_root)

    def deploy(self, config: DeployConfig) -> DeployResult:
        """Execute the full deployment pipeline."""
        start_time = time.monotonic()

        self.logger.info("=" * 70)
        self.logger.info("  SOVEREIGN PAAS — Deployment Engine")
        self.logger.info("  Repository: %s", config.repo_path)
        self.logger.info("  App Name:   %s", config.app_name)
        self.logger.info("  Domain:     %s", config.domain or "auto")
        self.logger.info("  Dry Run:    %s", config.dry_run)
        self.logger.info("=" * 70)

        repo_path = config.repo_path.resolve()
        if not repo_path.is_dir():
            return DeployResult(
                success=False, app_name=config.app_name, stack="unknown",
                error=f"Repository path is not a directory: {repo_path}",
            )

        # ── Phase 1: DETECT ──────────────────────────────────────────
        self.logger.info("[1/6] DETECT — Scanning repository...")
        detection = self.detector.detect(repo_path)

        if detection.stack == StackType.UNKNOWN:
            return DeployResult(
                success=False, app_name=config.app_name, stack="unknown",
                error="Could not detect project stack. Add a Dockerfile manually.",
            )

        # ── Phase 2: PREPARE ─────────────────────────────────────────
        self.logger.info("[2/6] PREPARE — Generating Dockerfile...")
        dockerfile_path = repo_path / "Dockerfile"
        generated_dockerfile = False

        if detection.stack == StackType.DOCKER:
            self.logger.info("  User-provided Dockerfile found. Skipping generation.")
        else:
            dockerfile_content = self.dockerfile_gen.generate(detection, repo_path)
            if config.dry_run:
                self.logger.info("  [DRY RUN] Would generate Dockerfile:")
                for line in dockerfile_content.splitlines():
                    self.logger.info("    %s", line)
            else:
                dockerfile_path.write_text(dockerfile_content, encoding="utf-8")
                generated_dockerfile = True
                self.logger.info("  Dockerfile generated: %s", dockerfile_path)

        if config.dry_run:
            elapsed = int((time.monotonic() - start_time) * 1000)
            self.logger.info("[DRY RUN] Stopping. Pipeline validated in %dms.", elapsed)
            return DeployResult(
                success=True, app_name=config.app_name,
                stack=detection.stack.value, duration_ms=elapsed,
            )

        # ── Phase 3: BUILD ───────────────────────────────────────────
        self.logger.info("[3/6] BUILD — Building Docker image...")
        image_tag = f"sovereign-{config.app_name}:latest"

        try:
            image_id = self.docker.build_image(repo_path, image_tag)
            self.logger.info("  Image built: %s (%s)", image_tag, image_id[:12])
        except Exception as e:
            self._cleanup_dockerfile(dockerfile_path, generated_dockerfile)
            return DeployResult(
                success=False, app_name=config.app_name,
                stack=detection.stack.value,
                error=f"Docker build failed: {e}",
            )

        # ── Phase 4: DEPLOY ──────────────────────────────────────────
        self.logger.info("[4/6] DEPLOY — Starting container...")

        # Teardown existing container if redeploying
        existing = self.manifest.get(config.app_name)
        if existing and existing.get("container_id"):
            self.logger.info("  Tearing down previous deployment...")
            self.docker.stop_container(existing["container_id"])

        try:
            container_info = self.docker.run_container(
                image_tag=image_tag,
                app_name=config.app_name,
                port=config.port,
                env_vars=config.env_vars,
                cpus=config.cpus,
            )
            self.logger.info(
                "  Container started: %s (port %d)",
                container_info.container_id[:12], container_info.host_port,
            )
        except Exception as e:
            self._cleanup_dockerfile(dockerfile_path, generated_dockerfile)
            return DeployResult(
                success=False, app_name=config.app_name,
                stack=detection.stack.value,
                error=f"Container start failed: {e}",
            )

        # ── Phase 5: ROUTE ───────────────────────────────────────────
        self.logger.info("[5/6] ROUTE — Configuring reverse proxy...")
        domain = config.domain or f"{config.app_name}.localhost"

        try:
            self.proxy.add_route(
                app_name=config.app_name,
                domain=domain,
                upstream_port=container_info.host_port,
            )
            url = f"https://{domain}" if domain != f"{config.app_name}.localhost" else f"http://{domain}"
            self.logger.info("  Route configured: %s -> localhost:%d", domain, container_info.host_port)
        except Exception as e:
            self.logger.warning("  Proxy configuration failed: %s", e)
            url = f"http://localhost:{container_info.host_port}"

        # ── Phase 6: VERIFY ──────────────────────────────────────────
        self.logger.info("[6/6] VERIFY — Health check...")
        healthy = self.docker.health_check(container_info.container_id, retries=5)
        if healthy:
            self.logger.info("  Container is HEALTHY ✓")
        else:
            self.logger.warning("  Container health check inconclusive — may still be starting")

        # ── Finalize ─────────────────────────────────────────────────
        elapsed = int((time.monotonic() - start_time) * 1000)

        result = DeployResult(
            success=True,
            app_name=config.app_name,
            stack=detection.stack.value,
            container_id=container_info.container_id,
            port=container_info.host_port,
            url=url,
            domain=domain,
            duration_ms=elapsed,
        )

        self.manifest.register(result)
        self._cleanup_dockerfile(dockerfile_path, generated_dockerfile)

        self.logger.info("=" * 70)
        self.logger.info("  DEPLOYMENT COMPLETE")
        self.logger.info("  App:       %s", config.app_name)
        self.logger.info("  Stack:     %s (%s)", detection.stack.value, detection.framework or "generic")
        self.logger.info("  Container: %s", container_info.container_id[:12])
        self.logger.info("  Port:      %d", container_info.host_port)
        self.logger.info("  URL:       %s", url)
        self.logger.info("  Time:      %dms", elapsed)
        self.logger.info("=" * 70)

        return result

    def teardown(self, app_name: str) -> bool:
        """Tear down a deployed application."""
        self.logger.info("Tearing down: %s", app_name)
        app = self.manifest.get(app_name)
        if not app:
            self.logger.error("App '%s' not found in manifest", app_name)
            return False

        # Stop container
        if app.get("container_id"):
            self.docker.stop_container(app["container_id"])
            self.logger.info("  Container stopped")

        # Remove proxy route
        self.proxy.remove_route(app_name)
        self.logger.info("  Route removed")

        # Remove from manifest
        self.manifest.unregister(app_name)
        self.logger.info("  App '%s' torn down successfully", app_name)
        return True

    def list_deployments(self):
        """Print all active deployments."""
        apps = self.manifest.list_apps()
        if not apps:
            self.logger.info("No active deployments.")
            return

        self.logger.info("Active deployments:")
        for name, info in apps.items():
            self.logger.info(
                "  %-20s | %-8s | port %-5s | %s",
                name, info.get("stack", "?"),
                info.get("port", "?"), info.get("url", "?"),
            )

    def _cleanup_dockerfile(self, path: Path, was_generated: bool):
        """Remove auto-generated Dockerfile if we created it."""
        if was_generated and path.exists():
            path.unlink()


# ─── App Name Sanitizer ─────────────────────────────────────────────────────

def sanitize_app_name(name: str) -> str:
    """Sanitize an app name for use as a container/domain name."""
    clean = re.sub(r"[^a-z0-9\-]", "-", name.lower())
    clean = re.sub(r"-+", "-", clean).strip("-")
    return clean or "app"


# ─── CLI ─────────────────────────────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(
        description="Sovereign PaaS — Zero-Config Deployment Engine",
    )
    parser.add_argument(
        "--repo", type=str,
        help="Path to the Git repository to deploy",
    )
    parser.add_argument(
        "--name", type=str, default=None,
        help="Application name (auto-derived from repo dir if not set)",
    )
    parser.add_argument(
        "--domain", type=str, default=None,
        help="Custom domain (e.g., my-app.example.com)",
    )
    parser.add_argument(
        "--port", type=int, default=None,
        help="Force a specific host port",
    )
    parser.add_argument(
        "--cpus", type=str, default=None,
        help="CPU cores to pin to (e.g., '0-3', '0,1')",
    )
    parser.add_argument(
        "--env", type=str, nargs="*", default=[],
        help="Environment variables (KEY=VALUE)",
    )
    parser.add_argument(
        "--dry-run", action="store_true",
        help="Validate pipeline without building or deploying",
    )
    parser.add_argument(
        "--force", action="store_true",
        help="Force rebuild even if container exists",
    )
    parser.add_argument(
        "--list", action="store_true",
        help="List all active deployments",
    )
    parser.add_argument(
        "--teardown", type=str, default=None,
        help="Tear down an app by name",
    )
    parser.add_argument(
        "--log-level", type=str, default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
    )

    args = parser.parse_args()

    # ── Logging ──────────────────────────────────────────────────────
    log_level = getattr(logging, args.log_level)
    console = logging.StreamHandler()
    console.setLevel(log_level)
    console.setFormatter(logging.Formatter(LOG_FORMAT, datefmt=LOG_DATE_FORMAT))

    root = logging.getLogger()
    root.setLevel(logging.DEBUG)
    root.addHandler(console)

    deployer = SovereignDeployer()

    # ── Commands ─────────────────────────────────────────────────────
    if args.list:
        deployer.list_deployments()
        return

    if args.teardown:
        deployer.teardown(args.teardown)
        return

    if not args.repo:
        parser.error("--repo is required for deployment")

    repo_path = Path(args.repo).resolve()
    app_name = sanitize_app_name(args.name or repo_path.name)

    # Parse env vars
    env_vars = {}
    for ev in args.env:
        if "=" in ev:
            k, v = ev.split("=", 1)
            env_vars[k] = v

    config = DeployConfig(
        repo_path=repo_path,
        app_name=app_name,
        domain=args.domain,
        port=args.port,
        cpus=args.cpus,
        env_vars=env_vars,
        dry_run=args.dry_run,
        force_rebuild=args.force,
    )

    result = deployer.deploy(config)

    if not result.success:
        print(f"\n✗ Deployment failed: {result.error}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    main()
