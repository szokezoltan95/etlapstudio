# Másolható prompt új ÉtlapStúdió grafikákhoz

## PNG háttér készítése képgeneráló AI-val

Az alábbi szöveg különálló háttérképet kér. A kész PNG/JPG a **Megjelenés → PNG/JPG importálása…** gombbal tölthető be. Nem kell hozzá témacsomag vagy SVG. A beépített `backgrounds/botanical.png` egy ilyen minta.

```text
Készíts elegáns, nyomdai minőségű ÉTLAP HÁTTÉRGRAFIKÁT, portré 4:5 arányban,
lehetőleg 1440 × 1800 px vagy nagyobb felbontásban, PNG formátumban.
Téma: [ÉVSZAK / ÜNNEP / STÍLUS]. Színvilág: [SZÍNEK].
A dekoráció kizárólag a külső szegélyeken és sarkokban legyen. Az oldal középső
legalább 75–80%-a, különösen a felső cím, a napi A/B menü és a két hasábnyi
étellista helye maradjon üres és világos. Sűrű, kis méretű fekete étlapfelirat
kerül majd fölé, ezért ne legyen mögötte erős kontraszt vagy tömör minta.
Finom, igényes, részletgazdag motívumokat használj. Ne írj rá semmilyen szöveget,
ételnevet, árat, dátumot vagy logót. Ne helyezz el látszólagos szövegsorokat.
Ha képes vagy valódi átlátszó PNG-t készíteni, a dekoráción kívüli részek
legyenek átlátszók. Ellenkező esetben tiszta, világos háttérrel add vissza.
Ne készíts perspektivikus mockupot, asztalra fektetett lapot vagy fényképet:
egyetlen lapos, teljes oldalas képfájlt kérek.
```

## SVG díszítő témacsomag készítése

### PNG alternatíva a három díszhez

Képgeneráló AI esetén kérj három külön **átlátszó PNG** képet: `header.png` pontosan **1200 × 200 px** (szabad középpel), `divider.png` pontosan **1200 × 200 px** (vékony vízszintes elválasztó) és `corner.png` pontosan **290 × 290 px** (egy sarokdísz). Ne legyen rajtuk szöveg. A `manifest.json` szerkezete marad ugyanaz, de az `assets` alatt a megfelelő `.png` neveket írd. A fájlokat ZIP gyökerébe csomagold. SVG és PNG egy témában is keverhető. A PNG-k rögzített színekkel jelennek meg; a program színválasztója csak az SVG-k palettaszíneit cseréli. A PNG díszek különállnak a teljes oldalas háttértől.

Az alábbi szöveget bármely olyan AI modellnek odaadhatod, amely képes szabványos SVG kódot írni. A szögletes zárójelben lévő részeket cseréld ki. Ha a modell nem tud ZIP-fájlt készíteni, a négy fájl tartalmát külön kódblokkokban kérd, és csomagold őket egy ZIP gyökerébe.

```text
Készíts egy teljes, importálható ÉtlapStúdió témacsomagot a következő témához:
[TÉMA – például adventi mézeskalács, magyar népi motívum, mediterrán nyár]

Hangulat és vizuális irány: [RÖVID LEÍRÁS].
Fő szín: [#RRGGBB]. Kiegészítő szín: [#RRGGBB]. Nagyon világos háttérszín: [#RRGGBB].
A téma gépi azonosítója: [kisbetus_azonosito]. Megjelenített neve: [Téma neve].

Négy, UTF-8 kódolású fájlt adj vissza, ezekkel a PONTOS fájlnevekkel:
1. manifest.json
2. header.svg
3. divider.svg
4. corner.svg

A manifest.json kötelező szerkezete:
{
  "schema_version": 1,
  "id": "[kisbetus_azonosito]",
  "name": "[Téma neve]",
  "palette": {
    "primary": "[#RRGGBB]",
    "accent": "[#RRGGBB]",
    "background": "[#RRGGBB]"
  },
  "assets": {
    "header": "header.svg",
    "divider": "divider.svg",
    "corner": "corner.svg"
  }
}

Az id 2–32 karakter hosszú, kisbetű, szám, aláhúzás vagy kötőjel megengedett;
az első karakter kisbetű. Mindhárom szín pontosan hatjegyű hexadecimális RGB.

A grafikai fájlok KÖTELEZŐ technikai méretei:
- header.svg: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 600 100" width="600" height="100">.
  A díszek a bal és jobb szélen legyenek, és a középső kb. 330 egység maradjon
  tiszta az étterem nevének és címének. Finom alsó vonalat is tartalmazhat.
- divider.svg: ugyanaz a 600 × 100 és viewBox. Karcsú vízszintes elválasztó,
  középen kis motívummal, a szélek felé futó vonallal.
- corner.svg: <svg xmlns="http://www.w3.org/2000/svg" viewBox="0 0 145 145" width="145" height="145">.
  Kompakt sarokdísz, amely 14 mm-es méretre kicsinyítve is felismerhető.

A háttér legyen átlátszó. Ne rajzolj ételnevet, dátumot, logót vagy éttermi
szöveget az SVG-be: ezeket az alkalmazás helyezi rá. A formák legyenek
igényesek, légiesek és olvasható szöveg mellett is jól működők. Kevés,
összefüggő vektorvonalat és tömör színfoltot használj, ne legyen zsúfolt.
Az SVG-ben a primary és accent paletta pontos hex kódját használd a fő színekhez,
hogy az appban átállított színek a grafikán is cserélhetők legyenek.

Az SVG-k kizárólag a következő elemeket használhatják: svg, g, path, circle,
ellipse, line, rect, polygon, polyline. Megengedett attribútumok: xmlns,
viewBox, width, height, d, fill, stroke, stroke-width, stroke-linecap,
stroke-linejoin, opacity, transform, cx, cy, r, rx, ry, x, y, x1, x2, y1, y2,
points, fill-opacity, stroke-opacity. Ne használj style blokkot, CSS-t,
scriptet, szöveget, képet, maszkot, szűrőt, gradienst, <defs>/<use> elemet,
beágyazott vagy külső hivatkozást, url(...) értéket, illetve betűtípust.
Minden SVG maradjon 500 kB alatt. Minden XML legyen jól formált.

Válaszolj pontosan négy, a fájlnevével egyértelműen címkézett kódblokkal.
Először a manifest.json, majd header.svg, divider.svg, corner.svg teljes
forrása jöjjön. Ne használj csonkítást vagy „a többi hasonló” helyettesítést.
Ellenőrizd magadban a fájlneveket, a viewBox méreteket, a paletta egyezését,
az XML szintaxist és a fenti tiltásokat, mielőtt válaszolsz.
```

A négy fájlt ZIP-be kell csomagolni úgy, hogy közvetlenül a ZIP gyökerében legyenek, ne egy belső mappában. Ezután a program **Megjelenés → Témacsomag importálása…** gombjával tölthetők be. Ha azonos azonosítójú téma már létezik, az új csomag külön sorszámozott azonosítót kap.
