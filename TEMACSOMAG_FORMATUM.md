# ÉtlapStúdió grafikai csomag – PNG formátum

A csomag ZIP-fájl, benne közvetlenül a gyökérben lévő fájlokkal. A grafikák teljes színű, átlátszó hátterű PNG-k. Az alkalmazás SVG grafikát nem rajzol.

| Fájl | Méret | Helye az étlapon |
| --- | ---: | --- |
| `header.png` | 1200 × 200 px | Étteremnév és fejléc körüli dísz |
| `divider.png` | 1200 × 200 px | Napi menü és étellista közötti elválasztó |
| `corner.png` | 290 × 290 px | Alsó sarokdísz |
| `manifest.json` | UTF-8 | Témacímke, színek és fájlnevek |

Példa `manifest.json`:

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
    "header": "header.png",
    "divider": "divider.png",
    "corner": "corner.png"
  }
}
```

Az `id` 2–32 karakteres kisbetűs azonosító; használható benne szám, `_` és `-`. A grafika legyen légies, és hagyjon üres helyet a rákerülő szövegnek. Ne legyen rajta felirat, dátum, ár, logó vagy vízjel. A háttérgrafikát külön, 4:5 álló kép formájában importáld; ehhez ajánlott méret 1440 × 1800 px vagy nagyobb.

A témacsomagot a **Dizájn → Témacsomag importálása…** gombbal lehet betölteni. Teljes oldalas hátteret a **Dizájn → Háttér vagy díszítőelem importálása…** gomb fogad.
