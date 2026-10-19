# Tematikus étlapgrafikák – AI promptok

Az ÉtlapStúdió az étlap dátuma alapján automatikusan állítja a színeket és a beépített évszakos hátteret. A saját/importálható témacsomag legfontosabb grafikai eleme egy finom, átlátszó hátterű vonalas elválasztó. A háttérgrafika választható. Az étlap fejlécére, szövegpanelekre vagy kategóriák mögé ne készüljön külön téglalap vagy ecsetvonás.

## 1. prompt – szezonális vonalas elválasztó

Az alábbi promptban cseréld ki az évszakot és a színeket. A generált `divider.png` közvetlenül betehető az importálható témacsomagba.

```text
Készíts elegáns, finom LINE-ART jellegű vízszintes elválasztó díszt egy
barátságos, modern magyar étterem nyomtatott étlapjához. Évszak / alkalom:
[TAVASZ / NYÁR / ŐSZ / TÉL / HÚSVÉT / KARÁCSONY]. Színpaletta: [ELSŐDLEGES
SZÍN] és [KIEGÉSZÍTŐ SZÍN].

Kép: pontosan 1800 × 120 px, vízszintes, teljesen átlátszó háttérrel (valódi
alfa-csatorna). Középen fusson egy vékony, finoman stilizált vonal vagy
indás szál, amelyhez az évszakot felismerhetővé tevő néhány apró vonalas dísz
kapcsolódik: például tavasszal levelek vagy apró virág, nyáron növényindák,
ősszel levél, télen hópehely. Ünnepi téma esetén csak visszafogott, kis
motívumot használj. A dísz légies, aszimmetrikus és elegáns legyen, a vonalak
ne legyenek vastagok. A grafika ne foglaljon el nagy felületet, a középső
terület maradjon könnyű és áttekinthető.

Ne készíts kitöltött téglalapot, színes sávot, ecsetvonást, kártyát, keretet,
panelt, ismétlődő mintát, hátteret vagy árnyékot. Ne legyen rajta szöveg,
betű, szám, logó, étel, vízjel vagy mockup. A motívumon kívül minden pixel
legyen teljesen átlátszó. PNG-ként add vissza, pontosan 1800 × 120 px méretben.
```

## 2. prompt – opcionális, visszafogott teljes oldalas háttér

```text
Készíts teljes oldalas, függőleges szezonális háttérillusztrációt egy A4-es
éttermi étlaphoz. Évszak / alkalom: [TÉMA]. Hangulat és színek: [RÖVID
LEÍRÁS]. Kép: pontosan 1440 × 2037 px.

Kézzel festett, természetes, finoman részletgazdag illusztráció legyen,
amelynek a szélein és sarkaiban jelennek meg a téma díszítő elemei. A lap
középső 75 százaléka világos, alacsony kontrasztú és nyugodt maradjon, mert
itt üveghatású, olvasható szövegpanelek fedik majd. A grafika legyen szép,
teljes színű, de ne versenyezzen az étlap szövegével.

Az általános téli témához ne tegyél karácsonyfát, díszt vagy ajándékot. Az
általános tavaszi témához ne tegyél hímes tojást, nyulat vagy húsvéti díszt.
Az ünnepi változatok ezektől különbözzenek. Ne tegyél a képre szöveget,
betűt, számot, logót, vízjelet, keretet vagy panelt. PNG-ként add vissza,
pontosan 1440 × 2037 px méretben.
```

## 3. Importálható témacsomag

Az új formátum minimálisan egy `divider.png` fájlt és egy `manifest.json`-t kér. Opcionálisan `background.png` is tehető mellé. A pontos méreteket és a minta manifestet a [TEMACSOMAG_FORMATUM.md](TEMACSOMAG_FORMATUM.md) tartalmazza. Kiinduló csomag: [`TEMA_SABLON.zip`](TEMA_SABLON.zip).

Ha a képgeneráló nem tud pontos képméretet vagy valódi átlátszóságot adni, utólag vágd/méretezd át, és ellenőrizd az alfa-csatornát. Az alkalmazás nem hív automatikusan AI-szolgáltatást.

## Logóprompt

```text
Készíts egyszerű, friss vonalrajzos logót a Megyeháza Étterem számára,
amelyben felismerhető a miskolci Megyeháza épülete. Használj kevés,
visszafogott bordó, zöld és krémszínt. A rajz kis méretben is legyen tiszta,
barátságos és jól olvasható; ne legyen túl díszes. Átlátszó hátterű PNG legyen,
vízjel, mockup, keret és fölösleges díszítés nélkül. A logón jelenjen meg a
„Megyeháza Étterem” felirat is.
```
