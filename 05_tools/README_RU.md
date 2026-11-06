# Инструменты ME7.2

Основные независимые entry point: `read.py`, `write.py`, `verify.py`, `checksums.py`. [Полная инструкция](../03_docs/TOOLS_RU.md).

| Модуль me72 | Ответственность |
| --- | --- |
| images.py + profile JSON | Размер, EPK, указатели/границы, cal-only diff |
| checksum.py | 38 проверок и отдельный исправляющий алгоритм |
| transport.py | B8/XOR, эхо, фрагменты, таймауты, журнал до TX |
| protocol.py | OEM запросы, seed/key, сессии и условия |
| reader.py | Полное чтение + повторные проверки + восстановление сессии |
| writer.py | Ограниченная state machine erase/transfer/readback/native checksum |
| diagnostics.py | DTC, λ-группы и известные RAM-слова |
| files.py | Уникальные и защищённые от перезаписи артефакты |
| cli.py | Связывает операции; `--execute` — единственный путь к порту |

Не импортировать legacy snapshots вместо этой библиотеки. Не добавлять «raw SID» CLI, произвольный erase, универсальный `--force`, повтор передачи по таймауту или маску игнорирования readback. Новый профиль/образ другой сборки требует отдельной проверки.

`prepare_stock.py` добавляет только офлайн-подготовку stock-cal overlay; выбор машины, coding/EWS и полная512 запись не автоматизируются. См.03_docs/STOCK_FLASHING_RU.md.
