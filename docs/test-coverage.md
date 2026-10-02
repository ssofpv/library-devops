\# Матрица функционального покрытия



Основание: функциональные требования FR-01–FR-09 из ТЗ

веб-приложения «Библиотека» к лабораторной работе №1.



\## Методика расчёта



Функциональное покрытие оценивается по требованиям ТЗ.

Количество тестов и процент покрытия строк кода не являются

процентом функционального покрытия.



Для подтверждения порога 40% используется консервативная

нижняя оценка: учитываются четыре требования, для которых

тесты непосредственно проверяют все основные сценарии,

перечисленные в соответствующей строке ТЗ:

FR-04, FR-05, FR-06 и FR-09.



Минимальное подтверждённое функциональное покрытие:

4 / 9 × 100% = 44,4%.



Остальные требования также проверяются тестами, указанными

ниже, но не включены в эту нижнюю оценку. Такая оценка

не означает, что остальные функции не тестируются,

и не утверждает полное покрытие всех возможных вариантов.



\## Требования и тесты



В таблице указаны классы и конкретные методы тестов.

Названия методов приведены без префикса класса.



| Требование | Файл и класс | Проверяемые сценарии и методы |

|---|---|---|

| FR-01. Авторы | `catalog/tests.py`, `AuthorAPITests`, `AuthorDeletionUnitTests` | Создание: `test\_create\_author`; список: `test\_list\_authors`; отдельная запись: `test\_get\_author`; изменение: `test\_update\_author`; удаление без книг: `test\_delete\_author\_without\_books`; запрет удаления с книгами: `test\_cannot\_delete\_author\_with\_books`. Unit-тесты отдельно проверяют обе ветви правила удаления. |

| FR-02. Книги | `catalog/test\_books\_api.py`, `BookAPITests` | Создание с авторами: `test\_create\_book\_with\_authors`; создание без необязательных полей: `test\_create\_book\_without\_optional\_fields`; просмотр: `test\_list\_books`, `test\_get\_book`; изменение авторов: `test\_update\_book\_and\_replace\_authors`; удаление с сохранением автора: `test\_delete\_book\_preserves\_author`. |

| FR-03. Филиалы | `inventory/tests.py`, `BranchAPITests`; `inventory/test\_copies\_api.py`, `CopyAPITests` | Создание: `test\_create\_branch`; просмотр: `test\_list\_branches`, `test\_get\_branch`; изменение: `test\_update\_branch\_address`; удаление пустого филиала: `test\_delete\_branch`; запрет удаления непустого: `test\_protected\_deletion\_through\_api\_preserves\_data`. |

| FR-04. Экземпляры | `inventory/test\_copies\_api.py`, `CopyAPITests` | Регистрация: `test\_create\_copy`; просмотр списка и записи: `test\_list\_and\_retrieve`; изменение: `test\_put\_updates\_copy`; удаление: `test\_delete\_copy\_preserves\_book\_and\_branch`; обязательные поля: `test\_required\_fields`; уникальность номера: `test\_inventory\_number\_is\_unique\_in\_database`, `test\_duplicate\_update\_is\_rejected`; ошибочные связи и сохранность БД: `test\_invalid\_create\_preserves\_database`. Учитывается в нижней оценке. |

| FR-05. Перемещение | `inventory/test\_copies\_api.py`, `CopyAPITests` | Изменение филиала с сохранением остальных полей: `test\_patch\_moves\_copy\_and\_preserves\_other\_fields`; отказ при ошибочных данных без изменения экземпляра: `test\_invalid\_patch\_preserves\_all\_fields`. Учитывается в нижней оценке. |

| FR-06. Фильтрация | `inventory/test\_copies\_api.py`, `CopyAPITests` | `test\_filters` проверяет фильтры по книге, филиалу, их сочетанию и пустой результат; `test\_invalid\_filters` проверяет ошибочные параметры. Учитывается в нижней оценке. |

| FR-07. Веб-интерфейс | `catalog/test\_web.py`, `inventory/test\_web.py` | Тесты HTML-списков и форм, создания и изменения записей, отображения связанных объектов, ошибочного ввода и сохранности данных при отказе. |

| FR-08. HTTP API | `catalog/tests.py`, `catalog/test\_books\_api.py`, `inventory/tests.py`, `inventory/test\_copies\_api.py`, `config/tests.py` | API-тесты проверяют ответы успешных операций и ошибочных запросов. Примеры: `test\_missing\_author\_returns\_404`, `test\_missing\_book\_returns\_404`, `test\_missing\_branch\_returns\_404`, `test\_missing\_copy`, `test\_invalid\_data\_is\_rejected`, `test\_protected\_deletion\_through\_api\_preserves\_data`, `test\_health\_rejects\_post`. |

| FR-09. Доступность | `config/tests.py`, `HealthEndpointTests` | `test\_health\_returns\_ok` проверяет GET, статус 200 и JSON; `test\_health\_rejects\_post` проверяет отказ с кодом 405. Учитывается в нижней оценке. |



\## Unit-тесты предметного правила



Класс `AuthorDeletionUnitTests` находится в `catalog/tests.py`.



\- `test\_author\_with\_books\_is\_not\_deleted` проверяет статус 409,

&#x20; код ошибки `author\_has\_books` и отсутствие вызова удаления.

\- `test\_author\_without\_books\_can\_be\_deleted` проверяет вызов

&#x20; удаления и возврат ответа со статусом 204.



Тесты вызывают настоящий метод `AuthorViewSet.destroy`.

Получение автора, проверка наличия связанных книг и операция

удаления заменены объектами Mock. Условие предметного правила

не подменяется.



Класс наследуется от `SimpleTestCase`, который запрещает

обращения к базе данных по умолчанию.



\## Интеграционные тесты и изоляция



Тесты моделей, API и HTML проверяют работу приложения

с отдельной тестовой БД.



Используется конфигурация `config.settings\_test`.

Тестовые данные создаются внутри тестов. Рабочая SQLite

и PostgreSQL на виртуальной машине не используются

при выполнении этого локального набора тестов.



Тесты миграций проверяют сохранение существующих данных:



\- `BookDescriptionMigrationTests`;

\- `CopyShelfLocationMigrationTests`;

\- `CopyStatusMigrationTests`.



\## Покрытие кода и обязательные проверки



Coverage отдельно измеряет покрытие исполняемых строк кода.

Порог покрытия строк установлен в конфигурации проекта.

Он не заменяет расчёт функционального покрытия по ТЗ.



Полный обязательный набор проверок запускается командой:



&#x20;   make verify



Запрещено пропускать тесты, снижать пороги или добавлять

исключения анализаторов только ради успешного результата.

Изменения правил проверок требуют обоснования и review

в соответствии с CONTRIBUTING.md.

