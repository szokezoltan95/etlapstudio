# ÉtlapStúdió

Asztali program napi étlapok és heti menük készítésére. Az à la carte ételek és áraik helyi SQLite adatbázisba kerülnek; a heti leves és az A/B menü külön, szabad szövegként szerkeszthető. A heti terv adott napi sora automatikusan megjelenik a napi étlapon. Mindkét típusból készülhet A4 PDF és Facebookra szánt, álló PNG.

![A hét beépített téma előnézete](Temak_elonezete.png)

## Fő funkciók

- **Napi étlap:** dátumválasztás, aznapi à la carte kínálat kijelölése, automatikus leves és A/B menü a heti tervből.
- **Heti menü:** hétfő–péntek, naponként leves, A és B menü. Az ételnevek nem az à la carte adatbázisból származnak; a B menü üresen hagyható.
- **Ételadatbázis:** kategóriák, árak, keresés, hozzáadás, szerkesztés, törlés. Az alkalmazás üres adatbázissal indul.
- **Megjelenés:** klasszikus, tavasz, nyár, ősz, tél, karácsony és húsvét téma; állítható alap- és kiegészítő szín; díszítések ki- és bekapcsolása; új SVG témacsomag importja.
- **Export:** A4 PDF nyomtatáshoz és 4:5 arányú, 1440 × 1800 képpontos PNG közösségi megosztáshoz. A több oldalra törő étlap számozott PNG-fájlokba kerül.
- **Adatok:** helyi SQLite, kézi biztonsági mentés. Nincs fiók és szerverkapcsolat.

## Indítás Windows alatt

1. Telepítsd a [Python 3](https://www.python.org/downloads/) 3.10-es vagy újabb verzióját, ha még nincs a gépen. A telepítőben engedélyezd a Python launchert (`py`).
2. Töltsd le a repót ZIP-ként, és csomagold ki egy írható mappába.
3. Indítsd az `Inditas_Windows.bat` fájlt. Az első indítás létrehoz egy helyi `.venv` környezetet és telepíti a PDF/SVG/PNG modulokat. Ehhez internetkapcsolat kell.
4. Ezután minden alkalommal ugyanezzel a fájllal indítsd az appot.

Ha Python nélküli változat kell, a **Build Windows app** GitHub Actions munkafolyamat Windows futtatható csomagot készít. A sikeres futás után az Actions oldalon az `EtlapStudio-Windows` artifact tölthető le. Az artifactot ki kell csomagolni, és az `EtlapStudio.exe` fájlt indítani.

### Fejlesztői indítás

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python etlapstudio.pyw
```

Linuxon a Tkinter rendszerfüggőséget külön is telepíteni kellhet. A program Python 3.10+ verzióval működik.

## Használat

1. Az **Étterem adatai** fülön írd be a nevet, címet, telefonszámot és az alsó megjegyzést.
2. Az **Ételek és árak** fülön vedd fel az à la carte kínálatot.
3. A **Heti menü** fülön szerkeszd a hétfőtől péntekig tartó tervet. A Mentés gombbal vagy másik fülre lépve mentődik.
4. A **Napi étlap** fülön naponta válaszd ki az elérhető à la carte ételeket.
5. A **Megjelenés** fülön állítsd be a témát. A napi és heti export azonos megjelenést használ.
6. Ments PDF-et vagy Facebook PNG-t. A PNG-ket az alkalmazás nem tölti fel automatikusan a Facebookra.

A helyi adatbázis Windows alatt a `Dokumentumok\EtlapStudio\etlapstudio.sqlite3` fájlba kerül. Importált témák ugyanitt, a `themes` mappában vannak. A biztonsági másolat az **Étterem adatai** fülön készíthető. A program könyvtárában nincs éles ételadatbázis.

> Az árak az ételadatbázis aktuális értékei. Ha később módosítasz egy árat, egy régi dátum újraexportált PDF/PNG fájlján már az új ár szerepel. A korábban elmentett fájlok természetesen nem változnak.

## Témák és saját grafikák

A beépített SVG-k a `themes_builtin/` könyvtárban vannak. A **Megjelenés → Témacsomag importálása** gombbal új ZIP tölthető be. A szerződés és méretek: [TEMACSOMAG_FORMATUM.md](TEMACSOMAG_FORMATUM.md). A [`TEMA_SABLON.zip`](TEMA_SABLON.zip) másolható kiindulópont. A [GRAPHICS_PROMPT.md](GRAPHICS_PROMPT.md) teljes, modellfüggetlen promptot tartalmaz új grafikai készlet létrehozásához.

Egy csomag négy fájlja: `manifest.json`, `header.svg` (600 × 100), `divider.svg` (600 × 100), `corner.svg` (145 × 145). Az app a fájlokat betöltés előtt ellenőrzi. Az SVG-k vektorként kerülnek a PDF-be; a Facebook PNG ugyanabból az elrendezésből készül.

## Projektfájlok

| Fájl | Szerep |
| --- | --- |
| `etlapstudio.pyw` | Asztali felület, SQLite, PDF és PNG export |
| `themes.py` | Témacsomag betöltés és importellenőrzés |
| `themes_builtin/` | Hét beépített témacsomag |
| `generate_assets.py` | A beépített vektordíszek forrásgenerátora |
| `fonts/` | PDF-be ágyazott DejaVu betűk és licencük |
| `Inditas_Windows.bat` | Helyi Python környezet létrehozása és indítás |
| `.github/workflows/windows-build.yml` | Windows `.exe` csomag készítése |

## Jelenlegi korlátok

A heti menü hétfőtől péntekig jelenik meg. Az app egyetlen gépen, helyi adatbázissal dolgozik. A grafikai előnézet a téma színeit és fejlécdíszét mutatja; a teljes végleges tördelés a PDF/PNG exportban látszik. A hosszú napi étlap több PNG-re kerül. A korábbi árváltozatokat az adatbázis jelenleg nem tárolja.
