# Prompt étlapgrafikák készítéséhez

A másolható promptok bármely képgeneráló AI-nak megadhatók. A grafika mindig raszteres, teljes színű PNG/JPG legyen; az alkalmazás SVG grafikákat nem használ.

## Teljes oldalas, szezonális háttér

```text
Készíts igényes, nyomtatásra és Facebookra szánt teljes oldalas étlap-hátteret
álló 4:5 képarányban, lehetőleg legalább 1440 × 1800 képpont felbontásban.
Téma: [ÉVSZAK VAGY ÜNNEP]. Színek: [SZÍNEK]. Stílus: részletgazdag,
kézzel festett, teljes színű akvarell vagy gouache illusztráció, elegáns éttermi
arculathoz. A díszítő növények, termések és ünnepi motívumok keretezzék az oldal
külső szélét és sarkait. A lap középső legalább 75%-a legyen világos, visszafogott
és majdnem üres, hogy sűrű fekete ételnevek és árak jól olvashatók maradjanak.
Ne tegyél rá szöveget, betűt, számot, logót vagy vízjelet. Ne használj geometrikus
vektorgrafikát, mockupot vagy asztalra helyezett lapot. Egyetlen lapos, teljes
oldalas PNG/JPG képet készíts.
```

## Fejléc, címsáv, elválasztó és sarokdísz

Kérj négy külön, átlátszó hátterű, teljes színű PNG grafikát egyetlen témában.
A ZIP témacsomagban a méretek és fájlnevek kötöttek:

- `header.png` — 1200 × 200 px: díszítőelemek főleg a két szélen; középen maradjon hely az étterem nevének.
- `divider.png` — 1200 × 200 px: elegáns, vékony vízszintes dísz, középen kis motívummal.
- `corner.png` — 290 × 290 px: egy sarokban használható kompakt dísz.
- `manifest.json` — téma neve, színei és az előbbi fájlnevek; a struktúrához használd a [csomagformátum leírását](TEMACSOMAG_FORMATUM.md).

A grafikák ne tartalmazzanak feliratot, ételnevet, dátumot, árat, logót vagy vízjelet. Tartsd meg a valódi átlátszóságot, és kerüld a túl sűrű részleteket a szöveg helyén. A négy fájlt a ZIP gyökerébe tedd, ne belső könyvtárba. A teljes oldalas háttér külön PNG/JPG fájl, nem része a témacsomagnak.
