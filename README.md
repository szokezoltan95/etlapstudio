# ÉtlapStúdió

Asztali program napi étlapok és heti menük készítésére. Az à la carte ételek és áraik helyi SQLite adatbázisba kerülnek; a heti leves és az A/B menü külön, szabad szövegként szerkeszthető. A heti terv adott napi sora automatikusan megjelenik a napi étlapon. Mindkét típusból készülhet A4 PDF és Facebookra szánt, álló PNG.

![A hét beépített téma előnézete](Temak_elonezete.png)

## Fő funkciók

- **Napi étlap:** dátumválasztás, aznapi à la carte kínálat kijelölése, automatikus leves és A/B menü a heti tervből.
- **Heti menü:** hétfő–péntek, naponként leves, A és B menü. Az ételnevek nem az à la carte adatbázisból származnak; a B menü üresen hagyható.
- **Ételadatbázis:** kategóriák, árak, keresés, hozzáadás, szerkesztés, törlés. Az alkalmazás üres adatbázissal indul.
- **Étlap-adatbázis:** a napi étlap külön Mentés gombbal, a heti menü a meglévő Mentés gombbal kerül az archívumba. A **Mentett étlapok** fül dátum szerint listázza az összes mentett napi és heti étlapot. Dupla kattintással újranyithatók, és a mentett változatból PDF vagy Facebook PNG készülhet. Azonos típus és dátum ismételt mentése az archív bejegyzést frissíti.
- **Megjelenés:** hét téma, állítható színek és díszítések, külön betűválasztás az étterem nevéhez, főcímhez, alcímekhez, heti/A-B menühöz és étel/ár sorokhoz. Az étel és az ár között kérhető pontozott, szaggatott vagy folytonos vezetőjel, illetve kikapcsolható. Importálható PNG/JPG háttér, állítható erősséggel; beépített botanikus PNG minta is van.
- **Export:** A4 PDF nyomtatáshoz és 4:5 arányú, 1440 × 1800 képpontos PNG közösségi megosztáshoz. A napi étlap mindig egy PNG: a fejléc és a napi menü blokk fix méretű, az à la carte rész betűmérete a tételek számához igazodik.
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
4. A **Napi étlap** fülön naponta válaszd ki az elérhető à la carte ételeket, majd kattints a **Napi étlap mentése** gombra. A heti szerkesztőben a **Heti menü mentése** gomb rögzíti az adott hetet.
5. A **Mentett étlapok** fülön egy régebbi étlapot dupla kattintással megnyithatsz, és újra exportálhatsz.
6. A **Megjelenés** fülön állítsd be a témát, az öt betűtípust, a vezetőjelet és szükség esetén a háttérképet. A napi és heti export azonos beállításokat használ.
7. Ments PDF-et vagy Facebook PNG-t. A PNG-ket az alkalmazás nem tölti fel automatikusan a Facebookra.

A helyi adatbázis Windows alatt a `Dokumentumok\EtlapStudio\etlapstudio.sqlite3` fájlba kerül. Az importált témák a `themes`, a saját háttérképek a `backgrounds` mappában vannak. A biztonsági másolat az **Étterem adatai** fülön készíthető; a saját háttérképeket és témákat külön másold le, ha másik gépre költözöl. A program könyvtárában nincs éles ételadatbázis.

> A **Mentett étlapok** fülön újraexportált étlap a mentéskori ételneveket, árakat, heti szövegeket és megjelenési beállításokat használja. Ha viszont egy régi dátumot közvetlenül a Napi étlap szerkesztőjében exportálsz újra, ott továbbra is az aktuális à la carte adatbázis adatai érvényesek. Az importált egyedi grafikák fájljait is őrizd meg: az archívum ezekre hivatkozik, nem másolja be őket az SQLite-ba.

Korábbi telepítés első indításakor a már dátumozott napi kiválasztások és heti menük bekerülnek az archívumba a **migráláskor aktuális** ételárakkal. A korábbi árváltozatok nem állíthatók helyre, ha azok nem voltak mentve.

## Témák és saját grafikák

A beépített SVG-k a `themes_builtin/` könyvtárban vannak. A **Megjelenés → Témacsomag importálása** gombbal új ZIP tölthető be SVG vagy PNG díszítő elemekkel, akár vegyesen. A szerződés és méretek: [TEMACSOMAG_FORMATUM.md](TEMACSOMAG_FORMATUM.md). A [`TEMA_SABLON.zip`](TEMA_SABLON.zip) másolható SVG kiindulópont. A [GRAPHICS_PROMPT.md](GRAPHICS_PROMPT.md) teljes, modellfüggetlen promptot tartalmaz új grafikai készlet létrehozásához.

Háttérképhez nem kell SVG vagy ZIP: az AI-val készített PNG-t vagy JPG-t a **Megjelenés → PNG/JPG importálása** gomb tölti be. Ajánlott méret **1440 × 1800 px**, álló **4:5** arányban, a kép közepén nagy üres hellyel. Legalább 800 × 1000 px, legfeljebb 20 MB és 36 megapixel megengedett. Az átlátszó PNG finom szegélymotívumokhoz különösen hasznos. A kép az oldal teljes felületére nyúlik; A4 PDF esetén az eltérő oldalarány miatt kissé torzulhat. A betűk olvashatósága érdekében az erősséget alacsonyan érdemes tartani. A beépített botanikus minta a `backgrounds/botanical.png` fájl.

Egy csomag négy fájlja: `manifest.json` és a `header`, `divider`, `corner` elemek. SVG méretek: 600 × 100, 600 × 100, 145 × 145 viewBox; PNG méretek: 1200 × 200, 1200 × 200, 290 × 290 px. A `manifest.json` az egyes elemek `.svg` vagy `.png` fájlnevére hivatkozik. Az app a fájlokat betöltés előtt ellenőrzi. Az SVG-k vektorként, a PNG-k áttetszőséggel kerülnek a PDF-be; a Facebook PNG ugyanabból az elrendezésből készül. A színválasztó az SVG motívumokat is átszínezi, a PNG motívumok saját színeiket megtartják.

## Projektfájlok

| Fájl | Szerep |
| --- | --- |
| `etlapstudio.pyw` | Asztali felület, SQLite, PDF és PNG export |
| `themes.py` | Témacsomag betöltés és importellenőrzés |
| `themes_builtin/` | Hét beépített témacsomag |
| `generate_assets.py` | A beépített vektordíszek forrásgenerátora |
| `fonts/` | PDF-be ágyazott DejaVu betűk és licencük |
| `backgrounds/botanical.png` | Beépített, átlátszó botanikus háttér |
| `Inditas_Windows.bat` | Helyi Python környezet létrehozása és indítás |
| `.github/workflows/windows-build.yml` | Windows `.exe` csomag készítése |

## Jelenlegi korlátok

A heti menü hétfőtől péntekig jelenik meg. Az app egyetlen gépen, helyi adatbázissal dolgozik. A grafikai előnézet a téma színeit és fejlécdíszét mutatja; a teljes végleges tördelés a PDF/PNG exportban látszik. Nagyon sok vagy különösen hosszú à la carte tételnél az egyetlen napi PNG betűi kicsik lehetnek. Az archívum típusonként és dátumonként a legutóbbi mentést őrzi; korábbi verziókat ugyanarra a dátumra nem tart meg.
