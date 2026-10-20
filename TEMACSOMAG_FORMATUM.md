# ÉtlapStúdió témacsomag

Új dizájnt a **Dizájn → Új dizájn létrehozása…** ablak promptja alapján lehet készíteni. Betölthető ZIP-csomagként vagy külön képfájlokként. Külön képfájloknál a program a gyakori PNG, JPEG, WebP és BMP formátumokat a témához szükséges PNG-méretre alakítja. Egy háttérkép és 1–5 elválasztó tölthető be.

## ZIP-témacsomag

A ZIP gyökerében legyen `manifest.json`, `background.png`, `divider.png`, valamint opcionálisan `divider_1.png`–`divider_5.png`. Az összes képfájl pontos méretű PNG legyen:

| Fájl | Méret | Használat |
| --- | ---: | --- |
| `background.png` | 1440 × 2037 px | Teljes oldalas, visszafogott háttér; a középső szövegterület maradjon világos és nyugodt. |
| `divider.png` | 1800 × 120 px | Vonalas, átlátszó hátterű elválasztó. |
| `divider_1.png`–`divider_5.png` | 1800 × 120 px | Opcionális változatok; a program étlapdátum szerint váltogatja őket. |

Példa `manifest.json`:

```json
{
  "schema_version": 1,
  "id": "oszi_level",
  "name": "Őszi levelek",
  "occasion": "Őszi étlap",
  "palette": {
    "primary": "#315747",
    "accent": "#B66A36",
    "background": "#F7F2E9"
  },
  "assets": {
    "divider": "divider.png",
    "background": "background.png"
  },
  "divider_variants": [
    "divider_1.png",
    "divider_2.png",
    "divider_3.png",
    "divider_4.png",
    "divider_5.png"
  ]
}
```

`divider_variants` elhagyható, ha csak a `divider.png` áll rendelkezésre. A `palette` színei `#RRGGBB` formátumúak. A divider legyen valódi, átlátszó hátterű line-art: ne legyen kitöltött téglalap, vastag sáv vagy felirat rajta. A ZIP gyökerében ne legyenek almappák. A program ellenőrzi a csomagot, a PNG-fájlokat és azok méreteit; az ismert régi témacsomag-formátumok importálása is megmaradt.

Ha az AI-modell nem tud ZIP-et készíteni, a külön képfájlok betöltése használható. Sikertelen ZIP-importnál a hibaüzenet is javasolja ezt a lehetőséget.
