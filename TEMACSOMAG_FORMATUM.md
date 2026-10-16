# ÉtlapStúdió témacsomag – 1. verzió

A téma egy ZIP-fájl, amelynek gyökerében négy fájl van:

| Fájl | Méret és `viewBox` | Felhasználás |
| --- | --- | --- |
| `header.svg` | 600 × 100, `0 0 600 100` | Címsor; a középső 330 egységben maradjon hely az étterem nevének. |
| `divider.svg` | 600 × 100, `0 0 600 100` | Elválasztó a cím és a menü között. |
| `corner.svg` | 145 × 145, `0 0 145 145` | Kis sarokdísz az oldal alján. |
| `manifest.json` | UTF-8 szöveg | Név, színek és fájlnevek. |

Példa `manifest.json`:

```json
{
  "schema_version": 1,
  "id": "nyari_citrom",
  "name": "Nyári citrom",
  "palette": {
    "primary": "#157A8A",
    "accent": "#E3A543",
    "background": "#FFF8E7"
  },
  "assets": {
    "header": "header.svg",
    "divider": "divider.svg",
    "corner": "corner.svg"
  }
}
```

Az `id` kisbetűből, számból, `_` vagy `-` karakterből áll, 2–32 karakter hosszú. A három szín hatjegyű hexadecimális kód. Az SVG átlátszó hátterű, csak egyszerű vektorelemekből állhat (`path`, `g`, `circle`, `ellipse`, `line`, `rect`, `polygon`, `polyline`). Külső képek, hivatkozások, betűtípusok, szkriptek és beágyazott stíluslapok nem használhatók. Egy SVG legfeljebb 500 kB.

Az app a grafikákat méretarányosan helyezi a PDF-be és a Facebook PNG-be. A saját alapszín és kiegészítő szín a grafikákban is lecseréli a téma palettájának megfelelő színeket. A szövegek mindig az alkalmazásból kerülnek a grafika fölé: az SVG nem tartalmaz ételneveket.

A képexport 4:5 képarányú PNG, 1440 × 1800 képponttal. A nyomtatható PDF A4 méretű. A napi PNG mindig egy kép: a felső menüblokk mérete fix, az à la carte rész betűi a tartalomhoz igazodnak. A kész `TEMA_SABLON.zip` fájlt másold le, alakítsd át a grafikákat és a manifestet, majd az app „Megjelenés” fülén importáld.
