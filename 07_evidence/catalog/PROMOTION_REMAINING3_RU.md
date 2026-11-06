# Три оставшихся STRUCT — повторный triple-evidence

**A) EWS / `0x380032`: STILL_STRUCT**  
**B) Speed `0x1BBC0/C4/C8/CC`: STILL_STRUCT**  
**C) TLRHS scale `@0x1A753`: STILL_STRUCT**

SW `6901I41D` / BIN car+stock; декодер `review_decode.py` (калибровка `9F17`/`D7400602`/`C2F43016`). Патч из этого прохода **не** поднимать.

---

## A — `0x380032` / EWS

| Пункт | Статус | Факт |
|---|---|---|
| 1 consumer | **PASS** | Gate→`0xFF00`/`FFFF`→`0x8032` (phys DPP2=`0x380032`); 7×`OR …,0x8032`→`CMP #FFFF` / сборка `F922`/`F92A` |
| 2 семантика EWS | **FAIL** | FR знает EWS (STECK/SY WFS/`B ECULOCK`/EEDAT), live `B_EWS_OK`, но **не** адрес `0x380032`/`F922` |
| 3 опровержения | см. ниже | имя EWS не проходит |

**F922 readers:** при выровненном `review_decode` — только `MOV 0xF922/F92A,R2` (writers). Ложных «CMP R10,0xF922» из невыровненного скана нет. Топливо / стартёр / CAN-EWS из `F922` **не закрыты**.

**`0x383150` / `B_ews_ok` myth:** чужой A2L `B_ews_ok` @`0x383150` (E5A0) / `@0x38315D` (E650). На 6901 `0xB150` сравнивается с магией `0x7A61`, не Freigabebit. Gate смотрит `B154`/`B17A`/`FDDC.2`, не `B150.0`. **ID опровергнут.**

**`FD4A.5`:** пишется воротами; читается @`862F20`/`863140`→`FDAC.3`. Чужой A2L: `B_eculock` @`FD4A` mask `0x20` (=bit5) — **перенесено**, годится как HYP для side-flag, не как имя слова `0x8032`.

**Вердикт:** не `PROVEN_EWS`, не `PROVEN_OTHER_NAME` → **STILL_STRUCT**.

---

## B — Speed words `0x1BBC0/C4/C8/CC`

| Пункт | Статус | Факт |
|---|---|---|
| 1 consumer | **PASS** | `@0x868210+` `EXTP #0x206` → phys `0x81BBC8/C4/CC/C0`; ветка `B17E.0` грузит siblings `BBCA/C6/CE/C2`; CMP/SUB vs `0xA4B6` |
| 2 единицы km/h | **FAIL** | FR: VVORH/VMAXMD как функция есть; шкала на 6901 не доказана |
| 3 опровержения | | адресный перенос E650 `0x81BC0x` / E5A0 `0x81B88x` **не** совпадает с `0x81BBC0` |

**Stock vs car:** high byte **+47** на четырёх словах (напр. `BBC0` 101→148, `BBC8` 103→150).

**Интерпретации (обе недоказаны на 6901):**

| шкала | stock ≈ | car ≈ | +47 hi |
|---|---|---|---|
| raw/256 | 101–103 km/h | 148–150 | +47 km/h |
| raw/128 (чужой `vfzg_uw_q0p00781`) | 203–206 / LR 67–70 | 297–300 | +94 km/h |

Семейство из 8 слов + LR-ветка **STRUCT**-похоже на VABSCH/VHYST/VMAXO/VVORH±LR; имена по смещению и km/h — **гипотеза/перенос**. `0xA4B6`≠доказанный `vfzg`.

**Вердикт:** **STILL_STRUCT** (не `PROVEN_units`).

---

## C — TLRHS `@0x1A753` scale

| Пункт | Статус | Факт |
|---|---|---|
| 1 consumer | **PASS** | `8750E6..EE`: `EXTP#206` `0x2753`→`A7EA` (phys `0x81A753`, stock `14`); `ADDB A7EA,ONES` @`8750D8` при `FD48.1` |
| 2 timebase 0.1 s | **FAIL** | роль FR ок; период задачи `87508A` не доказан |
| 3 опровержения | | «`FD48.1` = 100 ms tick» **отклонена** |

**Что ставит `FD48.1`:** реальный код `@0x870F28` `BSET FD48.1` (пара с clear `@0x870F4C`), caller `@0x86BF28`. Чужой A2L: `B_stend` @`FD48` mask `0x2` — уровень «конец старта», не квант времени. FR: TLRHS «as of end of start»; `LREB100MS` = условия в **100 ms cycle** (лист функции, не привязка к нашему entry).

**Следствие:** LSB = период вызова `0x87508A` × 1. Доказать 100 ms → 0.1 s/LSB на 6901 **не удалось** (указатель `8A508700` @`816DAC` без raster-ID). E650 `t100msxs` — перенос.

**Вердикт:** **STILL_STRUCT** (не `PROVEN_scale`).

---

## Итог

| # | Объект | Вердикт | В патч |
|---|---|---|---|
| A | `0x380032` EWS name | STILL_STRUCT | нет |
| B | `0x1BBCx` km/h | STILL_STRUCT | нет |
| C | TLRHS 0.1 s/LSB | STILL_STRUCT | нет |

JSON: `PROMOTION_REMAINING3_REPORT.json`.
