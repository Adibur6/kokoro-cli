import hashlib
import os
import shutil
import time
import urllib.error
import urllib.request

from rich.console import Console
from rich.progress import (
    BarColumn,
    DownloadColumn,
    Progress,
    TextColumn,
    TimeRemainingColumn,
    TransferSpeedColumn,
)

from kokoro_cli.config import (
    DATA_DIR,
    DATA_MODEL_DIR,
    PROJECT_MODEL_DIR,
    resolve_model_dir,
)

REPO_URL = "https://huggingface.co/hexgrad/Kokoro-82M/resolve/main"
APPROX_SIZE_MB = 330

console = Console()


def _manifest_path() -> str:
    path = os.path.join(os.path.dirname(os.path.abspath(__file__)), "data", "Kokoro-82M.md5")
    if os.path.isfile(path):
        return path
    raise SystemExit("Manifest Kokoro-82M.md5 not found.")


def load_manifest() -> list[tuple[str, str]]:
    """Return [(md5, relpath), ...] from the checksum manifest."""
    entries = []
    with open(_manifest_path(), encoding="utf-8") as f:
        for line in f:
            parts = line.split()
            if len(parts) == 2:
                entries.append((parts[0], parts[1]))
    return entries


def md5_of(path: str) -> str:
    h = hashlib.md5()
    with open(path, "rb") as f:
        for chunk in iter(lambda: f.read(1 << 20), b""):
            h.update(chunk)
    return h.hexdigest()


def _complete(path: str, want: str) -> bool:
    return os.path.isfile(path) and md5_of(path) == want


def is_complete(base_dir: str) -> bool:
    if not os.path.isdir(base_dir):
        return False
    return all(_complete(os.path.join(base_dir, rel), want) for want, rel in load_manifest())


def dir_size(path: str) -> str:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            total += os.path.getsize(os.path.join(root, name))
    if total < 1 << 20:
        return f"{total / (1 << 10):.0f} KB"
    return f"{total / (1 << 20):.1f} MB"


def _fetch(url: str, tmp: str, existing: int, update) -> None:
    headers = {"Range": f"bytes={existing}-"} if existing else {}
    req = urllib.request.Request(url, headers=headers)
    with urllib.request.urlopen(req) as resp:
        resumed = resp.status == 206
        if resumed:
            total = int(resp.headers.get("Content-Range", "").split("/")[-1])
        else:
            total = int(resp.headers.get("Content-Length") or 0)
            existing = 0
        update(existing, total)
        with open(tmp, "ab" if resumed else "wb") as out:
            while True:
                chunk = resp.read(1 << 16)
                if not chunk:
                    break
                out.write(chunk)
                existing += len(chunk)
                update(existing, total)


def _download(url: str, tmp: str, update, retries: int = 3) -> None:
    """Fetch into tmp, resuming a partial download when the server allows it.

    Some CDNs (HuggingFace's xet bridge) reject Range requests with HTTP 403,
    so we fall back to a full re-download in that case. Transient network errors
    are retried.
    """
    existing = os.path.getsize(tmp) if os.path.isfile(tmp) else 0
    for attempt in range(retries):
        try:
            _fetch(url, tmp, existing, update)
            return
        except urllib.error.HTTPError as e:
            if e.code == 403 and existing:
                console.print(f"  [yellow]resume rejected (HTTP 403); re-downloading[/yellow]")
                os.remove(tmp)
                existing = 0
                continue
            if e.code == 416:
                os.remove(tmp)
                existing = 0
                continue
            if e.code >= 500 and attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise
        except (urllib.error.URLError, TimeoutError, ConnectionError):
            if attempt < retries - 1:
                time.sleep(1.5 * (attempt + 1))
                continue
            raise


def download_weights(confirmed: bool = False) -> None:
    """Download model + voices (md5-verified) into whichever dir resolve_model_dir() picks."""
    entries = load_manifest()
    target_dir = resolve_model_dir()
    if is_complete(target_dir):
        location = "the project dir" if target_dir == PROJECT_MODEL_DIR else "the data dir"
        console.print(f"[green]Model already present[/green] in {location}: {target_dir}")
        return

    if not confirmed:
        if not _confirm(f"Download Kokoro-82M (~{APPROX_SIZE_MB}MB) to {target_dir}?"):
            raise SystemExit("Aborted.")

    os.makedirs(target_dir, exist_ok=True)
    with Progress(
        TextColumn("[progress.description]{task.description}"),
        BarColumn(),
        DownloadColumn(),
        TransferSpeedColumn(),
        TimeRemainingColumn(),
        console=console,
    ) as progress:
        for want, rel in entries:
            dest = os.path.join(target_dir, rel)
            if _complete(dest, want):
                continue
            os.makedirs(os.path.dirname(dest), exist_ok=True)
            task = progress.add_task(f"Downloading {rel}", total=None)
            tmp = dest + ".part"
            try:
                _download(
                    f"{REPO_URL}/{rel}",
                    tmp,
                    lambda got, total, t=task: progress.update(t, completed=got, total=total or None),
                )
                if not _complete(tmp, want):
                    raise SystemExit(f"md5 mismatch for {rel}")
                os.replace(tmp, dest)
            except Exception:
                progress.remove_task(task)
                raise
            progress.update(task, completed=True)


def uninstall(force: bool = False) -> None:
    if not os.path.isdir(DATA_MODEL_DIR):
        console.print("[yellow]Nothing to remove[/yellow] — no managed model data at "
                      f"{DATA_MODEL_DIR}.")
    else:
        size = dir_size(DATA_MODEL_DIR)
        if not force and not _confirm(f"Remove {size} of model data from {DATA_MODEL_DIR}?"):
            raise SystemExit("Aborted.")
        shutil.rmtree(DATA_MODEL_DIR)
        console.print(f"[green]Removed[/green] {DATA_MODEL_DIR} ({size}).")

    parent = DATA_DIR
    if os.path.isdir(parent) and not os.listdir(parent):
        os.rmdir(parent)
        console.print(f"Removed empty directory {parent}")

    console.print("Now run [bold]pip uninstall kokoro-cli[/bold] to remove the package.")


def _confirm(prompt: str) -> bool:
    try:
        ans = input(f"{prompt} [y/N] ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return ans in ("y", "yes")


def doctor() -> None:
    entries = load_manifest()
    n = len(entries)
    for label, path in (("Project dir", PROJECT_MODEL_DIR), ("Data dir", DATA_MODEL_DIR)):
        status = f"[green]ok ({dir_size(path)})[/green]" if is_complete(path) else "[red]missing[/red]"
        console.print(f"{label:11} {path}")
        console.print(f"             {n} files: {status}")
