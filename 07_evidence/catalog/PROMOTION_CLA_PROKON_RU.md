# Продвижение CLA / PROKON → PROVEN (6901I41D)

Машинный отчёт: `PROMOTION_CLA_PROKON_REPORT.json`.

**Итог: PROVEN 17 / не PROVEN 0.**

BIN: `00_original/ME72_7532675_full_512KiB_20261105T164440Z.bin`  
Stock: `…/ME72_7532675_6901I41D_stock_from_G7533626_512KiB.bin`  
Декодер: `10_review/20261106_deep_review/tools/review_decode.py`  
DPP0=0x204, DPP1=0x205, DPP2=0x0E0.

Контракт на каждый байт: (1) consumer + EXTP/DPP + сырые байты, (2) независимая семантика (FR / таблица DFPM→DTC `0x153F2` / live / свой код ДМЕ), (3) заранее заявленный фальсификатор проверен и не сработал.

---

## Сводка

| # | Имя | Addr | Stock | Verdict |
|---|-----|------|-------|---------|
| 1 | CWKONLS | 0x1A5EA | 33 | **PROVEN** |
| 2 | CWKONABG | 0x1A5E9 | 05 (dump 00) | **PROVEN** |
| 3 | SAP passport | 0x1A5EC | 01 | **PROVEN** |
| 4 | CWDKAT | 0x11FD3 | 01 | **PROVEN** |
| 5 | ESKONF[3] SLP | 0x11B2F | F3 | **PROVEN** |
| 6 | ESKONF[5] SLV | 0x11B31 | F0 | **PROVEN** |
| 7 | CLALSH | 0x1162F | 25 | **PROVEN** |
| 8 | CLALSH2 | 0x11630 | 25 | **PROVEN** |
| 9 | CLALASH | 0x11624 | 25 | **PROVEN** |
| 10 | CLALASH2 | 0x11625 | 25 | **PROVEN** |
| 11 | CLAHSH | 0x11613 | 25 | **PROVEN** |
| 12 | CLAHSH2 | 0x11614 | 25 | **PROVEN** |
| 13 | CLASLPE | 0x1164C | 25 | **PROVEN** |
| 14 | CLASLVE | 0x11651 | 25 | **PROVEN** |
| 15 | CLAHSV | 0x11615 | 21 (dump 00) | **PROVEN** |
| 16 | CLAHSV2 | 0x11616 | 21 (dump 00) | **PROVEN** |
| 17 | DTEVE | 0x1165B | 25 | **PROVEN** |

---

## PROKON / codewords

### CWKONLS @ 0x1A5EA — PROVEN
- **Consumer:** `86B506` `D7 40 06 02` / `F3 F8 EA 25` → phys `0x81A5EA`; биты 0/1/4/5 → `FD50.12/.10/.13/.11`.
- **Семантика:** FR GGLSV/GGLSH + PROKON p.884: Bit0/1/4/5 = B_lsv/B_lsh/B_lsv2/B_lsh2; сумма «все 4» = 0x33.
- **Фальсификатор:** «это CWKONABG» → bit0 шёл бы в FDC0.7; факт: FDC0.7 ← 0x1A5E9. Не сработал.

### CWKONABG @ 0x1A5E9 — PROVEN
- **Consumer:** `86B570` EXTP#206 `MOVB 0x25E9` → `0x81A5E9`; bit0/1/2 → FDC0.7/.8/.13.
- **Семантика:** FR: CWKONABG → B_katfz / B_kath. В **этом** SW bit2 → FDC0.13 (B_uhrrmin), не B_slsfz.
- **Фальсификатор:** «bit2 = B_slsfz → FDC0.11» — FDC0.11 пишется из 0x1A5EC. Не сработал (community-модель отвергнута; адрес codeword подтверждён).

### SAP passport @ 0x1A5EC — PROVEN
- **Consumer:** `86B552` EXTP#206 `MOVB 0x25EC` → `0x81A5EC` bit0 → **FDC0.11**.
- **Семантика:** FR B_slsfz = SLS fitted; FDC0.11 гейтит SLS/KH-пути (JB/JNB). Источник калибровки в 6901 — отдельный байт, не CWKONABG.2.
- **Фальсификатор:** «паспорт = CWKONABG» → цели битов разные. Не сработал.

### CWDKAT @ 0x11FD3 — PROVEN
- **Consumer:** `86B4B6` `F3 F8 D3 1F` при DPP0=0x204 → `0x811FD3`; bit0 ∧ ¬FDD8.7 → OR `0x904A,#0x0100`.
- **Семантика:** FR PROKON p.885: CWDKAT → B_cdkat (с B_nokatfz).
- **Фальсификатор:** «не скаляр / сосед 0x1FD1 тот же путь» — байт 01; сосед ведёт в 0x904C. Не сработал.

### ESKONF[3] SLP @ 0x11B2F — PROVEN
- **Consumer:** `85AAA6` `MOV R12,#3`; `85AAAA` грузит `0x815824[1]=0x0C`; `85AAB6` ORB в runtime ESKONF[3].
- **Семантика:** FR DECJ p.813: [3] bits3:2 = SLP; 11 = Diagnose inaktiv. Callback → idx 0x73 / B9CC → LROBD.
- **Фальсификатор:** «маска 0x03» — table[1]=0x0C; (F3⊕FF)=0x0C. Не сработал.

### ESKONF[5] SLV @ 0x11B31 — PROVEN
- **Consumer:** `85AABA` `MOV R12,#5`; маска `0x815824[0]=0x03`; ORB @ `85AACA`.
- **Семантика:** FR p.813: [5] правая пара = SLV; 11 = inaktiv. → idx 0x78 / B9D6 → LROBD.
- **Фальсификатор:** «SLV в bits3:2» — маска была бы 0x0C; факт 0x03. Не сработал.

---

## CLA / DFPM классы

Общий путь: fault-site `MOV R12,#idx` → `CALLS 0x82,0x96E2` (DFPM) → класс `MOVB [R4+#0x15D9]` @ `82938A` (DPP0 → база `0x8115D9`). DTC: `0x153F2 + 2·idx` (16-bit LE).

| Имя | Addr | idx | DTC | Consumer | Live/FR |
|-----|------|-----|-----|----------|---------|
| CLALSH | 0x1162F | 56 | 0x0C hinter Kat | 857E02 | A0 |
| CLALSH2 | 0x11630 | 57 | 0x14 Bank2 | 857E10 | A0 |
| CLALASH | 0x11624 | 4B | 0x11 Alterung | 82C38E | FORTTEXTE |
| CLALASH2 | 0x11625 | 4C | 0x17 Alterung B2 | 82C39C | FORTTEXTE |
| CLAHSH | 0x11613 | 3A | 0x0E Heizung hinter | 854D6C | A0 |
| CLAHSH2 | 0x11614 | 3B | 0x04 Heizung hinter B2 | 854E46 | A0 |
| CLASLPE | 0x1164C | 73 | 0x54 SLP Endstufe | 85B592 | A0; B9CC→LROBD |
| CLASLVE | 0x11651 | 78 | 0x55 SLV Endstufe | 85B618 | A0; B9D6→LROBD |
| CLAHSV | 0x11615 | 3C | 0x0D Heizung vor | 854BB8 | FR DHLS |
| CLAHSV2 | 0x11616 | 3D | 0x05 Heizung vor B2 | 854C92 | FR DHLS |
| DTEVE | 0x1165B | 82 | 0x62 TEV Endstufe | 85B724 | A0 |

**Фальсификатор (общий для CLA):** соседний индекс даёт другой DTC / другой адрес класса — проверено для каждого; не сработал.

**DTEVE отдельно:** старый адрес `0x11611` = idx 0x38 → DTC **0xE2**, не 0x62. Правильный класс — **0x1165B**.

---

## Явные ограничения

- Class **00** = подавление **регистрации** в fault memory, не снятие монитора/readiness.
- Не форсить `B_lr`; LROBD для SAP — через B9CC/B9D6 + ESKONF inactive, не через CLA alone.
- CWKONABG bit2 в 6901 = uhrrmin-путь, не SAP.
- Этот документ продвигает **определения** в PROVEN; flash-бандлы по-прежнему требуют checksum и отдельного whitelist.
