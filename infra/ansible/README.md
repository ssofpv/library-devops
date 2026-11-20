# Ansible для проекта «Библиотека»

Ansible подготавливает отдельную Ubuntu Server 24.04 amd64.
Текущий playbook разрешает применение только к одному узлу окружения lab.
Настройка staging через эту роль пока заблокирована проверкой окружения.

## Окружения и параметры

Окружение lab работает на ВМ library-lab. Проверенный адрес —
192.168.56.105, администратор — sofia. Адрес получен через DHCP;
перед новым применением его нужно проверить командой
`ip -br -4 address` на library-lab.

Для lab заданы проект Compose library-lab, каталог /opt/library-lab
и порт приложения 18001. Роль lab_application развёртывает приложение
по запросу после подготовки Linux и Docker.

Окружение staging описывает действующую ВМ library-app:
192.168.56.10, администратор sofia, проект library-staging,
каталог /opt/library-staging и порт 18000. Учётная запись
library-deploy используется существующим CD.
Production и прежняя ВМ library-db в inventory не входят.

| Уровень | Расположение | Параметры |
| --- | --- | --- |
| Общий | group_vars/all.yml | Интерпретатор Python, версии Docker и Compose, общие параметры приложения |
| Окружение | inventories/<окружение>/group_vars/library_hosts.yml | Проект Compose, каталог и порт приложения |
| Узел | inventories/<окружение>/host_vars/<узел>.yml | SSH-адрес, пользователь, пути к ключам и сетевые ограничения |
| Секреты | Вне репозитория | Закрытые ключи и пароли; для настроек приложения предусмотрены отдельные Vault-файлы |

## Управляющая машина

Для ручных проверок используется library-app. Ansible установлен
в отдельное окружение ~/.venvs/library-ansible.
Версия ansible-core 2.21.6 закреплена в requirements.txt;
используется Python 3.12.

Содержимое каталога infra/ansible скопировано на управляющую машину
в ~/lr7-ansible-check. После изменения исходников эту копию необходимо
обновлять. Команды ниже выполняются на library-app из этого каталога:

```bash
cd "$HOME/lr7-ansible-check"
```

На управляющей машине находятся публичные ключи
~/.ssh/library_lab_ansible.pub и ~/.ssh/library_sofia_windows.pub.
Закрытый ключ ~/.ssh/library_lab_ansible защищён парольной фразой
и должен быть загружен в ssh-agent в текущем сеансе.

Пароли SSH и sudo вводятся интерактивно.
Закрытые ключи и пароли в Git не добавляются.
Существующие секреты staging остаются в серверных .env.staging
и .smoke.json с правами 0600.

## Проверки и применение

На управляющей машине задаются параметры lab:

```bash
export LIBRARY_LAB_HOST=192.168.56.105
export LIBRARY_LAB_SSH_USER=sofia
```

Проверка inventory lab:

```bash
~/.venvs/library-ansible/bin/ansible-inventory --playbook-dir . -i inventories/lab/hosts.yml --graph
```

В группе library_hosts должен быть только library_lab.

Проверка inventory staging:

```bash
~/.venvs/library-ansible/bin/ansible-inventory --playbook-dir . -i inventories/staging/hosts.yml --graph
```

В группе library_hosts должен быть только library_staging.
Выбирать один inventory на запуск.

Проверка синтаксиса выполняется без подключения к целевой ВМ:

```bash
~/.venvs/library-ansible/bin/ansible-playbook -i inventories/lab/hosts.yml site.yml --syntax-check
```

```bash
sh -n roles/bootstrap/files/apply-firewall.sh
```

Первый запуск на чистой ВМ с первоначальным парольным SSH-доступом:

```bash
~/.venvs/library-ansible/bin/ansible-playbook -i inventories/lab/hosts.yml site.yml --limit library_lab --ask-pass --ask-become-pass
```

После настройки используется вход по ключу:

```bash
~/.venvs/library-ansible/bin/ansible-playbook -i inventories/lab/hosts.yml site.yml --limit library_lab --private-key "$HOME/.ssh/library_lab_ansible" --ask-become-pass
```

На запрос BECOME password вводится пароль пользователя sofia
от library-lab.

## Развёртывание приложения на library-lab

На контроллере создай каталог для Vault вне репозитория и зашифрованный файл:

```bash
install -d -m 0700 "$HOME/.config/library-lab"
~/.venvs/library-ansible/bin/ansible-vault create "$HOME/.config/library-lab/vault.yml"
```

В файле нужны два поля, `django_secret_key` и `postgres_password`. Используй
два независимо сгенерированных значения, например по одному вызову
`openssl rand -hex 32` на поле. Сохрани пароль Vault отдельно. Для уже
созданного тома PostgreSQL сохраняй тот же пароль БД.

Из актуальной копии infra/ansible на контроллере запусти:

```bash
~/.venvs/library-ansible/bin/ansible-playbook -i inventories/lab/hosts.yml site.yml --limit library_lab --private-key "$HOME/.ssh/library_lab_ansible" --ask-become-pass --ask-vault-pass -e library_deploy_app=true
```

SHA образа задан в inventories/lab/group_vars/library_hosts.yml. Приложение
публикуется только на адресе Host-only с портом 18001. Миграции выполняются
до запуска веб-сервиса. Проверки обращаются к каталогу книг через Django ORM,
а контроллер проверяет /health/ и /version/. Полный повтор с теми же
параметрами должен дать changed=0.

## Требуемое состояние и права

Роль bootstrap обеспечивает базовые пакеты, SSH, техническую
учётную запись library-deploy, каталоги, Docker Engine, Compose
и firewall. Версии Docker, CLI, containerd и Compose заданы явно.

Учётная запись library-deploy имеет заблокированный пароль
и только основную группу. Каталоги приложения и выпусков
принадлежат root с правами 0700. Каталоги .ssh имеют права 0700,
файл authorized_keys — 0600.

SSH-конфигурация применяется после проверки входа администратора
по ключу. Вход под root и парольная SSH-аутентификация запрещены.
Перед перечитыванием службы проверяется конфигурация sshd.

Для IPv4 разрешены SSH и опубликованный порт приложения 18001
с Windows 192.168.56.1 и управляющей машины 192.168.56.10
через enp0s8. Служебный DHCP-трафик сохраняется.
Для IPv6 разрешены служебные ICMPv6 и DHCPv6.

Сценарий apply-firewall.sh проверяет файлы правил, загружает
управляемые цепочки и подключает их к INPUT и DOCKER-USER.
Проверка существующих переходов предотвращает их дублирование.
Служба library-firewall загружает правила при старте ВМ.
Запуск Docker зависит от успешного запуска firewall.

Изменения ролей, шаблонов, параметров доступа и workflow
должны проходить ревью второй участницы перед слиянием в main.

## Результаты проверки 17.11.2026

| Проверка | Результат |
| --- | --- |
| Подготовка чистой library-lab | ok=31, changed=17, unreachable=0, failed=0 |
| Повторный запуск | ok=28, changed=0, unreachable=0, failed=0 |
| Восстановление ручной правки | Права /opt/library-lab изменены с 0700 на 0755; Ansible восстановил 0700, changed=1, failed=0 |
| Перезагрузка | SSH-доступ восстановлен, проверка служб успешна, цепочки firewall загружены |
| Права library-deploy | Только основная группа; групп sudo и docker нет |
| Сетевые сокеты | Из нелокальных TCP-портов слушается SSH 22; DNS работает на loopback, DHCP используется для адресации |

## Автоматические проверки

Workflow ansible-inventory.yml проверяет inventory обоих окружений,
синтаксис playbook и firewall-сценария. Версия Ansible закреплена.
Эти проверки не подключаются к ВМ.

## Запуск CD для library-lab

GitHub Actions публикует образ в GHCR после проверок. Оператор запускает
применение на library-app из проверенной версии инфраструктурного кода.
Используется тот же SSH-ключ из ssh-agent и тот же Vault, что при ручном
запуске Ansible. На контроллере нужен клиент Docker для проверки манифеста
образа в GHCR.

Из актуального каталога infra/ansible:

```bash
export LIBRARY_LAB_HOST=192.168.56.105
export LIBRARY_LAB_SSH_USER=sofia
sh ./deploy-lab.sh "$RELEASE_SHA"
```

Перед запуском присвой RELEASE_SHA полный SHA коммита, образ которого уже
опубликован. Команда проверяет тег в реестре, применяет Ansible только
к library-lab и выполняет предусмотренные проверки приложения и версии.
При ошибке реестра, применения или проверки команда завершается с ненулевым
кодом. Для повторного выпуска с тем же SHA ожидается changed=0.