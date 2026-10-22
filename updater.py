"""Windows self-updater for the portable EtlapStudio release package."""
from __future__ import annotations

import ctypes
import hashlib
import os
import shutil
import subprocess
import sys
import tempfile
import urllib.request
import zipfile
from pathlib import Path, PurePosixPath, PureWindowsPath

SYNCHRONIZE = 0x00100000
WAIT_OBJECT_0 = 0
WAIT_TIMEOUT = 0x102
WAIT_FAILED = 0xFFFFFFFF
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
    from ctypes import wintypes

    kernel = ctypes.WinDLL("kernel32", use_last_error=True)
    kernel.OpenProcess.argtypes = [wintypes.DWORD, wintypes.BOOL, wintypes.DWORD]
    kernel.OpenProcess.restype = wintypes.HANDLE
    kernel.WaitForSingleObject.argtypes = [wintypes.HANDLE, wintypes.DWORD]
    kernel.WaitForSingleObject.restype = wintypes.DWORD
    kernel.CloseHandle.argtypes = [wintypes.HANDLE]
    kernel.CloseHandle.restype = wintypes.BOOL

    handle = kernel.OpenProcess(SYNCHRONIZE, False, pid)
    if not handle:
        error = ctypes.get_last_error()
        if error in {87, 1168}:  # The app exited before the helper started waiting.
            ready_file.write_text("already-closed", encoding="ascii")
            return
        raise ctypes.WinError(error)
    try:
        ready_file.write_text("ready", encoding="ascii")
        result = kernel.WaitForSingleObject(handle, 120_000)
        if result == WAIT_TIMEOUT:
            raise TimeoutError("Az alkalmazás 120 másodpercen belül nem zárult be.")
        if result == WAIT_FAILED:
            raise ctypes.WinError(ctypes.get_last_error())
        if result != WAIT_OBJECT_0:
            raise OSError(f"A Windows folyamatvárakozás hibát jelzett: {result}")
    finally:
        kernel.CloseHandle(handle)


def download_update(url: str, version: str, expected_digest: str, directory: Path) -> Path:
    expected_name = f"EtlapStudio-Windows-{version}.zip"
    if not url.startswith(REPOSITORY_PREFIX) or not url.endswith("/" + expected_name):
        raise ValueError("A GitHub kiadáshoz tartozó frissítőcsomag hivatkozása érvénytelen.")
    if len(expected_digest) != 64 or any(c not in "0123456789abcdefABCDEF" for c in expected_digest):
        raise ValueError("A frissítőcsomag SHA-256 ellenőrző összege érvénytelen.")

    request = urllib.request.Request(url, headers={"User-Agent": "EtlapStudio-Updater"})
    target = directory / expected_name
    digest = hashlib.sha256()
    with urllib.request.urlopen(request, timeout=90) as response, target.open("wb") as output:
        signature = response.read(4)
        if signature[:2] != b"PK":
            raise ValueError("A letöltött fájl nem ZIP-frissítőcsomag.")
        output.write(signature)
        digest.update(signature)
        while chunk := response.read(1024 * 1024):
            output.write(chunk)
            digest.update(chunk)
    actual = digest.hexdigest()
    if actual.lower() != expected_digest.lower():
        target.unlink(missing_ok=True)
        raise ValueError("A frissítőcsomag SHA-256 ellenőrzése nem sikerült.")
    log(f"Downloaded {expected_name}, sha256={actual}")
    return target


def extract_update(archive: Path, destination: Path) -> Path:
    destination.mkdir(parents=True, exist_ok=True)
    root = destination.resolve()
    with zipfile.ZipFile(archive) as package:
        for item in package.infolist():
            posix_name = PurePosixPath(item.filename)
            windows_name = PureWindowsPath(item.filename)
            target = (destination / Path(*posix_name.parts)).resolve()
            mode = item.external_attr >> 16
            if (posix_name.is_absolute() or windows_name.is_absolute() or windows_name.drive
                    or ".." in posix_name.parts or ".." in windows_name.parts
                    or (target != root and root not in target.parents)):
                raise ValueError("A frissítőcsomag nem biztonságos fájlútvonalat tartalmaz.")
            if mode and (mode & 0o170000) == 0o120000:
                raise ValueError("A frissítőcsomag szimbolikus hivatkozást tartalmaz.")
        package.extractall(destination)
    if (destination / "EtlapStudio.exe").is_file():
        return destination
    children = list(destination.iterdir())
    if len(children) == 1 and children[0].is_dir() and (children[0] / "EtlapStudio.exe").is_file():
        return children[0]
    raise RuntimeError("A frissítőcsomag nem tartalmaz teljes EtlapStúdió alkalmazást.")


def main() -> int:
    if len(sys.argv) != 7:
        return 2
    url, digest, pid_text, install_dir_text, app_exe_text, ready_text = sys.argv[1:]
    pid, install_dir, app_exe = int(pid_text), Path(install_dir_text), Path(app_exe_text)
    ready_file = Path(ready_text)
    temp_root = Path(tempfile.mkdtemp(prefix="EtlapStudio-update-"))
    try:
        wait_for_app(pid, ready_file)
        version = url.split("/download/", 1)[1].split("/", 1)[0].removeprefix("v")
        archive = download_update(url, version, digest, temp_root)
        source = extract_update(archive, temp_root / "extracted")
        # This helper is a temporary copy outside the install directory, so every app file can be replaced.
        shutil.copytree(source, install_dir, dirs_exist_ok=True)
        if not app_exe.is_file():
            raise FileNotFoundError(f"Az alkalmazás nem található a frissítés után: {app_exe}")
        subprocess.Popen([str(app_exe)], cwd=str(install_dir), close_fds=True)
        log(f"Installed EtlapStudio {version} to {install_dir}; relaunched.")
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
