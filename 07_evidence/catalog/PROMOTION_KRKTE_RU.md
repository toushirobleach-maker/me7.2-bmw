# KRKTE → PROVEN

**Адрес:** `0x19CC4` → CPU `0x819CC4` (стр. `0x206`)  
**Stock raw:** `0x56` (86) → **KRKTE = 0.183467 ms/%** (`rkti_sy`, `/468.75`)  
**Qstat (FR):** ≈ **150.6 g/min** (n-heptane), Vh=4.398/8 дм³ → класс ~220 cc/min.

Декодер: `review_decode.py` (EXTP phys на `C2F4C41C` → `0x819CC4`).

## 1. Consumer (доказано кодом)

```
803734 D7400602   EXTP     #0x206,#1
803738 C2F4C41C   MOVBZ    R4,0x1CC4 ; phys=0x819CC4
80373C 5C84       SHL      R4,#8
80373E F6F42EA2   MOV      0xA22E,R4
```

Тот же байт → `0xA230`. Адаптация: `CALLS 0x6D7A` (IROM), clamp к **cal±2** (`0x85E6F2`).

## 2. Семантика (независимо)

- FR AES: `ti = rk * frkte + tvu`; `frkte` включает перевод через **KRKTE**.
- FR APP: `KRKTE = 50.2624 * Vh / Qstat`.
- E5A0: `KRKTE @0x819BC4`, сосед `CWPKAPP @0x819BC3` → 6901 `0x19CC3`/`0x19CC4` (оба через `EXTP #206`).

## 3. Falsifier — DID_NOT_FIRE

| Условие | Проверка |
|---|---|
| page 0x205 | phys `0x815CC4` ≠ cal |
| это TATELL (E5A0+1) | consumer на `0x19CC4` + SHL#8 ±2 |
| старый catalog `0x19CD3` | loads только `0x1CC4`; `[0x19CD3]=00` |

## Не доказано этим отчётом

Прямой `MULU rk,FRKTE` в external flash не найден (вероятно IROM/`RKTI`); для PROVEN константы достаточно consumer+FR+соседний якорь.
