# Тесты без данных машины

`python3 -m unittest discover -s 08_tests -v`.

`fixtures.py` создаёт искусственную оболочку512 КиБ из profile/FF и тестовых байтов. В ней нет рабочего двигателя program, VIN/ISN/долговременных данных/калибровки реальной машины. BIN создаются только во временной директории и удаляются. Вставленный marker — часть искусственной модели, не рекомендация чинить stock неизвестными байтами.

Проверяются38 checksum, повреждение сумм/данных/указателей, передача/ACK/timeout, exact UIF-reference, full postcycle comparison, offline gates, relocation без research, synthetic OEM vectors, C166-векторы, XDF regeneration, sparse SP-Daten parser/overlay и public-tree policy. Код аппаратных ветвей подменяется FakeECU.

Raw vehicle trials не требуются. [Последний результат](../04_reports/TEST_RESULTS_CURRENT.txt).
