# ЛР2: PostgreSQL на library-db

Эта инструкция описывает развёртывание PostgreSQL без контейнеров для проекта «Библиотека» на Ubuntu Server 24.04.5 LTS. Сеть и SSH по ключам должны быть настроены заранее согласно [инструкции по двум ВМ](ubuntu-network-ssh.md). Выполненные проверки относятся к PostgreSQL 16 на `library-db` (`192.168.56.20/24`) и клиенту `library-app` (`192.168.56.10/24`). Настройки Django и служба приложения относятся к отдельному этапу.

## Установка и исходное состояние

Работайте в SSH-сеансе `polina@library-db:~$`. Снимок `02-ssh-keys-only` должен быть доступен для отката. Сначала проверьте свободное место и доступный пакет:

```bash
lsblk -o NAME,SIZE,TYPE,FSTYPE,MOUNTPOINTS
df -h /
apt-cache policy postgresql
sudo apt update
sudo apt install postgresql
pg_lsclusters
systemctl is-active postgresql
sudo ss -ltnp | grep ':5432'
```

На использованной ВМ диск 25 ГБ разбит с LVM: корневой том около 11,5 ГБ, до установки было около 6 ГБ свободно. Разметку не меняли. После установки кластер `16 main` работал на порту 5432, первоначально только на `127.0.0.1`. Если версия или пути отличаются, определите их по выводу на своей машине до редактирования конфигурации.

## Firewall до открытия сетевого порта

Перед включением UFW оставьте действующий SSH-сеанс открытым и подготовьте разрешение для SSH с Windows-хоста `192.168.56.1`. На `library-db`:

```bash
sudo ufw default deny incoming
sudo ufw allow in on enp0s8 proto tcp from 192.168.56.1 to 192.168.56.20 port 22
sudo ufw allow in on enp0s8 proto tcp from 192.168.56.10 to 192.168.56.20 port 5432
sudo ufw show added
sudo ufw enable
sudo ufw status verbose
```

На вопрос `Proceed with operation (y|n)?` ответьте `y` после проверки правил. Затем **из PowerShell Windows**, а не из Linux, откройте новый сеанс, сохраняя старый до успешного входа:

```powershell
ssh -i "$env:USERPROFILE\.ssh\library_polina" -o IdentitiesOnly=yes polina@192.168.56.20
```

UFW должен показывать `active`, `deny (incoming)` и только указанные входящие правила. Эти разрешения привязаны к интерфейсу и точному адресу назначения. Пароль Ubuntu нужен только для `sudo`, passphrase SSH-ключа запрашивается на Windows.

## База и роль приложения

На `library-db` проверьте парольное шифрование:

```bash
sudo -u postgres psql -Atqc 'SHOW password_encryption'
```

В проверенной установке значение `scram-sha-256`. Создайте роль с вводом уникального пароля в интерактивном приглашении; символы не отображаются. Не вводите пароль в аргументы команд, чат, скриншоты или Git.

```bash
sudo -u postgres createuser --pwprompt --no-superuser --no-createdb --no-createrole library_app
sudo -u postgres createdb --owner=postgres library_db
sudo -u postgres psql -d library_db -c 'REVOKE ALL ON DATABASE library_db FROM PUBLIC'
sudo -u postgres psql -d library_db -c 'GRANT CONNECT ON DATABASE library_db TO library_app'
sudo -u postgres psql -d library_db -c 'REVOKE ALL ON SCHEMA public FROM PUBLIC'
sudo -u postgres psql -d library_db -c 'GRANT USAGE, CREATE ON SCHEMA public TO library_app'
```

Роль `library_app` не является суперпользователем и не может создавать базы или роли. Она может подключаться к своей БД, использовать схему `public` и создавать в ней объекты для миграций Django; владельцем БД остаётся `postgres`. Команды создания роли и БД выполняйте один раз: перед повтором проверьте, существуют ли они. Для проверки без раскрытия пароля:

```bash
sudo -u postgres psql -Atqc "SELECT rolname, rolcanlogin, rolsuper, rolcreatedb, rolcreaterole FROM pg_roles WHERE rolname='library_app';"
sudo -u postgres psql -Atqc "SELECT datname, pg_get_userbyid(datdba) FROM pg_database WHERE datname='library_db';"
sudo -u postgres psql -d library_db -Atqc "SELECT has_database_privilege('library_app','library_db','CONNECT'), has_database_privilege('library_app','library_db','CREATE'), has_schema_privilege('library_app','public','USAGE'), has_schema_privilege('library_app','public','CREATE');"
psql -h 127.0.0.1 -U library_app -d library_db -W -c 'SELECT current_user, current_database();'
```

Проверенные результаты: `library_app|t|f|f|f`, `library_db|postgres`, `t|f|t|t`, вход как `library_app` в `library_db`.

## Прослушивание и правило доступа

На установленном кластере пути определены командами:

```bash
sudo -u postgres psql -Atqc 'SHOW config_file'
sudo -u postgres psql -Atqc 'SHOW hba_file'
```

Получены `/etc/postgresql/16/main/postgresql.conf` и `/etc/postgresql/16/main/pg_hba.conf`. В `postgresql.conf` уже включён `include_dir = 'conf.d'`; исходные правила `pg_hba.conf` допускают локальные соединения и loopback с SCRAM. Запишите отдельный файл с адресами прослушивания и добавьте ровно одно правило для приложения:

```bash
sudo cp -a /etc/postgresql/16/main/pg_hba.conf /etc/postgresql/16/main/pg_hba.conf.before-library
printf "%s\n" "listen_addresses = 'localhost,192.168.56.20'" | sudo tee /etc/postgresql/16/main/conf.d/10-library.conf
printf '%s\n' 'host library_db library_app 192.168.56.10/32 scram-sha-256' | sudo tee -a /etc/postgresql/16/main/pg_hba.conf
```

Перед повторным добавлением правила проверьте `sudo tail -n 10 /etc/postgresql/16/main/pg_hba.conf`, чтобы не создавать дубликат. Правило `/32` относится только к `library-app`. Для проверки перед перезапуском:

```bash
sudo -u postgres psql -P pager=off -Atqc "SELECT line_number, type, database, user_name, address, auth_method, coalesce(error,'') FROM pg_hba_file_rules WHERE address='192.168.56.10' OR error IS NOT NULL;"
sudo -u postgres /usr/lib/postgresql/16/bin/postgres -D /var/lib/postgresql/16/main -c config_file=/etc/postgresql/16/main/postgresql.conf -C listen_addresses
```

Ожидается правило для `library_db`, `library_app`, `192.168.56.10`, `scram-sha-256` без ошибки и значение `localhost,192.168.56.20`. До перезапуска `pg_file_settings` может показывать `setting could not be applied` для `listen_addresses`: это параметр времени старта. Если проверка `postgres -C` или разбор `pg_hba_file_rules` даёт иную ошибку, сначала исправьте её.

```bash
sudo pg_ctlcluster 16 main restart
pg_lsclusters
sudo ss -ltnp | grep ':5432'
```

После перезапуска проверены `online` и прослушивание на `127.0.0.1:5432` и `192.168.56.20:5432`. Не используйте `listen_addresses = '*'`: серверу не требуется слушать NAT или все IPv6 интерфейсы.

## Проверки с клиента и после перезагрузки

На `library-app` в сеансе `sofia@library-app:~$` можно сначала проверить TCP без установки пакетов:

```bash
python3 -c "import socket; s=socket.create_connection(('192.168.56.20',5432),3); print('TCP 5432 reachable'); s.close()"
sudo apt update
sudo apt install postgresql-client
psql -h 192.168.56.20 -U library_app -d library_db -W -c 'SELECT current_user, current_database(), inet_client_addr();'
```

Пароль PostgreSQL вводится только на запрос `Password:`. Проверены `library_app`, `library_db` и адрес клиента `192.168.56.10`. С Windows-хоста выполните в PowerShell:

```powershell
Test-NetConnection -ComputerName 192.168.56.20 -Port 5432
```

Проверенный результат: `SourceAddress: 192.168.56.1`, `PingSucceeded: True`, `TcpTestSucceeded: False`. Ping подтверждает достижимость ВМ, но доступ к PostgreSQL с Windows закрыт.

До перезагрузки `systemctl is-enabled postgresql` показал `enabled`, а `sudo ufw status` — `active`. Команда `sudo reboot` на `library-db` штатно разрывает SSH. Подождите загрузки, подключитесь заново по ключу с Windows и выполните `pg_lsclusters` и `sudo ufw status verbose`. После выполненной перезагрузки подтверждены вход по SSH, кластер `16 main online`, адрес `192.168.56.20/24` и активный UFW с прежними правилами. Первые попытки SSH во время загрузки дали timeout/reset; после завершения загрузки вход прошёл.

Настройки Django для PostgreSQL, служба приложения и firewall на `library-app` здесь не рассматриваются. Реальные пароли и закрытые SSH-ключи нельзя помещать в репозиторий.
