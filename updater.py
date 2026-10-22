"""Windows release updater. Uses a native process handle to wait for EtlapStudio to exit."""
from __future__ import annotations

import ctypes
import hashlib
import os
import subprocess
import sys
import tempfile
import urllib.request
from pathlib import Path

SYNCHRONIZE = 0x00100000
PROCESS_QUERY_LIMITED_INFORMATION = 0x1000
WAIT_OBJECT_0 = 0x00000000
WAIT_TIMEOUT = 0x00000102
MOVEFILE_DELAY_UNTIL_REBOOT = 0x00000004
REPOSITORY_PREFIX = "https://github.com/szokezoltan95/etlapstudio/releases/download/"


def log(message: str) -> None:
    try:
        root = Path(os.environ.get("LOCALAPPDATA", tempfile.gettempdir())) / "EtlapStudio"
        root.mkdir(parents=True, exist_ok=True)
        with (root / "update.log").open("a", encoding="utf-8") as stream:
            stream.write(message.rstrip() + "\n")
    except Exception:
        pass


def notify(message: str, error: bool = False) -> None:
    try:
        ctypes.windll.user32.MessageBoxW(None, message, "ÉtlapStúdió frissítő",
            0x10 if error else 0x40)
    except Exception:
        pass


def wait_for_app(pid: int, ready_file: Path) -> None:
    kernel = ctypes.windll.kernel32
    kernel.OpenProcess.restype = ctypes.c_void_p
    handle = kernel.OpenProcess(SYNCHRONIZE | PROCESS_QUERY_LIMITED_INFORMATION, False, pid)
    if not handle:
        raise OSError("Nem sikerült megnyitni az alkalmazás folyamatát.")
    try:
        ready_file.write_text("ready", encoding="ascii")
        result = kernel.WaitForSingleObject(ctypes.c_void_p(handle), 120_000)
        if result == WAIT_TIMEOUT:
            raise TimeoutError("Az alkalmazás 120 másodpercen belül nem zárult be.")
        if result != WAIT_OBJECT_0:
            raise OSError(f"A Windows folyamatvárakozás hibát jelzett: {result}")
    finally:
        kernel.CloseHandle(ctypes.c_void_p(handle))


def download_installer(url: str, version: str, directory: Path) -> Path:
    expected = f"EtlapStudio-Setup-{version}.exe"
    if not url.startswith(REPOSITORY_PREFIX) or not url.endswith("/" + expected):
        raise ValueError("A GitHub kiadáshoz tartozó telepítőhivatkozás érvénytelen.")
    request = urllib.request.Request(url, headers={"User-Agent": "EtlapStudio-Updater"})
    target = directory / expected
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=45) as response, target.open("wb") as output:
        signature = response.read(2)
        if signature != b"MZ":
            raise ValueError("A letöltött fájl nem Windows-telepítő.")
        output.write(signature)
        digest.update(signature)
        while True:
            chunk = response.read(1024 * 1024)
            if not chunk:
                break
            output.write(chunk)
            digest.update(chunk)
    log(f"Downloaded {expected}, sha256={digest.hexdigest()}")
    return target


def main() -> int:
    if len(sys.argv) != 6:
        return 2
    url, pid_text, install_dir_text, app_exe_text, ready_text = sys.argv[1:]
    pid = int(pid_text)
    install_dir = Path(install_dir_text)
    app_exe = Path(app_exe_text)
    ready_file = Path(ready_text)
    try:
        wait_for_app(pid, ready_file)
        # The process handle is signaled only after the Qt app has closed its SQLite database.
        release = url.split("/download/", 1)[1].split("/", 1)[0].removeprefix("v")
        temp_root = Path(tempfile.mkdtemp(prefix="EtlapStudio-install-"))
        installer = download_installer(url, release, temp_root)
        completed = subprocess.run([
            str(installer), "/SILENT", "/SUPPRESSMSGBOXES", "/NORESTART",
            "/CLOSEAPPLICATIONS", f"/DIR={install_dir}"
        ], timeout=900, check=False)
        if completed.returncode != 0:
            raise RuntimeError(f"A Windows-telepítő {completed.returncode} hibakóddal állt le.")
        if not app_exe.is_file():
            raise FileNotFoundError(f"Az alkalmazás nem található a telepítés után: {app_exe}")
        subprocess.Popen([str(app_exe)], cwd=str(install_dir), close_fds=True)
        log(f"Installed EtlapStudio {release} to {install_dir}; relaunched.")
        return 0
    except Exception as exc:
        log(f"Update failed: {type(exc).__name__}: {exc}")
        notify("A frissítés nem sikerült. A helyi ételadatbázis külön fájlban maradt. "
               "Indítsd el újra a programot, majd próbáld később.\n\n" + str(exc), True)
        try:
            if app_exe.is_file():
                subprocess.Popen([str(app_exe)], cwd=str(install_dir), close_fds=True)
        except Exception as relaunch_error:
            log(f"Could not relaunch app: {relaunch_error}")
        return 1
    finally:
        try:
            ctypes.windll.kernel32.MoveFileExW(str(Path(sys.executable)), None,
                                                MOVEFILE_DELAY_UNTIL_REBOOT)
        except Exception:
            pass


if __name__ == "__main__":
    raise SystemExit(main())
