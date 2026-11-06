# Инструменты исследования

Работают офлайн и не требуют соседнего research-дерева.

## Поиск символов

```sh
python3 09_re_tools/query.py KRKTE --json
python3 09_re_tools/query.py KFZW
python3 09_re_tools/query.py --status PROVEN
```

## Исправленный C166-декодер

```sh
python3 09_re_tools/decode.py local/my_verified_512KiB.bin --start 0x87582C --end 0x87584E
```

Адреса — CPU, диапазон внешней flash. `--output новый_файл.asm` сохраняет отдельный листинг. `review_decode.py` исправляет проверенные bitoff/EXTP/MOVBZ формы поверх сохранённого GPL-3.0 декодера в `decoder/`. Это линейный листинг; он не доказывает достижимость, не строит полный control flow и не отслеживает произвольный DPP/EXTR контекст. Таблицы и лицензия включены.

## Генерация XDF

```sh
python3 09_re_tools/generate_xdf.py --output runs/xdf_build/ME72_from_damos.xdf
```

Каталог/manifest по умолчанию берутся из текущих `01_damos/` / `02_xdf/`; можно задать `--catalog` / `--manifest`. Команда не меняет исходный каталог и не перезаписывает существующие XDF/отчёт. Алгоритм исходного генератора сохранён, CLI стал явно задавать выход. Генерация не повышает статусы доказанности.

## Аудит комплекта

```sh
python3 09_re_tools/audit_repo.py --output runs/audit_build.json
```

Проверяет весь каталог, CSV, XDF, известные образы, буквальные consumer-bytes и наличие evidence-файлов. Оригинальные pipeline-скрипты архивированы в `07_evidence/source_snapshots/damos_pipeline/`; это материалы истории с прежними путями, не активный воспроизводимый pipeline новой упаковки.

## Целостность файлов репозитория

`python3 09_re_tools/manifest.py verify` сверяет все файлы, перечисленные в корневом MANIFEST_SHA256.json. Git, виртуальная среда, runs/workspace и Python-кеши исключены. Для нового снимка: `python3 09_re_tools/manifest.py create --file runs/new_manifest.json`; существующий файл не заменяется. Манифест подтверждает байты перечисленных файлов, не их подлинность или отсутствие дополнительных файлов.

## Публичная версия

`check_public_tree.py` проверяет рабочее дерево. `audit_report_references.py` классифицирует все ссылки из отчётов, включая отсутствующие/намеренно исключённые. `import_local_assets.py` переносит собственные материалы в gitignored local/. `factory_public_fixtures.cjs` регенерирует только искусственные векторы при наличии собственных factory jobs и npm dependencies. Полного FR PDF и ссылок на него нет.
