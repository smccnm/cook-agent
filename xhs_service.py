from __future__ import annotations

import json
import os
import subprocess
import time
import zipfile
from pathlib import Path
from typing import Any

import httpx

from settings import AppSettings


def extract_a1(cookies: list[dict[str, Any]]) -> str:
    for cookie in cookies:
        if cookie.get("name") == "a1":
            return str(cookie.get("value", ""))
    return ""


def build_cookie_header(cookies: list[dict[str, Any]]) -> str:
    parts = []
    for cookie in cookies:
        name = cookie.get("name")
        value = cookie.get("value")
        if name and value is not None:
            parts.append(f"{name}={value}")
    return "; ".join(parts)


class XHSServiceManager:
    def __init__(self, settings: AppSettings | None = None) -> None:
        self.settings = settings or AppSettings()
        self._login_process: subprocess.Popen | None = None
        self._mcp_process: subprocess.Popen | None = None

    def read_cookies(self) -> list[dict[str, Any]]:
        cookie_path = self.settings.xhs_cookies_file
        if not cookie_path.exists():
            return []
        try:
            return json.loads(cookie_path.read_text(encoding="utf-8"))
        except Exception:
            return []

    def sync_login_state_to_env(self) -> dict[str, str]:
        cookies = self.read_cookies()
        cookie_header = build_cookie_header(cookies)
        a1 = extract_a1(cookies)

        env_updates = {"XHS_COOKIE": cookie_header, "A1": a1}
        env_path = self.settings.project_root / ".env"
        existing: dict[str, str] = {}
        if env_path.exists():
            for line in env_path.read_text(encoding="utf-8").splitlines():
                if "=" in line and not line.strip().startswith("#"):
                    key, value = line.split("=", 1)
                    existing[key] = value
        existing.update(env_updates)
        env_path.write_text(
            "\n".join(f"{key}={value}" for key, value in existing.items()) + "\n",
            encoding="utf-8",
        )
        os.environ.update(env_updates)
        return env_updates

    def start_login(self) -> dict[str, Any]:
        binary = self.settings.xhs_login_binary
        if not binary.exists():
            self.ensure_binaries()

        self.settings.xhs_cookies_file.parent.mkdir(parents=True, exist_ok=True)
        env = os.environ.copy()
        env["COOKIES_PATH"] = str(self.settings.xhs_cookies_file)

        self._login_process = subprocess.Popen(
            [str(binary)],
            cwd=str(binary.parent),
            env=env,
        )
        return {"started": True, "pid": self._login_process.pid}

    def login_status(self) -> dict[str, Any]:
        process_running = self._login_process is not None and self._login_process.poll() is None
        cookies = self.read_cookies()
        cookie_header = build_cookie_header(cookies)
        a1 = extract_a1(cookies)
        logged_in = bool(cookie_header and a1)
        if logged_in:
            self.sync_login_state_to_env()
        return {
            "process_running": process_running,
            "logged_in": logged_in,
            "cookies_path": str(self.settings.xhs_cookies_file),
            "has_a1": bool(a1),
        }

    def ensure_mcp_server(self) -> str:
        try:
            response = httpx.get(f"{self.settings.xhs_mcp_base_url}/health", timeout=2.0)
            if response.status_code == 200:
                return self.settings.xhs_mcp_base_url
        except Exception:
            pass

        if self._mcp_process is not None and self._mcp_process.poll() is None:
            return self.settings.xhs_mcp_base_url

        binary = self.settings.xhs_mcp_binary
        if not binary.exists():
            self.ensure_binaries()

        env = os.environ.copy()
        env["COOKIES_PATH"] = str(self.settings.xhs_cookies_file)
        self._mcp_process = subprocess.Popen(
            [str(binary), "-headless=true", "-port", ":18060"],
            cwd=str(binary.parent),
            env=env,
        )

        for _ in range(30):
            try:
                response = httpx.get(f"{self.settings.xhs_mcp_base_url}/health", timeout=2.0)
                if response.status_code == 200:
                    return self.settings.xhs_mcp_base_url
            except Exception:
                time.sleep(1)

        raise RuntimeError("XHS MCP server did not become ready")

    def ensure_binaries(self) -> None:
        if self.settings.xhs_login_binary.exists() and self.settings.xhs_mcp_binary.exists():
            return

        release_url = (
            "https://github.com/xpzouying/xiaohongshu-mcp/releases/download/"
            "v2026.03.09.0605-0e16f4b/xiaohongshu-mcp-windows-amd64.zip"
        )
        download_dir = self.settings.project_root / "vendor" / "xiaohongshu-mcp" / "bin"
        download_dir.mkdir(parents=True, exist_ok=True)
        zip_path = download_dir / "xiaohongshu-mcp-windows-amd64.zip"

        if not zip_path.exists():
            with httpx.Client(timeout=120) as client:
                response = client.get(release_url)
                response.raise_for_status()
                zip_path.write_bytes(response.content)

        with zipfile.ZipFile(zip_path, "r") as archive:
            archive.extractall(download_dir)

    async def search(self, query: str) -> list[dict[str, Any]]:
        base_url = self.ensure_mcp_server()
        async with httpx.AsyncClient(timeout=30) as client:
            response = await client.get(
                f"{base_url}/api/v1/feeds/search",
                params={"keyword": query},
            )
            response.raise_for_status()
        payload = response.json()
        data = payload.get("data", {})
        if isinstance(data, dict) and "feeds" in data:
            items = data.get("feeds") or []
        elif isinstance(data, dict) and "items" in data:
            items = data.get("items") or []
        else:
            items = data if isinstance(data, list) else []
        return items
