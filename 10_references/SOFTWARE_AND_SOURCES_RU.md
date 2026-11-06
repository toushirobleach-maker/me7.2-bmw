# Софт и исходники для BMW ME7.2 и нашего 6901I41D

Проверено 05.11.2026 по страницам авторов и сохранённым commit snapshots. Репозиторий с исходниками не означает, что он умеет BMW ME7.2 или проверен на этом образе. Доступность на Mac ARM разделена на обработку файлов и реальный обмен с DME.

## Редакторы и определения

| Проект | Что даёт | Применимость / Mac ARM |
|---|---|---|
| [BMW-XDFs](https://github.com/MotorMouth93/BMW-XDFs) | XDF 6901/6902: 232 scalars, 102 tables, 4 functions, 10 patches; старые A2L/DAMOS | Лучший найденный публичный старт именно для 6901, но много выявленных дефектов. Нет обнаруженной общей лицензии на все вложенные материалы |
| [sostisoft ecu-definitions](https://github.com/sostisoft/ecu-definitions/tree/d5899b85e7b97e15b46990d574c44e9dbb525885/BMW/ME7.2_M62TU_V8) | 6901/6902, injector resizing, более объёмные 05A0/0650 XDF под full/partial | Сохранено. Не найден полный 6901I41D A2L. У зеркала 6901 warning CWDMTL удалён без изменения адреса |
| [TunerPro](https://www.tunerpro.net/downloadApp.htm) | Windows XDF-редактор | Нативный Mac ARM не подтверждён. Можно исследовать в Windows-среде, но точность XDF и ME7.2 checksum остаются отдельной задачей. Исходники приложения не найдены |
| [RomRaider](https://github.com/RomRaider/RomRaider) | Java редактор, GPL-2.0; полный исходный код сохранён | Файловый редактор можно рассматривать для Mac/JVM; конкретная установка не тестировалась. Готового проверенного 6901I41D XML не найдено |
| [Me72-XML surviving fork](https://github.com/handmade0octopus/Me72-XML) | Публичный draft переноса XDF в RomRaider; me72.xml и примеры 5A01 | Исходный zarboz URL не доступен, fork сохранён. В XML черновой base/5A01, не готовый 6901: повторяется xmlid 430056, а один MLOFS address автор прямо пометил invalid offset for testing. Лицензионного файла не обнаружено |
| [tunex](https://github.com/emdzej/tunex) | Локальный браузерный XDF+BIN редактор, TypeScript/Svelte; исходники сохранены | Подходит как основа Mac-инструмента, без загрузки BIN на сервер при локальном использовании. PolyForm Noncommercial 1.0, не permissive open source; 3D-renderer и некоторые детали ещё не завершены. BMW checksum не добавляет |
| [Universal Exporter](https://github.com/KingAiCodeForge/TunerPro-XDF-BIN-Universal-Exporter) | Python экспорт XDF+BIN в JSON/MD/TXT и другие форматы; MIT | Полезен для офлайн-анализа на Mac. Авторы помечают guarded release candidate; тесты на синтетике не доказывают семантику всех настоящих XDF. Исходники сохранены |
| [CLI map editor](https://github.com/KingAiCodeForge/tunerpro-xdf-bin-cli-map-editor) | Python детерминированные правки BIN по XDF, журнал изменений; MIT | Основа для собственной утилиты после проверки definition. Не ME7.2 flasher и не квалифицированный BMW checksum-корректор. Guarded RC; код сохранён, правки нашего BIN им не выполнялись |
| [Fabio ME7.2 Config Tool v0.53](https://fabiosoftware.net/product/bmw-me7-2-config-tool/) | Коммерческий редактор; автор прямо перечисляет 6901/6902, full512/partial64, конфигурации и карты | Требует .NET4.8+, лицензия 1 PC. **Автор прямо пишет No Checksum Correction.** Исходники не опубликованы/не найдены; сохранена страница, приложение не приобреталось |
| [BimmerEditor](https://www.bmweditor.com/Home/Title) | Коммерческий ME7.2 модуль, карты/DTC; автор объявлял встроенный flasher | Нативный Mac ARM не подтверждён. Наличие модуля не гарантирует правильные карты E53-variant; source не найден. Страница доступна через web lookup, прямое сохранение давало timeout; заметка сохранена |
| [WinOLS](https://www.evc.de/en/product/ols/software/) | Коммерческий поиск карт, сравнение версий, импорт через модули, checksum plugins | Полезен для DAMOS/A2L/OLS, но точного 6901 DAMOS у нас нет. Нельзя считать любой checksum plugin подходящим BMW. Source не найден, страница сохранена; приложение не установлено |

Прямая ссылка Fabio на online editor существует, но ваш дамп туда не передавался. Для офлайн-исследования удобнее собственный локальный парсер/экспорт или локальная сборка публичного редактора.

## Что реально есть в patchlist
+
+Сохранены 10 патчей внутри 6901/6902 XDF и 4 patch-объекта MS4X v0.1, плюс 29 таблиц/8 констант MS4X. Вводная страница упоминает Launch Control, но реализация LC отсутствует в скачанном v0.1. Checksum Bypass на странице прямо отмечен как not ready yet. Документация MS4X описывает bootmode/JMGarage как требование тогдашнего сценария; это не доказательство совместимости этого старого загрузчика с Mac или нашим OBD-сеансом. Сами исходники реализованного LC/NLS/flatshift именно для 6901I41D в сохранённых проектах не найдены; перенос VAG-патчей не проверен.
+
+## Чтение, запись, диагностика

| Проект | Что подтверждено | Ограничение |
|---|---|---|
| Наш Mac read-only reader | Реальный full512 read именно этого DME через FTDI K+DCAN и macOS ARM; исходники в `00_original/ME72_Mac_readonly_source.zip` | Чтение проверено, запись/erase/security/programming не реализованы и не тестировались |
| [BTT ME7.2 Quickflash](https://www.bimmertuningtools.com/product/me72-quickflash/) | Автор заявляет full/partial read-write, автоматические checksum, Windows7+, FT232RL | Коммерческий закрытый продукт; текущая страница v3.26 сохранена. Наш Mac-сценарий не его нативная платформа |
| BimmerFlasher Android | Автор в 2021 объявлял read/write calibration ME7.2 с checksum, OTG/K-Line | Это приложение Android, не Mac. В новости 2023 ME7.2 исключён из добавленных compatibility checks. Старые промо-цены не считаются текущей ценой |
| [NefMoto](https://github.com/NefMoto/NefMotoOpenSource) | GPL-3.0 C#/FTDI/KWP-исходники; полезны для изучения протокола и смены скорости | Основная цель VAG; не готовый проверенный BMW ME7.2 writer. BMW KWP2000* имеет свои кадры/сеансы |
| [C167BootTool](https://github.com/EcuProg7/C167BootTool) | GPL-3.0, bootstrap C167/ST10, Flash/ROM/EEPROM операции по описанию автора | Boot mode — отдельный аппаратный сценарий, не обещание работы через OBD K+DCAN. Нельзя автоматически считать его поддержкой нашего ECU/flash chip |
| SGBD ME7FLASH / ME72KWP1 | Сохранены текстовые описания jobs для Flash и диагностики из EDIABAS | Документированный job не равен готовой реализации протокола; оригинальные BMW PRG/пакеты не подменяются этим текстом |
| [SP-Daten Firmware Extractor](https://github.com/anglezarkk/BMW_WinKFP_Firmware_Extractor) | Python извлечение/конвертация .0DA в Intel HEX, разбор SW; код сохранён | Не читает и не прошивает DME. README демонстрирует 5A01. Без файла нужного варианта не создаст заводской эталон 6901I41D. Нет LICENSE в snapshot |

Подтверждённая наша быстрая сессия: при 9600 8E1 запрос `10 86 87`, ответ `50 86`, затем переключение host на 124800 8E1. Возврат согласовывался `10 86 10`, затем 9600 и normal session. Полный транспорт и ограничения сохранены в Mac reading notes. Эти сведения документируют состоявшийся опыт; текущие офлайн-скрипты не отправляют никаких запросов.

## Checksum и анализ кода

| Проект | Реальная польза | Совместимость |
|---|---|---|
| [ME7Sum](https://github.com/nyetlabs/ME7Sum) | BSD C source; схемы ROMSYS/CRC/multipoint, в свежем snapshot есть Porsche ME7.2 | Авторы заявляют VAG ME7.1/7.5 и Porsche986/996 ME7.2, **не BMW**. В BMW найден другой адрес первой MP-таблицы. Коррекцию по hardcoded Porsche offsets не применяли |
| Наш checksum audit | Все найденные суммы/инверсии и calibration CRC вашего образа реально пересчитаны | Python read-only, только проверка, без функции коррекции. Это результат анализа этого образа, не универсальная поддержка всех BMW ME7.2 |
| [hn/c166-dis](https://github.com/hn/c166-dis) | Оригинальный Perl C166 decoder/table files, GPL-3.0 по исходнику | Линейный дизассемблер, не полный decompiler/автоматический map finder |
| [Python/IDA C166 decoder](https://github.com/ayyo42069/c166-disasm-plugin) | GPL-3.0 port, работает standalone на Python; использован на выбранных участках дампа | Несколько operands INCOMPLETE; не скрываем их. IDA для standalone не требуется |
| [Ghidra C166 Haldex](https://github.com/TheFlashBold/ghidra-c166-haldex) | Экспериментальный SLEIGH processor module, DPP/EXTP/EXTS, исходники сохранены | Спецификация Tasking/r15 для Haldex/XC166 может не совпасть с ABI Bosch. Не устанавливался и не тестировался на ME7.2; LICENSE не обнаружен |

## Практический выбор для этого Mac

Для текущего разбора уже есть работающий локальный путь: наш Python-анализ → JSON/Markdown → самостоятельный C166 decoder и проверка checksum. Для редактирования разумно сначала подготовить отдельное проверенное определение **6901I41D**, исправив типы и размеры, а не открыть произвольный 6901 XDF и считать все 338 объектов точными.

Если нужен готовый коммерческий редактор, наиболее явное заявление поддержки 6901/6902 найдено у Fabio; отсутствие checksum correction у него прямо оговорено. TunerPro с качественным XDF и WinOLS с правильными символами также возможны, но нативный Mac ARM не подтверждён. Браузерные/Python/Java исходники позволяют построить локальный редактор; пока не найден готовый публичный проект, одновременно проверенный как BMW ME7.2 writer + checksum correction + точные 6901I41D definitions на Mac ARM.

## Хранение и лицензии

Все архивы `05_source_archives` закреплены commit SHA, распакованные версии лежат в `05_sources`. Лицензии исходных проектов не отменяют прав Bosch/BMW и авторов вложенных определений. «Нет LICENSE» означает отсутствие найденного явного разрешения на распространение/производные работы, а не public domain. Коммерческие установщики, ключи и сторонние дампы для заливки не покупались. Ваш исходный BIN не опубликован и не загружен во внешние сервисы.
