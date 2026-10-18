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
PNG_FILES = {"header": ("header.png", (1200, 200)),
             "divider": ("divider.png", (1200, 200)),
             "corner": ("corner.png", (290, 290))}
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
    assets=manifest.get("assets")
    if not isinstance(assets,dict) or set(assets)!=set(FILES):
        raise ValueError("A csomagban header, divider és corner grafika szükséges.")
    for key,filename in assets.items():
        if filename not in (FILES[key][0],PNG_FILES[key][0]):
            raise ValueError("Hibás grafikai fájlnév; SVG vagy PNG használható.")


def validate_png(data: bytes, size: tuple[int,int]) -> None:
    from PIL import Image
    from io import BytesIO
    if len(data)>6_000_000:
        raise ValueError("Egy PNG legfeljebb 6 MB lehet.")
    try:
        with Image.open(BytesIO(data)) as image:
            if image.format!="PNG" or image.size!=size:
                raise ValueError(f"Hibás PNG méret: {size[0]} × {size[1]} px szükséges.")
            image.load()
    except (OSError, Image.DecompressionBombError) as exc:
        raise ValueError("Hibás PNG állomány.") from exc


def validate_pack(folder: Path) -> dict:
    manifest=json.loads((folder/"manifest.json").read_text(encoding="utf-8"))
    validate_manifest(manifest)
    for key,filename in manifest["assets"].items():
        raw=(folder/filename).read_bytes()
        if filename.endswith(".png"):validate_png(raw,PNG_FILES[key][1])
        else:validate_svg(raw,FILES[key][1])
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
        if "manifest.json" not in names or len(names)>12:
            raise ValueError("A ZIP gyökerében manifest.json és három grafika szükséges.")
        manifest=json.loads(archive.read("manifest.json").decode("utf-8"))
        validate_manifest(manifest)
        if any(not name.endswith(".png") for name in manifest["assets"].values()):
            raise ValueError("Témacsomagban csak teljes színű PNG grafikák használhatók.")
        required={"manifest.json",*manifest["assets"].values()}
        if not required.issubset(names) or sum(archive.getinfo(n).file_size for n in required)>18_500_000:
            raise ValueError("Hiányzó grafika vagy túl nagy csomag.")
        raw={n:archive.read(n) for n in required}
    validate_manifest(manifest)
    for key,filename in manifest["assets"].items():
        if filename.endswith(".png"):validate_png(raw[filename],PNG_FILES[key][1])
        else:validate_svg(raw[filename],FILES[key][1])
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
        for filename in manifest["assets"].values():
            (folder/filename).write_bytes(raw[filename])
        (folder/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    except Exception:
        for item in folder.iterdir():
            item.unlink()
        folder.rmdir()
        raise
    return slug
