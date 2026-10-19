# ÉtlapStúdió témacsomag – PNG formátum

A témacsomag ZIP-fájl. Az új formátum egy vonalas elválasztóból, színpalettából, és igény szerint egy teljes oldalas háttérképből áll. A régi `header.png` + `divider.png` + `corner.png` formátumú témacsomagok továbbra is importálhatók, de az új generálásokhoz már ne készíts címsor mögötti sávot vagy sarokképet.

| Fájl | Méret | Használat |
| --- | ---: | --- |
| `divider.png` | 1800 × 120 px | Átlátszó hátterű, vékony évszakos line-art; két szekció között jelenik meg. |
| `background.png` | 1440 × 2037 px | Opcionális, teljes oldalas, visszafogott illusztráció; a lap közepén maradjon világos hely a szöveg számára. |
| `manifest.json` | UTF-8 | A téma neve, azonosítója, színei és fájljai. |

Minimális témacsomag `manifest.json`:

```json
{
  "schema_version": 1,
  "id": "oszi_level",
  "name": "Őszi levelek",
  "palette": {
    "primary": "#315747",
    "accent": "#B66A36",
    "background": "#F7F2E9"
  },
  "assets": {
    "divider": "divider.png"
  }
}
```

Háttérrel a manifest `assets` részét így bővítsd:

```json
"assets": {
  "divider": "divider.png",
  "background": "background.png"
}
```

Az `id` 2–32 karakteres kisbetűs azonosító; szám, `_` és `-` is használható. A színek `#RRGGBB` formátumúak legyenek. Mindkét kép PNG legyen, és pontosan a táblázatban megadott méretű. A divider valódi, átlátszó alfa-csatornát használjon; ne legyen rajta kitöltött sáv vagy téglalap. Az étlap közepén az olvashatóság miatt maradjon tiszta terület.

A témacsomagot a **Dizájn → Témacsomag importálása…** gombbal lehet betölteni. A teljes oldalas háttér opcionális; háttér nélkül az app a választott évszakhoz tartozó beépített képet használja. A grafikai irányt és a generálható promptokat a [GRAPHICS_PROMPT.md](GRAPHICS_PROMPT.md) írja le.
