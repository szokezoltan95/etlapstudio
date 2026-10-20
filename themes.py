"""Safe seasonal PNG theme packs with backward-compatible legacy imports."""
from __future__ import annotations

import json
import re
import tempfile
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
MODERN_PNG_FILES = {"divider": ("divider.png", (1800, 120)),
                    "background": ("background.png", (1440, 2037))}
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
    if not isinstance(assets,dict) or not (set(assets)==set(FILES) or set(assets) in ({"divider"},{"divider","background"})):
        raise ValueError("A csomagban divider grafika, opcionálisan háttérgrafika szükséges.")
    for key,filename in assets.items():
        allowed=(FILES[key][0],PNG_FILES[key][0]) if key in FILES else (MODERN_PNG_FILES[key][0],)
        if filename not in allowed:
            raise ValueError("Hibás grafikai fájlnév; SVG vagy PNG használható.")
    variants=manifest.get("divider_variants",[])
    if not isinstance(variants,list) or len(variants)>5 or any(name not in {f"divider_{i}.png" for i in range(1,6)} for name in variants):
        raise ValueError("Legfeljebb öt, divider_1.png–divider_5.png nevű elválasztó használható.")


def validate_builtin_manifest(manifest: dict) -> None:
    """Built-in themes provide palette metadata; artwork lives in design_assets/."""
    if manifest.get("schema_version") != SCHEMA:
        raise ValueError("Nem támogatott témacsomag-verzió.")
    if not isinstance(manifest.get("id"),str) or not IDENT.fullmatch(manifest["id"]):
        raise ValueError("Hibás beépített témaazonosító.")
    if not isinstance(manifest.get("name"),str) or not 1 <= len(manifest["name"]) <= 60:
        raise ValueError("Hibás beépített témanév.")
    palette=manifest.get("palette",{})
    if not isinstance(palette,dict) or any(not isinstance(palette.get(key),str) or not HEX.fullmatch(palette[key])
                                           for key in ("primary","accent","background")):
        raise ValueError("Hibás beépített színpaletta.")


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
    modern=set(manifest["assets"])!=set(FILES)
    files={**manifest["assets"]}
    files.update({f"divider_variant_{i}":name for i,name in enumerate(manifest.get("divider_variants",[]))})
    for key,filename in files.items():
        raw=(folder/filename).read_bytes()
        if filename.endswith(".png"):
            base_key="divider" if key.startswith("divider_variant_") else key
            size=MODERN_PNG_FILES[base_key][1] if modern else PNG_FILES[base_key][1]
            validate_png(raw,size)
        else:validate_svg(raw,FILES[key][1])
    return manifest


def load_themes(builtin: Path, user: Path) -> dict[str, tuple[dict, Path]]:
    result={}
    builtin_root=builtin.resolve()
    for folder in [builtin, user]:
        if not folder.exists():
            continue
        for child in sorted(folder.iterdir()):
            if not child.is_dir():
                continue
            try:
                if folder.resolve()==builtin_root:
                    manifest=json.loads((child/"manifest.json").read_text(encoding="utf-8"))
                    validate_builtin_manifest(manifest)
                else:
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
        required={"manifest.json",*manifest["assets"].values(),*manifest.get("divider_variants",[])}
        if not required.issubset(names) or sum(archive.getinfo(n).file_size for n in required)>18_500_000:
            raise ValueError("Hiányzó grafika vagy túl nagy csomag.")
        raw={n:archive.read(n) for n in required}
    validate_manifest(manifest)
    modern=set(manifest["assets"])!=set(FILES)
    files={**manifest["assets"]}
    files.update({f"divider_variant_{i}":name for i,name in enumerate(manifest.get("divider_variants",[]))})
    for key,filename in files.items():
        if filename.endswith(".png"):
            base_key="divider" if key.startswith("divider_variant_") else key
            size=MODERN_PNG_FILES[base_key][1] if modern else PNG_FILES[base_key][1]
            validate_png(raw[filename],size)
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
        for filename in {*manifest["assets"].values(),*manifest.get("divider_variants",[])}:
            (folder/filename).write_bytes(raw[filename])
        (folder/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2)+"\n",encoding="utf-8")
    except Exception:
        for item in folder.iterdir():
            item.unlink()
        folder.rmdir()
        raise
    return slug


def import_theme_images(background: Path, dividers: list[Path], name: str, occasion: str,
                        destination: Path, existing: set[str]) -> str:
    """Build a validated theme package from separately generated PNG files."""
    from PIL import Image, ImageOps
    from io import BytesIO
    import unicodedata
    if not background.is_file():
        raise ValueError("Válassz egy háttérképet (PNG, 1440 × 2037 px).")
    if not dividers:
        raise ValueError("Válassz legalább egy elválasztóképet (PNG, 1800 × 120 px).")
    if len(dividers) > 5:
        raise ValueError("Legfeljebb öt elválasztó tölthető be egyszerre.")
    safe=unicodedata.normalize("NFKD",name).encode("ascii","ignore").decode().lower()
    safe=re.sub(r"[^a-z0-9]+","_",safe).strip("_")[:24] or "tema"
    if len(safe)<2:safe="tema_"+safe
    manifest={"schema_version":SCHEMA,"id":safe,"name":name[:60],
              "occasion":occasion[:100],
              "palette":{"primary":"#526044","accent":"#B85A42","background":"#F1E9D7"},
              "assets":{"divider":"divider.png","background":"background.png"}}
    with tempfile.TemporaryDirectory(prefix="etlap-theme-") as tmp:
        folder=Path(tmp)
        def normalized_png(path, size, mode, contain=False):
            if path.stat().st_size>20_000_000:
                raise ValueError(f"A {path.name} fájl nagyobb 20 MB-nál.")
            try:
                with Image.open(path) as image:
                    image.load();has_alpha="A" in image.getbands()
                    image=ImageOps.contain(image.convert(mode),size,Image.Resampling.LANCZOS) if contain else ImageOps.fit(image.convert(mode),size,method=Image.Resampling.LANCZOS,centering=(.5,.5))
                    if mode=="RGBA" and not has_alpha:
                        alpha=ImageOps.invert(ImageOps.grayscale(image.convert("RGB"))).point(lambda px: 0 if px<7 else min(255,(px-7)*8))
                        image=image.convert("RGBA");image.putalpha(alpha)
                    if contain:
                        canvas=Image.new(mode,size,(0,0,0,0) if mode=="RGBA" else (255,255,255))
                        canvas.alpha_composite(image,((size[0]-image.width)//2,(size[1]-image.height)//2)) if mode=="RGBA" else canvas.paste(image,((size[0]-image.width)//2,(size[1]-image.height)//2))
                        image=canvas
                    output=BytesIO();image.save(output,format="PNG",optimize=True);return output.getvalue()
            except (OSError,Image.DecompressionBombError) as exc:
                raise ValueError(f"Nem olvasható képfájl: {path.name}") from exc
        bg_data=normalized_png(background,MODERN_PNG_FILES["background"][1],"RGB")
        validate_png(bg_data,MODERN_PNG_FILES["background"][1])
        (folder/"background.png").write_bytes(bg_data)
        divider_names=[]
        for index,path in enumerate(dividers,1):
            filename=f"divider_{index}.png"
            raw=normalized_png(path,MODERN_PNG_FILES["divider"][1],"RGBA",contain=True)
            validate_png(raw,MODERN_PNG_FILES["divider"][1])
            (folder/filename).write_bytes(raw);divider_names.append(filename)
        # Keep the standard primary divider filename; preserve additional variants in metadata.
        (folder/"divider.png").write_bytes((folder/divider_names[0]).read_bytes())
        if len(divider_names)>1:manifest["divider_variants"]=divider_names
        (folder/"manifest.json").write_text(json.dumps(manifest,ensure_ascii=False,indent=2),encoding="utf-8")
        with zipfile.ZipFile(folder/"theme.zip","w",zipfile.ZIP_DEFLATED) as archive:
            for item in folder.iterdir():
                if item.is_file() and item.name!="theme.zip":archive.write(item,item.name)
        return import_theme(folder/"theme.zip",destination,existing)

