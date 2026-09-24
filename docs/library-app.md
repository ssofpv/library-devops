# Развёртывание на library-app (Ubuntu 24.04)

Эта инструкция относится к двум ВМ в лабораторной сети: `library-app`
(`192.168.56.10`, пользователь администратора `sofia`) и `library-db`
(`192.168.56.20`, PostgreSQL 16). Все команды ниже, если не указано иное,
выполняются в SSH-сеансе `sofia@library-app`. Сначала проверьте фактические
адреса, свободное место, доступ к GitHub и БД, а также отсутствие каталогов
`/opt/library-app` и занятого порта 8000. Не выполняйте команды создания
повторно поверх уже развёрнутой службы.

```bash
hostnamectl
ip -br -4 address
python3 --version
git --version
df -h /
ls -ld /opt/library-app /srv/library-app 2>&1
git ls-remote https://github.com/ssofpv/library-devops.git HEAD
pg_isready -h 192.168.56.20 -p 5432
sudo ss -ltnp
```

`pg_isready` не проверяет пароль роли и не заменяет миграции Django. Для
установки используется системный Python 3.12 в отдельном виртуальном
окружении. Кодом управляет `sofia`, а служба работает под отдельным
пользователем без sudo и без права записи в исходники.

```bash
sudo apt update
sudo apt install -y python3-venv python3-pip git
sudo useradd --system --user-group --no-create-home --shell /usr/sbin/nologin library-app
sudo install -d -m 0755 -o sofia -g sofia /opt/library-app
git clone https://github.com/ssofpv/library-devops.git /opt/library-app
cd /opt/library-app
git switch main
git pull --ff-only origin main
git rev-parse --short HEAD
python3 -m venv .venv
.venv/bin/python -m pip install -r requirements.txt
```

Устанавливайте проверенный коммит после слияния PR по Issue №44. Перед
установкой сверяйте `git rev-parse` с ожидаемым коммитом в PR. Код и `.venv`
принадлежат `sofia`; служебный пользователь может их читать и запускать.
Не добавляйте служебного пользователя в группу `sudo` и не отдавайте ему
права записи на исходники.

## Настройки и база

Настоящий `.env` создаётся только на сервере, он исключён из Git. Подготовьте
файл с правами `0600` и владельцем `library-app`, затем отредактируйте его
локально в SSH-сеансе без демонстрации содержимого или пароля в скриншотах:

```bash
sudo install -m 0600 -o library-app -g library-app /dev/null /opt/library-app/.env
sudo nano /opt/library-app/.env
```

Нужны переменные `DJANGO_SECRET_KEY` (сгенерированное уникальное значение),
`DJANGO_DEBUG=false`, `DJANGO_ALLOWED_HOSTS=192.168.56.10`,
`DJANGO_DB_ENGINE=postgresql`, `POSTGRES_DB=library_db`,
`POSTGRES_USER=library_app`, `POSTGRES_PASSWORD` (существующий пароль роли),
`POSTGRES_HOST=192.168.56.20` и `POSTGRES_PORT=5432`. Строки должны
одновременно соответствовать синтаксису `systemd EnvironmentFile` и
`python-dotenv`; значения с пробелами и специальными знаками заключайте в
кавычки с соответствующим экранированием. Не используйте образец ключа.
Проверьте права, не печатая содержимое:

```bash
stat -c '%U:%G %a %n' /opt/library-app/.env
git status --short
```

Команды Django выполняются из `/opt/library-app` от имени пользователя
службы. Убедитесь, что настройки действительно указывают на PostgreSQL,
затем выполните системные проверки, миграции и сборку CSS:

```bash
cd /opt/library-app
sudo -u library-app .venv/bin/python manage.py shell -c 'from django.conf import settings; d=settings.DATABASES["default"]; print(d["ENGINE"], d["HOST"], d["NAME"], settings.DEBUG, settings.ALLOWED_HOSTS)'
sudo -u library-app .venv/bin/python manage.py check
sudo -u library-app .venv/bin/python manage.py check --deploy
sudo -u library-app .venv/bin/python manage.py migrate
sudo -u library-app .venv/bin/python manage.py showmigrations
sudo .venv/bin/python manage.py collectstatic --noinput
```

`check --deploy` может сообщать о HTTPS, HSTS и защищённых cookie: этот
лабораторный HTTP-сервис открыт только Windows-хосту в сети Host-only и не
является публичным производственным развёртыванием. Предупреждения нужно
записать и объяснить, а не скрывать. Для публичной сети необходим HTTPS и
повторная проверка настроек безопасности. `/health/` возвращает JSON без
запроса к базе; ответ 200 сам по себе не доказывает доступность PostgreSQL.

## Служба и сеть

Файл `deploy/library-app.service` в репозитории — образец для данного адреса,
пути и порта. До установки проверьте, что `192.168.56.10:8000` свободен,
а пользователь, виртуальное окружение и `.env` существуют. Затем:

```bash
sudo install -m 0644 deploy/library-app.service /etc/systemd/system/library-app.service
sudo systemd-analyze verify /etc/systemd/system/library-app.service
sudo systemctl daemon-reload
sudo systemctl enable --now library-app
systemctl status library-app --no-pager
sudo ss -ltnp
curl -i http://192.168.56.10:8000/health/
curl -I http://192.168.56.10:8000/static/library/site.css
```

Если CSS находится по другому пути, возьмите URL из HTML страницы входа.
Проверьте `systemctl restart library-app`, `systemctl stop library-app` и
`systemctl start library-app` с осмотром статуса и ответа. При ошибке
используйте `journalctl -u library-app -n 80 --no-pager` и `ss -ltnp`.

Перед включением UFW сохраните активный SSH-сеанс и добавьте разрешения
**только** для Windows-хоста на Host-only интерфейсе. Сначала изучите
действующие правила:

```bash
sudo ufw status verbose
sudo ufw default deny incoming
sudo ufw allow in on enp0s8 from 192.168.56.1 to any port 22 proto tcp
sudo ufw allow in on enp0s8 from 192.168.56.1 to any port 8000 proto tcp
sudo ufw status numbered
sudo ufw enable
sudo ufw status verbose
```

Из Windows PowerShell откройте **новое** SSH-подключение к `.10`, не закрывая
старое, и проверьте `http://192.168.56.10:8000/health/` в браузере.
Проверьте вход, HTML и оформление, а также отсутствие лишних правил и
прослушиваемых портов. Не открывайте PostgreSQL для Windows.

После перезагрузки обеих ВМ дождитесь их запуска и проверьте
`systemctl is-active library-app`, `systemctl is-enabled library-app`,
`pg_isready` и миграции от служебного пользователя. Перезагрузка ВМ штатно
прерывает SSH-сеанс. Для испытания отказа БД остановите PostgreSQL на
`library-db`, проверьте журнал и запрос, которому нужна база, затем снова
запустите кластер и подтвердите восстановление. `/health/` при этом может
остаться успешным. Для проверки `Restart=on-failure` завершите основной
процесс Gunicorn сигналом `KILL`, проверьте новый PID и состояние службы.
После испытаний оставьте обе службы работающими и сохраните скриншоты
фактических результатов без секретов.
