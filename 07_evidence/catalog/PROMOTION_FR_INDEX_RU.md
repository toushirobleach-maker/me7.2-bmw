# Промоушен после полного индекса FR (1043 стр.)

Источник: `07_analysis/fr_full_index/`  
Отчёт применимости: `FR_APPLICABILITY_6901I41D_RU.md`

## Счётчики XDF

| | Было (после MSLBAS/EWS/KFZW) | После FR-индекса |
|---|---:|---:|
| PROVEN | 31 | **44** |
| STRUCT | 23 | **12** |
| HYP | 2 | **0** |

## Что поднято благодаря FR+коду

- **MSLBAS** — FR DSLSLR: *Ini. secondary air mass* + consumer `0x819612`
- **CDAGR** (бывш. CWDAGR) — FR PROKON EURO DAGR inactiv + `0x11FC9→FDC0.4`
- **KFETRD / KFETRT** — FR ETR электрический термостат
- **TAMLTKA** — FR MLS E-fan PWM от температуры радиатора
- **MSLUB** — FR SLS f(ub)
- Патчи **SAP OFF**, **COMBO**, **88C*** → PROVEN

## Что осталось STRUCT (12)

- KFZW* + ignition patch — во FR семантика есть, **consumer адреса на 6901 нет**
- Gate NOP / EWS — во FR есть EWS как система, **не `0x380032`**
- Speed-limiter words — consumers есть, единицы нет
- TLRHS raw — роль FR ок, **масштаб LSB нет**
