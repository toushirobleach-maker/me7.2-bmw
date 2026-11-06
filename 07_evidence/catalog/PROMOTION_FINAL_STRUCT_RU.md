# Финальный дожим оставшихся STRUCT (неудачный для PROVEN)

Дата: 2026-11-06. Модель сабагентов: Auto.

Отчёты:
- `PROMOTION_KFZW2_REPORT.json` / `_RU.md`
- `PROMOTION_REMAINING3_REPORT.json` / `_RU.md`

## Вердикты

| Тема | Вердикт | Почему не PROVEN | Что нужно дальше |
|---|---|---|---|
| **KFZWOP/KFZW1 адрес** | STILL_STRUCT | Нет MOV/EXTP/far-ptr на `0x0220`/`0x0BC2`; cal-слова `@0x817946/79AC` без xref (LE `7946`/`79AC` = 0 во всём BIN) | DAMOS/A2L **6901**, live map ID, или эмулятор с трассировкой косвенного дескриптора |
| **EWS ↔ `0x380032`** | STILL_STRUCT | Gate/`FF00`/`F922` assembly доказаны; mem16-чтений `F922` нет; `B_ews_ok@0x383150` опровергнут | Live: корреляция `0x380032`/`F922` с `B_EWS_OK` / запрет топлива при NOP off |
| **Speed units** | STILL_STRUCT | EXTP-потребители есть; `/128` vs `/256` без якоря 6901 | Live vfzg рядом с порогом или FR+формула на этот FW |
| **TLRHS scale** | STILL_STRUCT | `FD48.1` ≠ 100 ms tick (start-бит `@0x870F28`); период задачи `87508A` не доказан | Трассировка scheduler / live длительности hot-start delay |

## Итог для XDF

**44 PROVEN / 12 STRUCT / 0 HYP** — без изменений после этого прохода.  
В патч из этих четырёх тем **ничего не повышено** (правило тройки).

Офлайн-реверс по flash+FR на этих пунктах **исчерпан** до внешнего якоря (live / DAMOS / эмулятор).
