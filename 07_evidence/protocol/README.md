# Синтетические OEM-векторы

`synthetic_oem_vectors.json` получен офлайн исполнением оригинальных BMW10EK726 jobs над искусственными данными:

- 516 payloads: erase,download,512×128 transfer,exit,native checksum;
- transfer pattern `(37*i+11)&255`, не firmware;
- 39 искусственных seed/key векторов, nonce3..41;
- ни одного реального security-ответа/ECU-идентификатора/кал-блока машины.

Генератор — `09_re_tools/factory_public_fixtures.cjs`; для самостоятельного повторения нужны собственный10EK726.prg и локально установленные @emdzej parser/interpreter (`--module-root`). Эти сторонние входы в Git не включены. Векторы подтверждают формат, а не пригодность target image для двигателя.

Полные прежние .prg/.ipo/.asm и real-target OEM_ORACLE не распространяются. Сохранившиеся короткие loader/status листинги являются исследовательскими snippets; ссылки на исключённые материалы перечисляет reference audit.
