# Статус: доказанные карты (все)

## Вердикт

**Все карты PROVEN offline — невозможно** на одном внешнем 512 KiB дампе.

Причина: семейство на стр. `0x204` (KFZW*, KFPU*, KFMIZU*, LUR/LUAR/… ) не имеет видимого consumer в flash; путь, судя по дескрипторам + `CALLS 0x791A`, уходит в **internal ROM** (`0x791A` = `FFFF`).

По правилам доказательств: без инструкции-потребителя с правильной страницей — **не PROVEN**, даже если имя/адрес из E5A0+FR и car-dump байты меняет.

## Счётчики DAMOS-lite

| Статус | Все символы | KF* |
|---|---:|---:|
| PROVEN | 154 | 56 |
| STRUCT | 98 | 7 |
| HYP | 300 | 39 |
| UNLINKED | 80 | 0 |

## Power / смесь / момент — PROVEN (стр. 0x206)

KFANS, KFATMLA, KFATMLA2, KFATMLAE, KFATMLAE2, KFATMZW, KFATMZW2, KFATMZWE, KFETRD, KFETRD, KFETRD, KFETRT, KFFTV, KFFTV2, KFKRMX, KFLAMFA, KFMDKO, KFMDKOG, KFMIRED, KFMIRED1, KFMIRLR, KFRI, KFRI2, KFRINH, KFRINH2, KFRP, KFRP2, KFRTV, KFRTV2, KFTATM, KFTATM2

Pass-3 добавил: `KFATMZW`, `KFATMZWE`, `KFRINH`, `KFRINH2` (addr fix), `DZWSPM`.

## Заблокировано offline (стр. 0x204) — 45 KF

Типичные: `KFZWOP/OP2/1/2/VL/MN/MNST`, `KFPU*`, `KFMIZU*`, `KFLUR*`, `KFLUAR*`, `KFDLUR*`, …

Отчёт: `KFZW_OFFLINE_BLOCK_PASS3_RU.md`.

Остаток KF на 0x206 без PROVEN: KFETATE.

## Что нужно для «всех карт»

1. Дамп / образ **internal ROM** (тело helper `0x791A` и соседей), **или**
2. Live-трасса (ETK/BDM), где в R12/base попадает `0x0220`/`0x0BC2` при интерполяции ZW.

Без этого патч по KFZW* и прочим page-204 KF — запрещён правилами репозитория.
