# Power maps pass-3

Дата: 2026-11-06T10:21:35.263477+00:00

## Подняты в PROVEN

- **KFATMZW** @ `0x19964` — consumer `0x85380e`
- **KFRINH** @ `0x19aea` — consumer `0x803486`
- **KFRINH2** @ `0x19b1c` — consumer `0x82ea9a`
- **KFATMZWE** @ `0x198c2` — consumer `0x85401e`
- **DZWSPM** @ `0x19628` — consumer `0x849b4c`

## KFZW* — OFFLINE_BLOCKED

Негатив pass-3 (доказано кодом): нет `MOV R13,#0x204/#205`, нет far-ptr на page 204/205 перед интерполятором, нет R12∈{0220,0320,0BC2,…}, слоты дескрипторов `0x7946`/`0x79AC` не читаются, тело `CALLS 0x00,0x791A` = `FFFF`.

Для PROVEN нужен дамп internal ROM или live-трасса, где база `0x810220`/`0x810BC2` уходит в интерполятор.
