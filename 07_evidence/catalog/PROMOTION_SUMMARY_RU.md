# Итог промоушена STRUCT/HYP → PROVEN

Сабагенты: **Auto** (`inherit`).  
Отчёты: `PROMOTION_CLA_PROKON_REPORT.json`, `PROMOTION_MISC_REPORT.json`.

## Счётчики

| | До | После |
|---|---:|---:|
| PROVEN | 12 | **31** |
| STRUCT | 34 | **22** |
| HYP | 10 | **3** |

## Что стало PROVEN

Всё из CLA/PROKON-пакета (17 адресов), включая:
- `CWKONLS`, `CWKONABG`, SAP passport `0x1A5EC`, `CWDKAT`
- `ESKONF[3]/[5]` (+ таблица ESKONF)
- `CLALSH/2`, `CLALASH/2`, `CLAHSH/2`, `CLASLPE/VE`, `CLAHSV/2`
- `DTEVE` @`0x1165B` (DTC `0x62`, idx `0x82`) — не путать с `0x11611`
- патч **DECAT / rear O2** (все entry закрыты)

Тройка: consumer через `review_decode.py` + FR/DTC/`0x153F2` + falsifier DID_NOT_FIRE.

## Что осталось STRUCT

Форма/байты есть, бизнес до конца нет:
- SAP OFF / COMBO (внутри ещё `MSLBAS` = HYP)
- 88C thermo/fan, ignition maps, gate@`0x5FFB2` (эффект доказан, имя EWS = HYP)
- TLRHS timebase, KFZW* имена/размеры без consumer 6901
- MSLUB, speed-words (подняты с HYP только до STRUCT)

## Что осталось HYP (3)

1. `CWDAGR` + патч `CWDAGR→00` — транспорт на `FDC0.4` есть, AGR не привязан  
2. `MSLBAS` — consumer `0x819612` есть, имени/SAP во FR нет  

## Дальше, если дожимать

1. Live/FR-якорь на `MSLBAS` → можно поднять SAP OFF/COMBO  
2. Кто семантически `0x380032` (EWS)  
3. Consumer KFZW* на 6901  
4. Период задачи для TLRHS  
5. Привязка `FDC0.4` к AGR