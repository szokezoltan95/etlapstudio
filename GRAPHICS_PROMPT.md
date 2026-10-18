# Prompt étlapgrafikák készítéséhez

A program automatikusan az étlap dátumához igazítja az alapszíneket. Az importálható grafikák ezt egészítik ki: legyenek visszafogottak, áttetszők, és hagyjanak sok helyet a szövegnek. A teljes oldalas, mintás háttér, színes keret vagy panel nem része a jelenlegi dizájnnak.

## Témacsomag prompt

Másold be a promptot egy képgeneráló modellnek, és cseréld ki a zárójeles részeket:

```text
Készíts átlátszó hátterű, raszteres PNG díszítőelemeket egy letisztult éttermi
étlaphoz. Téma: [ÉVSZAK VAGY ÜNNEP]. A hangulatot ezek a színek adják:
[SZÍNEK]. Az eredmény visszafogott, kézzel festett, elegáns legyen.

Készíts külön fájlt mindegyikhez, pontosan az alábbi méretben:
1. header.png — 1200 × 200 px: egyetlen finom, vízszintes ecsetvonás, amely
   címsor mögé tehető. A középső terület maradjon közel egyszínű és szöveghez
   használható.
2. divider.png — 1200 × 200 px: egy vagy két vékony, áttetsző festett vonás,
   amely ételcsoportok között használható. Ne legyen doboz vagy panel.
3. corner.png — 290 × 290 px: egy apró, légies, áttetsző motívum a lap széléhez.

Az ecsetvonás legyen egyszerű és nagy formájú. Ne tegyél rá ismétlődő mintát,
geometrikus díszt, keretet, teljes oldalas hátteret, fehér vagy színes téglalapot,
szöveget, számot, logót vagy vízjelet. Tényleges alfa-átlátszóságot használj.
Minden fájlt külön PNG-ként adj vissza, a pontos kért méretben.
```

A fájlokat és a témaszíneket tartalmazó ZIP felépítését a
[TEMACSOMAG_FORMATUM.md](TEMACSOMAG_FORMATUM.md) írja le. Kiinduló csomag:
[`TEMA_SABLON.zip`](TEMA_SABLON.zip). Az app nem hív automatikusan AI-szolgáltatást.
