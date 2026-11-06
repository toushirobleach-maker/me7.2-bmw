# Последовательный дожим: MSLBAS → EWS → KFZW

Сабагенты: Auto. Контракт: consumer (`review_decode.py`) + независимый якорь + falsifier.

## 1. MSLBAS @`0x19612`

**Вердикт: не MSLBAS PROVEN → STRUCT под новым именем**

| | |
|---|---|
| Доказано | 4× EXTP#206 → `0x819612` → сид `AF2C`/`AF2D` → `8A8D`/`8A8E` |
| Не доказано | Имя Bosch MSLBAS; связь с кривой MSLUB `0x196A9` |
| FR | Есть MSLUB, строки MSLBAS нет |
| Для PROVEN имени | Ярлык 6901 на адрес **или** `8A8D` ≡ FR `msl`/`mslstat` |

Отчёт: `PROMOTION_MSLBAS_*.md/json`  
XDF: `[STRUCT] AF2C/AF2D init scalar @0x19612`

## 2. EWS / `0x380032`

**Вердикт: STILL_STRUCT — EWS не доказан**

| | |
|---|---|
| Доказано | Ворота `0x85FFB2`, запись `0xFF00`/`FFFF` → phys `0x380032`; 7× `OR …,0x8032` → `CMP #FFFF` / `F922` |
| Не доказано | Что слово = immobilizer release; fuel/starter/CAN-EWS |
| Фальсификатор | «это `B_ews_ok`» — **FIRED** (в чужом A2L `B_ews_ok` @`0x383150`, не здесь) |

Отчёт: `PROMOTION_EWS_*.md/json`  
Патч NOP остаётся STRUCT без ярлыка «IMMO OFF» как PROVEN.

## 3. KFZWOP / KFZW1

**Вердикт: оба STILL_STRUCT**

| | |
|---|---|
| Поиск | `MOV #0x0220/#0x0BC2`, far-ptr, EXTP#204/#205 — **пусто** (EXTP#206 census ок) |
| Cal | Слова-оффсеты @`0x817946` / `0x8179AC` без xref из кода |
| °/LSB | Signed `0.75` на 6901 для этих карт **не доказан** |

Отчёт: `PROMOTION_KFZW_*.md/json`

## Итог очереди

Ни один из трёх пунктов **не** стал PROVEN по исходному бизнес-имени.  
Уточнены формулировки XDF; HYP по «MSLBAS» снят в пользу STRUCT с нейтральным именем.

Остаток HYP в XDF: в основном **CWDAGR** (транспорт есть, AGR — нет).  
SAP OFF / COMBO по-прежнему не PROVEN целиком, пока «MSL*» в бандле без доказанных имён.