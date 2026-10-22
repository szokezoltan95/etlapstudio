# ÉtlapStúdió

Windowsra szánt, helyi adatbázissal működő **Qt6 asztali étlapszerkesztő**. A napi, heti és különleges étlapok szerkeszthetők, előnézetben ellenőrizhetők, menthetők, majd PDF-be vagy képként exportálhatók. A felső menüsorban érhető el az adatkezelő, a külön ablakos étlaparchívum, a fájlműveletek és a **Program** menü frissítés-ellenőrzése.

![A hét beépített téma](Temak_elonezete.png)

## Funkciók

- **Napi étlap:** az új nap az előző olyan nap választásából indul, amelyen már volt étel. A kompakt kategóriagombok mindig láthatók; az ételrács az ablak szélességéhez igazodik, és kizárólag függőlegesen görgethető. Az ételre kattintva felugró ablakban lehet felvenni vagy kivenni, a normál és akciós árat pedig egyszerűen be lehet írni. A Mentés a normál árat, a napi kiválasztást és az akciót együtt, azonnal rögzíti. A napi leves és az A/B menü a heti szerkesztőből kerül a felső blokkba.
- **Akciók:** az étel felugró ablakában az akció jelölőnégyzete bekapcsolja az akciós ár mezőjét. Az árnak a normál árnál kisebbnek kell lennie. Az akció csak az adott napra vonatkozik. Az étlapon az eredeti ár áthúzva, az új ár pirossal és **AKCIÓ** felirattal látszik.
- **Heti menü:** hétfőtől péntekig önálló leves, A és B menü, nagyobb betűkkel és a nap nevével a fogások fölött. A mezők gépelés közben javaslatokat adnak a külön **Menü** kategóriából; szabadon új fogás is beírható. A Menü kategória tételei nem jelennek meg a napi à la carte pipálható listában.
- **Ételadatbázis:** 348 induló tétel a feltöltött 2026. július–októberi étlapképek alapján, kategóriák, árak, keresés, felvétel, szerkesztés, törlés. Új adatbázisba automatikusan betöltődik. Meglévő adatbázisban az **Ételek → Alapadatbázis hiányzó ételeinek betöltése** gomb egészíti ki; ez nem írja felül a saját neveket, árakat vagy törölt tételeket.
- **Korábbi étlapok:** a felső menüsor külön ablakában, hetek szerint csoportosítva érhetők el. Egy kattintás az előnézetet mutatja, dupla kattintással szerkeszthetők; a mentett étlapok törölhetők.
- **Dizájn:** a választott téma együtt állítja a színpalettát és a háttérképet; a tavasz és a húsvét, illetve a tél és a karácsony külön grafikát kap. A szekciókat finom, évszakhoz illő line-art elválasztók tagolják, nem tömör színű grafikai blokkok. Az áttetsző üveghatású panelek segítik az olvashatóságot. A betűválasztók a Windowsra telepített betűket listázzák. Az alapértelmezett címbetű Candara, a szövegbetű Segoe UI. A képernyőképen megadott betűméretek az alapértékek; a **Dizájn visszaállítása alapértékre** gomb ezeket, a betűket, színeket és térközöket is visszaállítja.
- **Export:** A4 álló formátumú Facebook PNG 1240 × 1754 képpontban, 150 dpi-vel, valamint margó nélküli A4 PDF. Az előnézet ugyanezt az A4-es oldalarányt használja. A Dizájn fülön minden szövegtípushoz külön betűtípus és nyomdai pontban (pt) megadott méret választható. A napi étlap egy képen marad; az à la carte ételnevek a beállított maximális méretnél automatikusan kisebbre zsugorodnak, ha a tördelés megkívánja.
- **Étlapfejléc:** az első üveghatású panelen balra a teljes, feliratos logó, középen függőlegesen középre igazítva a napi vagy heti cím és a dátum, jobbra pedig jobbra igazítva az étterem neve, címe, telefonszáma és Facebook-linkje jelenik meg. Mind a négy adat szerkeszthető a Dizájn fülön; az étterem neve ugyanolyan visszafogott adatmező, mint a többi. A második panelen a napi lapon csak a leves és az A/B menü jelenik meg. A heti lapon a fejléc alatt külön, csak az árat tartalmazó panel van, utána következnek a napok és fogások.
- **À la carte tagolás:** a szekciók között kis térköz van. A címsor csak a saját színes fület kapja meg, amely közvetlenül a hozzá tartozó fogások fölött áll; nincs teljes szélességű üvegpanelezés a címsor mögött.

## Indítás Windows alatt

1. Telepítsd a [Python 3](https://www.python.org/downloads/) 3.10-es vagy újabb verzióját a `py` launcherrel, ha nincs a gépen.
2. Töltsd le a repót ZIP-ként, csomagold ki egy írható mappába, és indítsd az `Inditas_Windows.bat` fájlt.
3. Az első indítás helyi `.venv` környezetet készít és telepíti a `requirements.txt` csomagjait. A következő indításokhoz használd ugyanezt a `.bat` fájlt.

A Python telepítése nélkül használható Windows telepítőt a [GitHub Releases](https://github.com/szokezoltan95/etlapstudio/releases/latest) oldalról töltheted le. A 64 bites `EtlapStudio-Setup-1.0.2.exe` telepíti az alkalmazást, létrehozza a Start menü parancsikont, és opcionálisan asztali ikont is készít. Az új Megyeháza Étterem logó jelenik meg programikonként és az indulóképernyőn; a splash képen az „ÉtlapStúdió indítása” szöveg is szerepel. A telepített Windows-verzióban a **Program → Frissítések keresése…** menüponttal ellenőrizheted az új kiadásokat. Jóváhagyás után az alkalmazás szabályosan bezárja az adatbázist, a külön frissítő pedig Windows-folyamatkezelőn várja meg a tényleges leállást, mielőtt elindítja a telepítőt.

### Fejlesztői indítás

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate
# Linux/macOS: source .venv/bin/activate
pip install -r requirements.txt
python qt_app.pyw
```

## Használat

1. A **Dizájn** fülön add meg az étterem nevét, címét, telefonszámát és Facebook-linkjét.
2. A **Heti** fülön írd be hétfőtől péntekig a leveseket és az A/B menüket.
3. A **Napi** fülön állítsd be a dátumot. A már használt étlapról indul; a kategóriagombokkal vagy keresővel válassz ételeket. Kattints a fogásra, majd a felugró ablakban add meg a kívánt árat és akciót.
4. A **Dizájn** fülön válassz évszakot, betűtípust, színeket és háttér-erősséget.
5. Mentsd az étlapot, majd exportáld PDF-be vagy Facebook-képként. A korábbi mentéseket a **Fájl → Megnyitás…** ablakban nyithatod meg, szerkesztheted vagy törölheted.

Az adatbázis Windows alatt a `Dokumentumok\EtlapStudio\etlapstudio.sqlite3` fájlban van, az alkalmazás telepítési mappájától külön. A kézi újratelepítő és az automatikus frissítő csak a programfájlokat cseréli. Az új verzió induláskor, tranzakcióban bővíti a régi adatbázissémát az étel-prioritás mezővel; megőrzi az ételneveket, kategóriákat, árakat, napi/heti étlapokat, egyedi sorrendeket és éttermi beállításokat. A korábban mentett sorrendkódokat átviszi az új mezőbe. A korábbi `itcetterem` Facebook-címet automatikusan a jelenlegi oldalra javítja, de más, egyedi címet érintetlenül hagy. Az importált témacsomagok a `themes` almappába kerülnek. A biztonsági másolat az adatbázist menti; a témacsomagokat is másold le, ha új gépre költözöl. A régi napi választások és heti menük első indításkor mentett bejegyzéssé is válnak.

A telepített rendszerfontok megjelennek a választókban. Egy font tényleges PDF-megjelenése a font és a Qt PDF motorjának támogatásától függ; a végleges exportot a PDF-ben is érdemes ellenőrizni. A választott saját betűtípus másik gépen csak akkor lesz ugyanolyan, ha azon is telepítve van.

## A feltöltött étlapokból készült alapadatbázis

A szerkeszthető [CSV fájl](data/alap_eteladatbazis.csv) 233 à la carte és 115 Menü kategóriájú tételt tartalmaz. A Menü kategóriában az üres ármező azt jelenti, hogy a fogáshoz nem volt külön ár: a korábbi lapokon látható **2800 Ft a levesből és főételből álló napi menü csomagára**, így ezt nem rendeltük hozzá egyik összetevőhöz sem. Az à la carte árak a legutóbbi jól olvasható **nem akciós** árak; a bizonytalan árakat üresen hagytuk, ezek az alkalmazásban „—” jellel szerepelnek. A CSV `megjegyzes` oszlopa jelzi a hiányzó árakat. A névírás OCR utáni kézi javítást és egységesítést kapott; a betöltött alapadatokat használat előtt érdemes az aktuális kínálathoz igazítani.

A menüfogások akkor is önálló Menü rekordok, ha ugyanaz az étel az à la carte kínálatban szerepel. Az első indítás adatbázisba másolja a CSV-t; későbbi CSV frissítésnél a gomb csak a hiányzó neveket veszi fel, meglévő árakat nem módosít. A korábban elmentett napi és heti étlapok tartalma változatlan.

## Saját grafikák

Az automatikus évszakos képek a `design_assets/` mappában vannak. Az étlap fejlécében a teljes, Megyeháza-épületet és étteremnevet is tartalmazó `megyehaza_wordmark.png` logó, a szerkesztőben pedig a `megyehaza_emblem.png` jelenik meg. A `spring_generic_background.jpg` általános tavaszi tájat, a `winter_generic_background.jpg` karácsonyi díszítés nélküli téli tájat mutat; a húsvéti és karácsonyi témák külön hátteret használnak. A klasszikus, négy évszakos, húsvéti, karácsonyi, Valentin-napi és augusztus 20-i témához is öt-öt átlátszó vonalas elválasztó készült. Az app a dátum alapján forgatja őket, a heti étlapon pedig a napok között is váltanak. Az új témacsomag egy finom vonalrajzos `divider.png`-ből és opcionális `background.png`-ből áll. A generálási promptokat és pontos importméreteket a [GRAPHICS_PROMPT.md](GRAPHICS_PROMPT.md) és a [TEMACSOMAG_FORMATUM.md](TEMACSOMAG_FORMATUM.md) írja le. A **Dizájn → Témacsomag importálása…** PNG-grafikákat és színpalettát tartalmazó ZIP-et fogad. Az app nem hív automatikusan AI-szolgáltatást.

Az automatikus téma az étlap **dátuma** alapján választ, és az étterem hétköznapi nyitvatartásához igazodik. A húsvéti időszak a húsvétvasárnap előtti 14. napon kezdődik, és az azt megelőző utolsó hétköznap végén lezárul; a mozgó dátumot a program minden évre kiszámítja. A karácsonyi háttér és elválasztó december 1–23. között aktív, tehát még az ünnep előtt; utána az általános téli grafika következik. Január–februárban tél, március–májusban tavasz, június–augusztusban nyár, szeptember–novemberben ősz jelenik meg. Valentin-nap előtt az utolsó öt munkanapon, valamint magán a Valentin-napon is megjelenik a külön téma, ha február 14. hétköznapra esik. Augusztus 20. előtt az ünnepet megelőző utolsó öt hétköznapon aktív az ünnepi téma. Hétvégi napokra nem kerül ünnepi étlap, mert az étterem zárva tart. Október 20-tól az őszhez tartozik egy mélyebb színpaletta; ez évszakváltás, nem külön ünnepi téma.

A **Különleges** füllel egyedi alkalomra készíthetsz étlapot: a dátum és a címsor szerkeszthető, a nagy szövegpanelen pedig félkövér, dőlt, aláhúzott, színezett, igazított és különböző betűméretű szöveget formázhatsz. Ez a változat is menthető az előzményekbe, és exportálható PDF-be vagy Facebookra szánt PNG-képbe.

## Licenc

A projekt alkalmazáskódja az [MIT licenc](LICENSE) alatt érhető el. A licenc lehetővé teszi a szoftver használatát, módosítását és továbbterjesztését, az eredeti szerzői jogi és licencmegjelölés megtartásával. A szoftver garancia nélkül, „ahogy van” állapotban kerül közzétételre.

A külső függőségek, betűkészletek és más, külön licenccel rendelkező mellékelt fájlok saját licencfeltételei ettől függetlenül érvényesek. Az MIT licenc csak azokra a projektfájlokra vonatkozik, amelyekre külön licenc nincs megadva.

## Projekt

| Fájl | Szerep |
| --- | --- |
| `qt_app.pyw` | Qt6 szerkesztő és élő előnézet |
| `menu_core.py` | SQLite adatbázis, sémamigráció, étel-prioritások, napi akciók és mentett étlapok |
| `updater.py` | Windows-frissítő, amely natív folyamatfogantyúval vár a program bezárására |
| `version.py` | Alkalmazásverzió, amelyet a kiadási build a git tag alapján állít be |
| `data/alap_eteladatbazis.csv` | A felismert ételnevek és legutóbbi olvasható normál árak |
| `catalog_seed.py` | A CSV betöltése új vagy meglévő adatbázisba |
| `menu_render.py` | Közös Qt előnézet, A4 PDF és Facebook PNG rajzolás |
| `themes.py` | PNG témacsomagok ellenőrzése és importja |
| `design_assets/` | Szezonális képek, logó és elválasztók |
| `Inditas_Windows.bat` | Windows indítás és függőségek telepítése |
| `.github/workflows/windows-build.yml` | Windows futtatható csomag |

A GUI a **PyQt6** kötést használja, amely GPLv3 vagy kereskedelmi licenccel érhető el. Saját terjesztés előtt a választott licencfeltételeket ellenőrizni kell. Az alkalmazás helyi, nem tölt fel étlapot vagy adatot automatikusan.
