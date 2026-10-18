# Prompt étlapgrafikák készítéséhez

A program az étlap dátumához igazítja az alapszíneket. A kívánt hangulat kézzel rajzolt, barátságos éttermi vintage: meleg krémpapír, bordó és ünnep szerint változó kiegészítőszínek, finom tusos vagy festett részletek. A referencia a korszak hangulatát mutatja; ne másold le annak pontos elrendezését, emblémáját, feliratait vagy karaktereit. Hagyj bőséges, tiszta helyet az ételneveknek és áraknak.

## Témacsomag prompt

Másold be a promptot egy képgeneráló modellnek, és cseréld ki a zárójeles részeket:

```text
Készíts átlátszó hátterű, raszteres PNG díszítőelemeket egy magyar étterem
klasszikus, barátságos napi étlapjához. Téma: [ÉVSZAK VAGY ÜNNEP]. Színek:
meleg krém és pergamen, mély bordó, valamint [SZEZONÁLIS KIEGÉSZÍTŐSZÍN].
Kézzel rajzolt, elegáns vintage éttermi illusztráció legyen, tiszta és könnyen
olvasható tipográfiával; az ételneveknek és áraknak maradjon hely.

Készíts külön fájlt mindegyikhez, pontosan az alábbi méretben:
1. header.png — 1200 × 200 px: egyetlen egyszerű, vízszintes bordó festéksáv
   áttetsző háttéren. Címsor kerül rá, ezért legyen egyenletes és jól olvasható.
2. divider.png — 1200 × 200 px: vékony, visszafogott kézzel festett vonás,
   esetleg két apró növényi vagy konyhai tollrajz a két végén.
3. corner.png — 290 × 290 px: egy apró, könnyed étel- vagy fűszernövényrajz
   a lap széléhez, természetes, nyitott kompozícióval.

Az ecsetvonás legyen egyszerű, egy színű és ne túl vastag. Ne használj
ismétlődő mintát, sakktáblamintás keretet, panelt, feliratot, számot, logót
vagy vízjelet. Tényleges alfa-átlátszóságot használj; a motívumokon kívüli
terület legyen átlátszó. Minden fájlt külön PNG-ként adj vissza, a pontos
kért méretben.
```

## Külön prompt az éttermi emblémához

```text
Készíts friss, barátságos, kézzel rajzolt éttermi emblémát a Megyeháza Étteremnek.
Kis méretben is felismerhető, önálló séfkarakter vagy konyhai motívum legyen,
krém, bordó, olívazöld és kevés meleg arany színekkel. Vintage nyomdai rajz
enyhe akvarellkitöltéssel. Ne másold a referencia emblémáját, ne használj
szöveget, betűket, vízjelet, keretet, hátteret vagy mockupot. Átlátszó PNG.
```

A fájlokat és a témaszíneket tartalmazó ZIP felépítését a
[TEMACSOMAG_FORMATUM.md](TEMACSOMAG_FORMATUM.md) írja le. Kiinduló csomag:
[`TEMA_SABLON.zip`](TEMA_SABLON.zip). Az app nem hív automatikusan AI-szolgáltatást.
