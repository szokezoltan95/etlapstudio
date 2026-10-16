# ÉtlapStúdió

Windowsra szánt, helyi adatbázissal működő **Qt6 asztali étlapszerkesztő**. Bal oldalon az adatbevitel és a beállítások, jobb oldalon folyamatosan a készülő napi vagy heti étlap előnézete látható. Ugyanaz a Qt rajzoló készíti az előnézetet, az A4 PDF-et és a Facebookra szánt PNG-t.

![A hét beépített téma](Temak_elonezete.png)

## Funkciók

- **Napi étlap:** dátumonként kiválasztott à la carte ételek; a napi leves és A/B menü a heti szerkesztőből kerül a rögzített méretű felső blokkba.
- **Akciók:** a napi étellistán pipáld be az ételt, majd dupla kattintással vagy az **Akció beállítása…** gombbal nyisd meg az akciós szerkesztőt. Az akció jelölőnégyzete aktiválja az akciós ár mezőjét. Az árnak a normál árnál kisebbnek kell lennie. Az akció **csak a kiválasztott dátumra** vonatkozik. Az étlapon az eredeti ár áthúzva, az új ár pirossal és **AKCIÓ** felirattal látszik.
- **Heti menü:** hétfőtől péntekig önálló leves, A és B menü. A mezők gépelés közben javaslatokat adnak a külön **Menü** kategóriából; szabadon új fogás is beírható. A Menü kategória tételei nem jelennek meg a napi à la carte pipálható listában.
- **Ételadatbázis:** 328 induló tétel a feltöltött 2026. július–októberi étlapképek alapján, kategóriák, árak, keresés, felvétel, szerkesztés, törlés. Új adatbázisba automatikusan betöltődik. Meglévő adatbázisban az **Ételek → Alapadatbázis hiányzó ételeinek betöltése** gomb egészíti ki; ez nem írja felül a saját neveket, árakat vagy törölt tételeket.
- **Mentett étlapok:** napi és heti étlapok dátum szerint listázva. A kiválasztott mentés az előnézetben megnyitható és a mentéskori nevekkel, árakkal, akciókkal újra exportálható. Egy típushoz és dátumhoz a legutóbbi mentés tartozik.
- **Megjelenés:** hét beépített téma; egyedi és importált SVG/PNG díszítő elemek; PNG/JPG háttér; vezetőjelek; külön betűválasztás öt szövegtípushoz. A betűválasztók az operációs rendszer által elérhető telepített fontokat sorolják fel, Windows alatt a Windows fontjait.
- **Export:** 1440 × 1800 képpontos, 4:5 arányú Facebook PNG és A4 PDF. A napi étlap mindig egy kép: a fejléc és a napi menüblokk helye fix, az à la carte rész szükség esetén kisebb betűvel tördelődik.

## Indítás Windows alatt

1. Telepítsd a [Python 3](https://www.python.org/downloads/) 3.10-es vagy újabb verzióját a `py` launcherrel, ha nincs a gépen.
2. Töltsd le a repót ZIP-ként, csomagold ki egy írható mappába, és indítsd az `Inditas_Windows.bat` fájlt.
3. Az első indítás helyi `.venv` környezetet készít és telepíti a `requirements.txt` csomagjait. A következő indításokhoz használd ugyanezt a `.bat` fájlt.

Python nélküli használathoz a **Build Windows app** GitHub Actions munkafolyamat `EtlapStudio-Windows` artifactot készít. A csomagot ki kell bontani, majd `EtlapStudio.exe` indítható.

### Fejlesztői indítás

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python qt_app.pyw
```

## Használat

1. A **Beállítások** fülön add meg az étterem nevét, címét, telefonszámát.
2. Az **Ételek** fülön ellenőrizd az alapárakat, és szerkeszd vagy bővítsd az ételadatbázist.
3. A **Heti menü** fülön add meg a leveseket és az A/B menüket; kattints a mentésre.
4. A **Napi étlap** fülön válaszd ki a dátumot, pipáld be az ételeket. Akció esetén nyisd meg a kijelölt étel akciós szerkesztőjét, jelöld be az akciót és add meg az árat. Kattints a **Napi étlap mentése** gombra.
5. A **Megjelenés** fülön válassz témát, fontokat, hátteret, színeket és vezetőjelet. A jobb oldali előnézet a változásokat követi.
6. A jobb felső **PDF** vagy **Facebook PNG** gombbal exportálj. A **Mentett étlapok** fülön kiválasztott régi változatot ugyanígy exportálhatod.

Az adatbázis Windows alatt a `Dokumentumok\EtlapStudio\etlapstudio.sqlite3` fájlban van. A saját témák a `themes`, a háttérképek a `backgrounds` almappában. A biztonsági másolat az adatbázist menti; a saját importált grafikákat külön másold le. A meglévő Tkinter verzió adatbázisát az új program helyben bővíti az akciók táblájával. A már korábban dátumozott kiválasztások és heti menük első indításkor mentett bejegyzéssé is válnak az akkori aktuális árakkal.

A telepített rendszerfontok megjelennek a választókban. Egy font tényleges PDF-megjelenése a font és a Qt PDF motorjának támogatásától függ; a végleges exportot a PDF-ben is érdemes ellenőrizni. A választott saját betűtípus másik gépen csak akkor lesz ugyanolyan, ha azon is telepítve van.

## A feltöltött étlapokból készült alapadatbázis

A szerkeszthető [CSV fájl](data/alap_eteladatbazis.csv) 213 à la carte és 115 Menü kategóriájú tételt tartalmaz. A Menü kategóriában az üres ármező azt jelenti, hogy a fogáshoz nem volt külön ár: a korábbi lapokon látható **2800 Ft a levesből és főételből álló napi menü csomagára**, így ezt nem rendeltük hozzá egyik összetevőhöz sem. Az à la carte árak a legutóbbi jól olvasható **nem akciós** árak; a bizonytalan árakat üresen hagytuk, ezek az alkalmazásban „—” jellel szerepelnek. A CSV `megjegyzes` oszlopa jelzi a hiányzó árakat. A névírás OCR utáni kézi javítást és egységesítést kapott; a betöltött alapadatokat használat előtt érdemes az aktuális kínálathoz igazítani.

A menüfogások akkor is önálló Menü rekordok, ha ugyanaz az étel az à la carte kínálatban szerepel. Az első indítás adatbázisba másolja a CSV-t; későbbi CSV frissítésnél a gomb csak a hiányzó neveket veszi fel, meglévő árakat nem módosít. A korábban elmentett napi és heti étlapok tartalma változatlan.

## Saját grafikák

A beépített témák a `themes_builtin/` mappában vannak. A **Megjelenés → Témacsomag importálása…** egy ZIP-et fogad, amelyben SVG és/vagy PNG fejléc, elválasztó és sarokdísz van. A pontos formátum: [TEMACSOMAG_FORMATUM.md](TEMACSOMAG_FORMATUM.md). Kiindulás: [`TEMA_SABLON.zip`](TEMA_SABLON.zip). A [GRAPHICS_PROMPT.md](GRAPHICS_PROMPT.md) szövege bármely képgeneráló AI-nak adható; PNG háttér külön is importálható. Az app nem hív automatikusan AI szolgáltatást.

## Projekt

| Fájl | Szerep |
| --- | --- |
| `qt_app.pyw` | Qt6 szerkesztő és élő előnézet |
| `menu_core.py` | SQLite adatbázis, napi akciók, mentett étlapok |
| `data/alap_eteladatbazis.csv` | A felismert ételnevek és legutóbbi olvasható normál árak |
| `catalog_seed.py` | A CSV betöltése új vagy meglévő adatbázisba |
| `menu_render.py` | Közös Qt előnézet, A4 PDF és Facebook PNG rajzolás |
| `themes.py` | SVG/PNG témacsomagok ellenőrzése és importja |
| `themes_builtin/`, `backgrounds/` | Beépített grafikai elemek |
| `Inditas_Windows.bat` | Windows indítás és függőségek telepítése |
| `.github/workflows/windows-build.yml` | Windows futtatható csomag |

A GUI a **PyQt6** kötést használja, amely GPLv3 vagy kereskedelmi licenccel érhető el. Saját terjesztés előtt a választott licencfeltételeket ellenőrizni kell. Az alkalmazás helyi, nem tölt fel étlapot vagy adatot automatikusan.
