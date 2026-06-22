#!/usr/bin/env python3
"""Deploy mentoria-remodelar to HostGator via FTP.

Reads credentials from .env. Mirrors the current directory to the remote
web root, skipping dotfiles, .git, deploy.py itself e arquivos de dev.

Uso:
    python3 deploy.py
"""
import ftplib
import os
import sys
from pathlib import Path

ROOT = Path(__file__).parent
SKIP_DIRS = {".git", ".wrangler", "node_modules", "__pycache__", ".claude"}
SKIP_FILES = {".DS_Store", ".env", ".env.example", ".gitignore", "deploy.py", "grid-export.html"}


def load_env(path: Path) -> dict:
    env = {}
    for line in path.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        k, _, v = line.partition("=")
        env[k.strip()] = v.strip()
    return env


def connect(env: dict) -> ftplib.FTP:
    host = env["FTP_HOST"]
    user = env["FTP_USER"]
    pw = env["FTP_PASS"]
    port = int(env.get("FTP_PORT", 21))
    print(f"[connect] {user}@{host}:{port}")
    ftp = ftplib.FTP()
    ftp.connect(host, port, timeout=60)
    ftp.login(user, pw)
    ftp.set_pasv(True)
    print(f"[connect] welcome: {ftp.getwelcome()}")
    print(f"[connect] cwd: {ftp.pwd()}")
    return ftp


def ensure_dir(ftp: ftplib.FTP, remote_dir: str) -> None:
    parts = [p for p in remote_dir.split("/") if p]
    path = ""
    for part in parts:
        path = f"{path}/{part}" if path else part
        try:
            ftp.cwd("/" + path)
        except ftplib.error_perm:
            print(f"[mkdir] /{path}")
            ftp.mkd("/" + path)
    ftp.cwd("/")


def upload_file(ftp: ftplib.FTP, local: Path, remote: str) -> None:
    size = local.stat().st_size
    print(f"[upload] {remote} ({size:,} bytes)")
    with local.open("rb") as f:
        ftp.storbinary(f"STOR {remote}", f, blocksize=64 * 1024)


def mirror(ftp: ftplib.FTP, local_root: Path) -> None:
    uploaded = 0
    for dirpath, dirnames, filenames in os.walk(local_root):
        dirnames[:] = [d for d in dirnames if d not in SKIP_DIRS and not d.startswith(".")]
        rel_dir = Path(dirpath).relative_to(local_root).as_posix()
        if rel_dir == ".":
            rel_dir = ""
        if rel_dir:
            ensure_dir(ftp, rel_dir)
        for name in filenames:
            if name in SKIP_FILES or name.startswith("."):
                continue
            local_path = Path(dirpath) / name
            remote_path = f"/{rel_dir}/{name}" if rel_dir else f"/{name}"
            try:
                upload_file(ftp, local_path, remote_path)
                uploaded += 1
            except Exception as e:
                print(f"[error] {remote_path}: {e}", file=sys.stderr)
                raise
    print(f"[done] {uploaded} file(s) uploaded")


def main() -> int:
    env_path = ROOT / ".env"
    if not env_path.exists():
        print("missing .env — copie .env.example pra .env e preencha", file=sys.stderr)
        return 1
    env = load_env(env_path)
    ftp = connect(env)
    try:
        mirror(ftp, ROOT)
    finally:
        ftp.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
