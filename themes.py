"""Portable vector theme packs with fixed asset geometry and safe ZIP import."""
from __future__ import annotations

import json
import re
import zipfile
from pathlib import Path
from xml.etree import ElementTree as ET

SCHEMA = 1
FILES = {"header": ("header.svg", "0 0 600 100"),
         "divider": ("divider.svg", "0 0 600 100"),
         "corner": ("corner.svg", "0 0 145 145")}
SAFE_TAGS = {"svg", "g", "path", "circle", "ellipse", "line", "rect", "polygon", "polyline"}
SAFE_ATTRS = {"xmlns", "viewBox", "width", "height", "d", "fill", "stroke",
              "stroke-width", "stroke-linecap", "stroke-linejoin", "opacity", "transform",
              "cx", "cy", "r", "rx", "ry", "x", "y", "x1", "x2", "y1", "y2",
              "points", "fill-opacity", "stroke-opacity"}
HEX = re.compile(r"^#[0-9a-fA-F]{6}$")
IDENT = re.compile(r"^[a-z][a-z0-9_-]{1,31}$")


def validate_svg(data: bytes, viewbox: str) -> None:
    if len(data) > 500_000:
        raise ValueError("Egy SVG legfeljebb 500 kB lehet.")
    if b"<!DOCTYPE" in data.upper() or b"<!ENTITY" in data.upper():
        raise ValueError("Az SVG nem tartalmazhat DTD-t vagy entitást.")
    try:
        root = ET.fromstring(data)
    except ET.ParseError as exc:
        raise ValueError("Hibás SVG állomány.") from exc
    namespace="{http://www.w3.org/2000/svg}"
    if root.tag != namespace+"svg" or root.attrib.get("viewBox") != viewbox:
        raise ValueError(f"Hibás SVG viewBox; az előírt méret: {viewbox}.")
    for element in root.iter():
        if not element.tag.startswith(namespace) or element.tag[len(namespace):] not in SAFE_TAGS:
            raise ValueError("Az SVG nem megengedett elemet tartalmaz.")
        for attr, value in element.attrib.items():
            if attr.rsplit("}", 1)[-1] not in SAFE_ATTRS or "url(" in value.lower():
                raise ValueError("Az SVG külső vagy nem megengedett hivatkozást tartalmaz.")


def validate_manifest(manifest: dict) -> None:
    if manifest.get("schema_version") != SCHEMA:
        raise ValueError("Nem támogatott témacsomag-verzió.")
    if not isinstance(manifest.get("id"), str) or not IDENT.fullmatch(manifest["id"]):
        raise ValueError("A téma azonosítója 2–32 kisbetűből, számból vagy kötőjelből állhat.")
    if not isinstance(manifest.get("name"), str) or not 1 <= len(manifest["name"]) <= 60:
        raise ValueError("A téma neve hiányzik vagy túl hosszú.")
    p = manifest.get("palette", {})
    if not isinstance(p, dict) or any(not isinstance(p.get(k), str) or not HEX.fullmatch(p[k])
                                      for k in ("primary", "accent", "background")):
        raise ValueError("A téma színei #RRGGBB formátumúak legyenek.")
    if manifest.get("assets") != {key: spec[0] for key, spec in FILES.items()}:
        raise ValueError("A csomagban header.svg, divider.svg és corner.svg szükséges.")


def validate_pack(folder: Path) -> dict:
    manifest=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    validate_manifest(manifest)
    for filename, viewbox in FILES.values():
        validate_svg((folder/filename).read_bytes(), viewbox)
    return manifest


def load_themes(builtin: Path, user: Path) -> dict[str, tuple[dict, Path]]:
    result={}
    for folder in [builtin, user]:
        if not folder.exists():
            continue
        for child in sorted(folder.iterdir()):
            if not child.is_dir():
                continue
            try:
                manifest=validate_pack(child)
                result[manifest["id"]]=(manifest,child)
            except (ValueError, OSError, KeyError, json.JSONDecodeError):
                continue
    return result


def import_theme(zip_path: Path, destination: Path, existing: set[str]) -> str:
    with zipfile.ZipFile(zip_path) as archive:
        names=set(archive.namelist())
        required={"manifest.json", *(v[0] for v in FILES.values())}
        if not required.issubset(names) or len(names)>12:
            raise ValueError("A ZIP gyökerében manifest.json és a három SVG szükséges.")
        if sum(archive.getinfo(n).file_size for n in required)>1_600_000:
            raise ValueError("A csomag túl nagy.")
        raw={n:archive.read(n) for n in required}
    manifest=json.loads(raw["manifest.json"].decode("utf-8"))
    validate_manifest(manifest)
    for _key,(filename,viewbox) in FILES.items():
        validate_svg(raw[filename],viewbox)
    original=manifest["id"]
    slug=original
    number=2
    while slug in existing or (destination/slug).exists():
        slug=f"{original[:27]}_{number}"
        number+=1
    manifest["id"]=slug
    folder=destination/slug
    folder.mkdir(parents=True,exist_ok=False)
    try:
        for filename,_viewbox in FILES.values():
            (folder/filename).write_bytes(raw[filename])
        (folder/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    except Exception:
        for item in folder.iterdir():
            item.unlink()
        folder.rmdir()
        raise
    return slug
