# Promotion MISC — 6901I41D

Декодер: `review_decode.py` (калибровка `9F17`→`FD2E.9`, `D7400602`, `C2F43016`).  
BIN/сток: как в `PROMOTION_MISC_REPORT.json`. DPP0/1/2 = `0x204/205/0E0`.

**Счётчики:** PROVEN **0** · STILL_STRUCT **8** · STILL_HYP **2**  
Повышения: **B**, **I** (HYP→STRUCT). В PROVEN — никто.

| ID | Объект | Вердикт | Кратко |
|---|---|---|---|
| A | MSLBAS `0x19612` | STILL_HYP | 4× EXTP#206→`0x819612` **доказано кодом**; имя/SAP/ноль — нет 2-го источника |
| B | MSLUB `0x196A9`/`0x196B2` | STILL_STRUCT | Кривая 08+8+8 + ptr `0206:16A9` **доказано**; FR MSLUB=f(ub) тянет STRUCT; UBF/`8C96` и zero-off ≠ PROVEN |
| C | CWDAGR `0x11FC9`→`FDC0.4` | STILL_HYP | Транспорт DPP0 **доказано**; AGR-смысл/`CDAGR` FR не привязан к этому байту |
| D | Thermo A `0x19B80`/`0x19B8D` | STILL_STRUCT | 6×5 + `0x85B9DE` **доказано**; KFETRD/°C — перенос |
| E | Thermo B `0x19BB2`/`0x19BBF` | STILL_STRUCT | 6×5/30 B + `0x85B9FE`; старый 6×7/42 B **опровергнут** |
| F | Fan `0x1A575`/`0x1A57C` | STILL_STRUCT | hdr07 + `0x866FF6` **доказано**; TAMLTKA/формула — перенос |
| G | TLRHS `0x1A753` timebase | STILL_STRUCT | Reload→`A7EA` + роль FR **ок**; **0.1 s/LSB не доказан** (период задачи / `FD48.1`) |
| H | Gate `0x5FFB2` / `0x380032` | STILL_STRUCT | NOP/запись `0xFF00` и phys DPP2 **доказано**; читатели `OR …,0x8032` @`0x830778+`; имя EWS/IMMO — **гипотеза** |
| I | Speed `0x1BBC0/C4/C8/CC` | STILL_STRUCT | EXTP#206 loads @`0x868210+` **доказано**; km/h/Vmax — нет |
| J | KFZWOP/KFZW1 | STILL_STRUCT | Прямого consumer на 6901 **нет**; размеры — A2L другого SW |

## Доказательная выжимка

### A — STILL_HYP
1. `849C7A/CAE`, `84BEE2`, `84BF8C`: `D7 40 06 02` + `F3 xx 12 16` → `0x819612`.
2. В FR SLS есть MSLUB, не MSLBAS; live/DTC ярлыка нет.
3. Фальсификатор «это кусок MSLUB» не сработал (другой адрес/форма) — имени не даёт.

### B — STILL_STRUCT (↑ с HYP)
1. `84C7EA`: `R12=#16A9`, `R13=#206`, `R14←8C96`, `CALLS B524`.
2. FR: MSLUB = KL по UBF; рядом код сравнивает `8C96` с калибровками у `0x196CB`.
3. Заголовок `08`, значения с `+9`; «патчить с заголовка» опровергается. Имя/zero-off до PROVEN не дотягивают (`8A0B`≠доказанный UBF).

### C — STILL_HYP
1. `86B5DE`: `MOVB 0x1FC9; ANDB #1; BMOV FDC0.4` при DPP0→`0x811FC9`.
2. FR `CDAGR`/`SY AGR` ≠ доказательство этого кодворда.
3. Bitoff `0x60`→`FDC0` подтверждён; семантика AGR — нет.

### D/E/F — STILL_STRUCT
Форма и far-pointer consumers (`B704`/`B524`, page `206`) **доказаны кодом**. Имена/единицы/88C — **перенесено**. У E фальсификатор 6×7 сработал: в BIN лежит `05 06`.

### G — STILL_STRUCT
`8750EA` грузит `0x81A753`→`A7EA`; `ADDB A7EA,ONES` при `FD48.1`. FR: TLRHS = delay hot-start. Масштаб 0.1 s — только перенос E650 / допущение 100 ms-слота без доказательства периода вызова на 6901.

### H — STILL_STRUCT
Сток @`0x85FFB2`: проверки `B154`/`B17A`/`FDDC.2` → `FD4A.5` → `MOV 0x8032,#0xFF00|ONES`. Phys `0x380032`. Читатели: `OR Rn,0x8032` затем `CMP #FFFF` / сборка в `F922` (`0x830778`, `0x83078E`, `0x830A3A`, `0x830B40`, …). EWS/IMMO — **гипотеза**.

### I — STILL_STRUCT (↑ с HYP)
Четыре слова читаются через EXTP#206 в `0x868210..240` и сравниваются с `A4B6`. Это пороги в коде (**STRUCT**). Подпись Vmax/км/ч — **гипотеза**.

### J — STILL_STRUCT
Поиск `MOV R12,#0220/#0BC2`, EXTP-окон и far-pointer `20 02 04 02` / `C2 0B 04 02` — пусто. Без consumer 6901 размеры/имена остаются переносом A2L.

## Не недоказанное закрывать
В патч/PROVEN из этого прохода **нечего** поднимать. STRUCT-форма B/D/E/F/I пригодна как структура; бизнес-имена и timebase TLRHS — нет.
