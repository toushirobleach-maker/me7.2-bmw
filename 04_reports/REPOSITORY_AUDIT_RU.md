# Аудит публичного состава

Проверяются632 записи каталога,155-элементный PROVEN-срез/CSV и оба XDF. Full XDF552 объекта, narrow snapshot56. Метаданные status_counts исправлены по actual records; данные символов и XML-байты сохранены.

Включён один stock-reconstruction BIN по фиксированному SHA, с известным результатом37/38 и отсутствующим marker. Донорские/модифицированные изображения и журналы передачи удалены. Byte-spot-checks по stock подтверждают только присутствие конкретных инструкций, не всю семантику.

[REPOSITORY_AUDIT_CURRENT.json](REPOSITORY_AUDIT_CURRENT.json) содержит текущие результаты. В отличие от прежней проверки одних DAMOS-basename, [reference audit](REPORT_REFERENCES_RU.md) сканирует ссылки в самих отчётах и явно разделяет private exclusions, local assets, примеры и реально отсутствующие research dependencies.

Синтетические тесты не заменяют аппаратное испытание stock restore. Подготовка публичной версии выполняется без обращения к автомобилю. Полный FR PDF и ссылки на него отсутствуют.
