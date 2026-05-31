"""
PROXY MANAGER — Dynamic Reverse Proxy Controller
Part of the Trishula Sovereign PaaS (Gap 1)

Manages Caddy reverse-proxy configuration. When a new container spins up,
this module writes a routing rule and triggers a Caddy reload.

Architecture:
    - Each app gets its own Caddyfile snippet in caddy/sites/
    - A master Caddyfile imports all snippets
    - Caddy reload is non-disruptive (zero-downtime reloads)
    - Auto-SSL via Let's Encrypt for production domains
    - Localhost mode for development (no SSL)

Supports Caddy via:
    1. File-based config (Caddyfile snippets) + reload signal
    2. Caddy Admin API (localhost:2019) for live config pushes
"""

import json
import logging
import os
import signal
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass
from pathlib import Path
from typing import Optional

logger = logging.getLogger("Sovereign.Proxy")


# ─── Data Models ─────────────────────────────────────────────────────────────

@dataclass
class RouteConfig:
    """Configuration for a single proxy route."""
    app_name: str
    domain: str
    upstream_port: int
    upstream_host: str = "127.0.0.1"
    tls_enabled: bool = True
    health_path: Optional[str] = None
    headers: dict = None

    def __post_init__(self):
        if self.headers is None:
            self.headers = {}
        # Localhost domains don't get TLS
        if self.domain.endswith(".localhost") or self.domain.startswith("localhost"):
            self.tls_enabled = False


# ─── Caddyfile Generator ────────────────────────────────────────────────────

class CaddyfileGenerator:
    """Generates Caddyfile configuration snippets."""

    @staticmethod
    def generate_site_block(route: RouteConfig) -> str:
        """Generate a Caddyfile site block for a single app."""
        upstream = f"{route.upstream_host}:{route.upstream_port}"

        lines = []

        # Domain block
        if route.tls_enabled:
            lines.append(f"{route.domain} {{")
        else:
            lines.append(f"http://{route.domain} {{")

        # Reverse proxy
        lines.append(f"    reverse_proxy {upstream} {{")
        lines.append(f"        header_up Host {{host}}")
        lines.append(f"        header_up X-Real-IP {{remote_host}}")
        lines.append(f"        header_up X-Forwarded-For {{remote_host}}")
        lines.append(f"        header_up X-Forwarded-Proto {{scheme}}")

        # Health check if configured
        if route.health_path:
            lines.append(f"        health_uri {route.health_path}")
            lines.append(f"        health_interval 30s")
            lines.append(f"        health_timeout 5s")

        lines.append("    }")

        # Security headers
        lines.append("")
        lines.append("    header {")
        lines.append("        X-Content-Type-Options nosniff")
        lines.append("        X-Frame-Options DENY")
        lines.append("        X-XSS-Protection \"1; mode=block\"")
        lines.append("        Referrer-Policy strict-origin-when-cross-origin")
        lines.append("        -Server")
        lines.append("    }")

        # Logging
        lines.append("")
        lines.append(f"    log {{")
        lines.append(f"        output file /var/log/caddy/{route.app_name}.log")
        lines.append(f"        format json")
        lines.append(f"    }}")

        lines.append("}")
        lines.append("")

        return "\n".join(lines)

    @staticmethod
    def generate_master_caddyfile(sites_dir: str) -> str:
        """Generate the master Caddyfile that imports all site configs."""
        return f"""# Sovereign PaaS — Master Caddyfile
# Auto-generated. Do not edit manually.
# Individual site configs are in {sites_dir}/

{{
    # Global options
    admin localhost:2019
    email admin@sovereign.local

    # Auto-HTTPS (Let's Encrypt)
    # Uncomment for production:
    # acme_ca https://acme-v02.api.letsencrypt.org/directory
}}

import {sites_dir}/*.caddy
"""


# ─── Proxy Manager ──────────────────────────────────────────────────────────

class ProxyManager:
    """
    Manages the Caddy reverse proxy configuration.

    Modes:
        - file:  Write Caddyfile snippets + reload Caddy process
        - api:   Push config via Caddy Admin API (localhost:2019)
    """

    def __init__(self, caddy_dir: Optional[Path] = None, mode: str = "file"):
        self.logger = logging.getLogger("Sovereign.Proxy")
        self.mode = mode
        self.caddy_dir = caddy_dir or Path("/etc/caddy")
        self.sites_dir = self.caddy_dir / "sites"
        self.master_caddyfile = self.caddy_dir / "Caddyfile"
        self.generator = CaddyfileGenerator()

        # Ensure directories exist
        self.sites_dir.mkdir(parents=True, exist_ok=True)

        # Generate master Caddyfile if it doesn't exist
        if not self.master_caddyfile.exists():
            master = self.generator.generate_master_caddyfile(
                str(self.sites_dir)
            )
            self.master_caddyfile.write_text(master, encoding="utf-8")
            self.logger.info("Generated master Caddyfile: %s", self.master_caddyfile)

    def add_route(
        self,
        app_name: str,
        domain: str,
        upstream_port: int,
        upstream_host: str = "127.0.0.1",
        health_path: Optional[str] = None,
    ) -> RouteConfig:
        """Add a reverse proxy route for an application.

        Args:
            app_name: Application identifier
            domain: Domain name (e.g., my-app.example.com)
            upstream_port: Port the container is listening on
            upstream_host: Host the container is reachable at
            health_path: Optional health check endpoint

        Returns:
            The created RouteConfig
        """
        route = RouteConfig(
            app_name=app_name,
            domain=domain,
            upstream_port=upstream_port,
            upstream_host=upstream_host,
            health_path=health_path,
        )

        if self.mode == "api":
            return self._add_route_api(route)
        else:
            return self._add_route_file(route)

    def remove_route(self, app_name: str):
        """Remove a reverse proxy route.

        Args:
            app_name: Application identifier
        """
        if self.mode == "api":
            self._remove_route_api(app_name)
        else:
            self._remove_route_file(app_name)

    def list_routes(self) -> list[str]:
        """List all configured app routes."""
        routes = []
        if self.sites_dir.exists():
            for f in self.sites_dir.glob("*.caddy"):
                routes.append(f.stem)
        return routes

    # ─── File-Based Mode ─────────────────────────────────────────────

    def _add_route_file(self, route: RouteConfig) -> RouteConfig:
        """Write a Caddyfile snippet and reload Caddy."""
        site_config = self.generator.generate_site_block(route)
        site_file = self.sites_dir / f"{route.app_name}.caddy"

        site_file.write_text(site_config, encoding="utf-8")
        self.logger.info(
            "Route written: %s -> %s:%d (%s)",
            route.domain, route.upstream_host, route.upstream_port, site_file,
        )

        self._reload_caddy()
        return route

    def _remove_route_file(self, app_name: str):
        """Remove a Caddyfile snippet and reload Caddy."""
        site_file = self.sites_dir / f"{app_name}.caddy"
        if site_file.exists():
            site_file.unlink()
            self.logger.info("Route removed: %s", app_name)
            self._reload_caddy()
        else:
            self.logger.debug("No route file found for: %s", app_name)

    def _reload_caddy(self):
        """Reload Caddy to pick up configuration changes."""
        # Method 1: Caddy Admin API reload
        try:
            self._caddy_api_reload()
            self.logger.debug("Caddy reloaded via Admin API")
            return
        except Exception:
            pass

        # Method 2: caddy reload command
        try:
            result = subprocess.run(
                ["caddy", "reload", "--config", str(self.master_caddyfile)],
                capture_output=True, text=True, timeout=10,
            )
            if result.returncode == 0:
                self.logger.debug("Caddy reloaded via CLI")
                return
            else:
                self.logger.debug("Caddy CLI reload failed: %s", result.stderr)
        except FileNotFoundError:
            self.logger.debug("Caddy CLI not found")
        except subprocess.TimeoutExpired:
            self.logger.warning("Caddy reload timed out")

        # Method 3: Signal-based reload (Linux only)
        try:
            caddy_pid = self._find_caddy_pid()
            if caddy_pid:
                os.kill(caddy_pid, signal.SIGUSR1)
                self.logger.debug("Sent USR1 to Caddy (PID %d)", caddy_pid)
                return
        except (OSError, AttributeError):
            pass

        self.logger.warning(
            "Could not reload Caddy. Config written but not applied. "
            "Start Caddy with: caddy run --config %s",
            self.master_caddyfile,
        )

    def _find_caddy_pid(self) -> Optional[int]:
        """Find the Caddy process PID."""
        try:
            result = subprocess.run(
                ["pgrep", "-x", "caddy"],
                capture_output=True, text=True, timeout=5,
            )
            if result.returncode == 0 and result.stdout.strip():
                return int(result.stdout.strip().split("\n")[0])
        except (FileNotFoundError, ValueError, subprocess.TimeoutExpired):
            pass
        return None

    # ─── API-Based Mode ──────────────────────────────────────────────

    def _add_route_api(self, route: RouteConfig) -> RouteConfig:
        """Push a route via Caddy's Admin API."""
        config = {
            "match": [{"host": [route.domain]}],
            "handle": [{
                "handler": "reverse_proxy",
                "upstreams": [{
                    "dial": f"{route.upstream_host}:{route.upstream_port}"
                }],
                "headers": {
                    "request": {
                        "set": {
                            "X-Real-IP": ["{http.request.remote.host}"],
                            "X-Forwarded-For": ["{http.request.remote.host}"],
                            "X-Forwarded-Proto": ["{http.request.scheme}"],
                        }
                    }
                },
            }],
            "@id": f"sovereign-{route.app_name}",
        }

        try:
            self._caddy_api_post(
                f"/config/apps/http/servers/sovereign/routes",
                config,
            )
            self.logger.info(
                "Route added via API: %s -> %s:%d",
                route.domain, route.upstream_host, route.upstream_port,
            )
        except Exception as e:
            self.logger.error("API route add failed: %s — falling back to file mode", e)
            return self._add_route_file(route)

        return route

    def _remove_route_api(self, app_name: str):
        """Remove a route via Caddy's Admin API."""
        try:
            self._caddy_api_delete(f"/id/sovereign-{app_name}")
            self.logger.info("Route removed via API: %s", app_name)
        except Exception as e:
            self.logger.warning("API route removal failed: %s", e)
            # Fall back to file removal
            self._remove_route_file(app_name)

    def _caddy_api_reload(self):
        """Trigger a Caddy reload via Admin API."""
        caddy_config = self.master_caddyfile.read_text(encoding="utf-8")
        req = urllib.request.Request(
            "http://localhost:2019/load",
            data=caddy_config.encode("utf-8"),
            headers={"Content-Type": "text/caddyfile"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            if resp.status not in (200, 204):
                raise RuntimeError(f"Caddy reload failed: HTTP {resp.status}")

    def _caddy_api_post(self, path: str, data: dict):
        """POST JSON to the Caddy Admin API."""
        req = urllib.request.Request(
            f"http://localhost:2019{path}",
            data=json.dumps(data).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read()

    def _caddy_api_delete(self, path: str):
        """DELETE from the Caddy Admin API."""
        req = urllib.request.Request(
            f"http://localhost:2019{path}",
            method="DELETE",
        )
        with urllib.request.urlopen(req, timeout=10) as resp:
            return resp.read()
