# Полный индекс FR и применимость к 6901I41D

## Что построено

| Артефакт | |
|---|---|
| PDF | `01_documentation/.../Funktionsramen_full/BMW Me7_2_English_Funktionsramen.pdf` (**1043** стр.) |
| Текст | `07_analysis/fr_full_index/full_text.txt`, `pages.jsonl` |
| Индекс | `FR_FULL_INDEX.json`, `symbol_pages.json` |
| Экстрактор | pypdf, 0 пустых страниц |

Старый `07_analysis/FR_contents_index.json` был с **20-стр. превью** — считать устаревшим TOC; пользоваться этим индексом.

## Насколько FR «наш»

Заголовок Vivace на каждой странице:

> **BMW 8-Zyl ME-7.2 M62LEV 3,5l und 4,4 l, variable Einl.-NW**  
> Project дата ~19.04.2000, Markus Riemann

Наша цель: **ME7.2 / M62B44LEV / 7532675 / EPK 6901I41D** (Freigabe ~2003).

| | Оценка |
|---|---|
| Семейство ECU/двигатель | **высокое** совпадение |
| Имена функций/калибровок | словарь **применим** как evidence_2 |
| Абсолютные адреса flash 6901 | **нет в FR** — только код/DAMOS этой сборки |
| Ревизия софта | FR 2000 ≠ обязательно байт-в-байт 6901I41D |

**Вывод:** FR — правильный Funktionsrahmen для M62LEV ME7.2, не «чужой мотор». Это не замена consumer+falsifier на BIN 6901.

## Что индекс дал по нашим дырам

### MSLBAS — раньше «нет во FR»

**Есть.** PDF p.298, секция **DSLSLR**:

> `MSLBAS FW Ini.- secondary air mass`

Также p.295 (диаграмма FMSLAMX/MSLBAS), p.961 (каталог → DSLSLR).

Стык с кодом 6901: `0x19612` / `0x819612` сидит в AF2C/AF2D как **init/seed** вторичного воздуха — согласуется с «Ini.- secondary air mass», не с порогом MSLUB.

→ Имя **MSLBAS** можно считать **доказанным** (код + FR), не community XDF.

### CWDAGR vs CDAGR

Строки **`CWDAGR` во FR нет**. Есть **`CDAGR`** (PROKON p.885–887):

> `CDAGR FW code word DAGR inactiv (EURO-coding)` → `B_cdagr`

На 6901: `MOVB 0x1FC9; ANDB #1; BMOV FDC0.4` @`0x86B5DE` (DPP0→`0x811FC9`).

Community-имя `CWDAGR` = скорее **`CDAGR`**. Смысл: евро-кодворд деактивации **DAGR**, не обязательно «выключить физический EGR актуатор» одной кнопкой.

→ Переименовать в XDF в **CDAGR**; PROVEN как codeword bit→флаг; эффект «EGR off» оставить осторожным.

### KFZWOP / KFZW1

FR **MDBAS** p.50–51: `KFZWOP` = optimum ignition nmot×rl.  
FR **ZWGRU** p.208–209: `KFZW1` = part-load ignition map variant 1.

Семантика карт **есть**. Consumer адреса `0x10220` / `0x10BC2` на 6901 **по-прежнему не найден** → адрес остаётся STRUCT.

### KFETRD / KFETRT / TAMLTKA

FR **ETR** p.688–689: электрический термостат; `KFETRD` = setpoint from dk×vfzg; `KFETRT` from tans×vfzg; min-select.  
FR **MLS** p.695–697: `TAMLTKA` = E-fan PWM request from radiator outlet temp.

Совпадает с нашими блоками `0x19B8D` / `0x19BBF` / `0x1A575` (форма уже по коду). Имена/роль → поднимаем до PROVEN (единицы °C/% по-прежнему формула ME7 temp).

### EWS / `0x380032`

Во FR: разъём **EWS immobilizer** (STECK p.716), `SY WFS` immobilizer via CAN/K-line (PROKON p.888), `B ECULOCK` locking request (AEVAB p.197), EEDAT «EWS-Werte» (p.943).

**Нет** привязки к RAM `0x380032` / `F922`.  
`immobilized turbine` p.62 — про гидротрансформатор, не иммо.

→ EWS как система в проекте есть; наш gate-NOP **не** доказан как EWS release одним FR.

### TLRHS

FR LREB p.329/335: blocking time LC hot-start; триггеры TASHS/TMSHS. Масштаб LSB **не указан** в найденных абзацах → timebase STRUCT.

## Практические следствия для XDF

| Было | Стало после индекса |
|---|---|
| MSLBAS HYP/STRUCT без имени | **PROVEN MSLBAS** (Ini. secondary air mass) |
| CWDAGR HYP | **PROVEN CDAGR** (EURO DAGR inactiv), title fix |
| Thermo/fan STRUCT имена | **PROVEN KFETRD/KFETRT/TAMLTKA** роли |
| KFZW / EWS gate | STRUCT (семантика FR ≠ адрес/бизнес на 6901) |
| SAP OFF бандл | может стать **PROVEN**, если MSLBAS теперь PROVEN |

## Как пользоваться индексом

```bash
# страницы символа
python3 -c "import json; d=json.load(open('07_analysis/fr_full_index/symbol_pages.json')); print(d.get('MSLBAS'))"

# полный текст
rg -n 'MSLBAS' 07_analysis/fr_full_index/full_text.txt
```

Поиск по `FR_FULL_INDEX.json` → `query_hits` / `critical_snippets` / `family_symbol_pages`.
