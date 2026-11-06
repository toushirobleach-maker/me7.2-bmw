# RAM `0x380032` / `0x8032` — EWS claim

**Вердикт: STILL_STRUCT** — байты ворот и OR-маска **доказаны кодом**; имя EWS/immobilizer release — **гипотеза** (не PROVEN).

Декодер: `10_review/20261106_deep_review/tools/review_decode.py`.  
BIN: `00_original/ME72_7532675_full_512KiB_…`; сток gate — SP-Daten G7533626. DPP2=`0x00E0` @`0x80BCEC` → `0x8032` = phys **`0x380032`**.

XDF-title при листинге: **`[STRUCT] Gate@0x5FFB2 forces 0xFF00→0x380032 (EWS name unproven)`**.

## Тройка

| # | Статус | Суть |
|---|---|---|
| 1 consumer | **PASS** | Writer stock @`0x85FFB2` + 3× `MOV 0x8032`; 7× `OR Rn,0x8032` → `CMP #FFFF` / `MOV F922|F92A` |
| 2 семантика EWS | **FAIL** | FR/DTC/live не именуют `0x380032`; чужой A2L `B_ews_ok` = **`0x383150`**, не этот адрес |
| 3 фальсификаторы | см. ниже | «не DPP2» / «только checksum» — DID_NOT_FIRE; «это B_ews_ok» — **FIRED** |

## Writer (сток vs дамп)

Сток @`0x85FFB2` (файл `0x5FFB2`):

```text
MOVBZ R4,0xB154 ; AND #1 ; JZ deny
MOVBZ R4,0xB17A ; AND #1 ; JZ deny
JB    FDDC.2 → deny
BCLR  PSW.6 / BMOV FD4A.5,PSW.6
deny: MOV 0x8032,ONES
pass: MOV R5,#0xFF00 ; MOV 0x8032,R5
```

Дамп: 13× `NOP` до `0x85FFCA` → всегда `BCLR PSW.6` → `0xFF00` в `0x8032`.  
Вызов: `CALLS 0x85,0xFFB2` @`0x86C05C`.

Ложные `32 80` в BIN: `0x8196E5` (BFLDL), `0x82E446` (JNB FD86.8) — **не** mem16 `0x8032`.

## Readers (все)

| CPU | RAW | Дальше |
|---|---|---|
| `830778` | `72F13280` OR R1 | `CMP #FFFF` → NZ на `83087A` |
| `83078E` | `72F23280` OR R2 | `MOV 0xF922,R2` |
| `830A3A` … `830D28` | то же OR R2 | `MOV 0xF922,R2` |
| `830E2E` | OR R2 | `MOV 0xF92A,R2` |

`0xFFFF` (ONES): OR всегда даёт `FFFF`, ветка CMP проходит, маска в F922/F92A = all-ones.  
`0xFF00`: high-byte принуждается; CMP проходит только если low уже `FF`.

**Не закрыто кодом:** mem16-чтений `F922`/`F92A` в 512 KiB **нет** → топливо / стартёр / CAN→EWS модуль из этого слова **не доказаны**.

## Почему не EWS PROVEN

1. E5A0 A2L: `B_ews_ok` «Freigabebit elektronische Wegfahrsperre» @**`0x383150`** (бит0) — **перенесено**; в A2L нет `0x380032`.
2. На 6901 mem16 `0xB150` (тот же phys при DPP2) живёт **отдельный** трафик; ворота смотрят `B154`/`B17A`/`FDDC.2`, пишут **`0x8032`**.
3. FR / DTC `0x27` / live `B_EWS_OK` не привязаны к `0x380032`.
4. Community «IMMO OFF» — не evidence_2.

## Фальсификаторы

1. «DPP2 ≠ 0xE0 ⇒ phys не 0x380032» → **DID_NOT_FIRE**.
2. «Только checksum/diag counter» → **DID_NOT_FIRE** (OR/CMP/F922 — путь управления).
3. «`0x8032` = B_ews_ok» → **FIRED** (чужой A2L + код на `0xB150` / другие писатели).
4. «NOP = IMMO OFF через fuel/starter/CAN-EWS» → **FIRED_AS_GAP** (нет потребителя F922 с именем EWS).

## Для PROVEN EWS нужно

Якорь 6901I41D: FR/DAMOS/live, что phys `0x380032` (или mailbox `F922`) = Freigabe Wegfahrsperre / DME↔EWS, **либо** код до документированного EWS-телеграмма.

До этого в патч/PROVEN-XDF под «EWS/IMMO OFF» не поднимать — только STRUCT gate bypass → `0xFF00`.
