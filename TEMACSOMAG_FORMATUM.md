# ÉtlapStúdió grafikai csomag – PNG formátum

A csomag ZIP-fájl, benne közvetlenül a gyökérben lévő fájlokkal. A grafikák teljes színű, valódi alfa-átlátszóságú PNG-k. A program az automatikus ünnepi palettát használja alapértelmezésként; egy importált téma kiválasztásakor a fejléc- és elválasztó PNG-k a címsor, illetve az ételcsoportok mögé kerülnek.

| Fájl | Méret | Helye az étlapon |
| --- | ---: | --- |
| `header.png` | 1200 × 200 px | Egyszerű ecsetvonás a címsor mögé |
| `divider.png` | 1200 × 200 px | Áttetsző festett vonás az ételcsoportok között |
| `corner.png` | 290 × 290 px | Apró, légies széli motívum |
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

A témacsomagot a **Dizájn → Témacsomag importálása…** gombbal lehet betölteni. A csomag elemei ne tartalmazzanak mintás hátteret, keretezett panelt vagy színes téglalapot; a címsor mögötti ecsetvonás maradjon egyszerű és áttetsző.
