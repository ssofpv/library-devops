# ЛР2: Ubuntu, сеть и SSH для двух виртуальных машин

Эта инструкция воспроизводит подготовку двух ВМ проекта «Библиотека» в Oracle VirtualBox. Она описывает уже выполненный ручной этап. Развёртывание приложения, PostgreSQL и firewall выполняются в следующих задачах ЛР2.

## Машины и сеть

| Назначение | Имя ВМ | Учётная запись администратора | Адрес Host-only |
| --- | --- | --- | --- |
| Приложение | `library-app` | `sofia` | `192.168.56.10/24` |
| База данных | `library-db` | `polina` | `192.168.56.20/24` |

На обеих ВМ установлена Ubuntu Server 24.04.5 LTS, 2 ГБ ОЗУ, 2 vCPU, виртуальный диск 25 ГБ. Используются два сетевых адаптера: NAT (`enp0s3`) для доступа к пакетам и Host-only (`enp0s8`) для связи с компьютером и между серверами. На Windows-хосте Host-only адаптер имеет адрес `192.168.56.1/24`. DHCP VirtualBox включён: сервер `192.168.56.100`, диапазон `192.168.56.101–192.168.56.254`; статические адреса ВМ лежат вне этого диапазона. Совпадающие NAT-адреса `10.0.2.15` у двух ВМ не мешают связи: машины используют отдельные NAT-сегменты, а друг с другом общаются через Host-only.

На каждой машине установите Ubuntu Server, создайте указанную учётную запись с правом `sudo` и установите `openssh-server`. Во время установки пароль учётной записи Ubuntu нужен для консоли и `sudo`; passphrase закрытого SSH-ключа на Windows — другой секрет. Не сохраняйте их в репозитории. Для отката перед ужесточением SSH выключите ВМ и создайте снимок `01-ubuntu-network-ssh`.

## Постоянные адреса

Исходный `/etc/netplan/50-cloud-init.yaml` с DHCP не удаляйте. На `library-app` создайте через консоль ВМ файл `/etc/netplan/99-library.yaml`:

```yaml
network:
  version: 2
  ethernets:
    enp0s8:
      dhcp4: false
      addresses:
        - 192.168.56.10/24
```

На `library-db` используйте такой же файл, заменив только адрес на `192.168.56.20/24`. Выполните в консоли **каждой** ВМ:

```bash
sudo chmod 600 /etc/netplan/99-library.yaml
sudo netplan generate
sudo netplan apply
ip -br addr
ip route
```

Проверяйте, что `enp0s8` получил нужный адрес, а маршрут по умолчанию остался через NAT (`enp0s3`, `10.0.2.2`). Менять IP лучше в консоли VirtualBox: действующий SSH-сеанс может оборваться. Перезагрузите ВМ и проверьте адрес снова. С `library-app` выполните `ping -c 4 192.168.56.20`, а с `library-db` — `ping -c 4 192.168.56.10`. Ответы на ping подтверждают сеть, но не работу PostgreSQL.

## Установка и проверка SSH

На обеих ВМ:

```bash
sudo apt update
sudo apt install openssh-server
sudo systemctl enable --now ssh
systemctl is-active ssh
systemctl is-enabled ssh
sudo ssh-keygen -lf /etc/ssh/ssh_host_ed25519_key.pub
```

Перед первым подключением с Windows сравните показанный отпечаток ключа **сервера** с отпечатком в приглашении SSH. Ключ сервера отличается от клиентского ключа пользователя.

На компьютере Софии в PowerShell созданы два клиентских ключа Ed25519 с passphrase: `$env:USERPROFILE\.ssh\library_sofia` и `$env:USERPROFILE\.ssh\library_polina`. Закрытые ключи остаются в профиле Windows Софии и никому не передаются; на серверы добавляются только соответствующие `.pub` файлы. Чтобы повторить создание ключа при необходимости, используйте `ssh-keygen -t ed25519 -f "$env:USERPROFILE\.ssh\library_sofia" -C "sofia-library-devops"` (для второго ключа замените имя файла и комментарий на `library_polina` и `polina-library-devops`). Не перезаписывайте существующий ключ.

После проверки отпечатка сервера можно добавить публичный ключ, не стирая ранее разрешённые ключи. Эти команды выполняются **в PowerShell Windows**, пока парольный SSH-вход ещё разрешён:

```powershell
Get-Content "$env:USERPROFILE\.ssh\library_sofia.pub" | ssh sofia@192.168.56.10 'umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys'
Get-Content "$env:USERPROFILE\.ssh\library_polina.pub" | ssh polina@192.168.56.20 'umask 077; mkdir -p ~/.ssh; cat >> ~/.ssh/authorized_keys; chmod 700 ~/.ssh; chmod 600 ~/.ssh/authorized_keys'
```

На каждой ВМ проверьте владельца и права через `stat -c '%U %a %n' ~/.ssh ~/.ssh/authorized_keys`; ожидаются свой пользователь, режимы `700` и `600`. Отпечаток записанного клиентского ключа можно проверить командой `ssh-keygen -lf ~/.ssh/authorized_keys` и сравнением с соответствующим `.pub` на Windows. До отключения паролей подтвердите новый вход по ключу, сохраняя старый SSH-сеанс открытым:

```powershell
ssh -i "$env:USERPROFILE\.ssh\library_sofia" -o IdentitiesOnly=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no sofia@192.168.56.10
ssh -i "$env:USERPROFILE\.ssh\library_polina" -o IdentitiesOnly=yes -o PasswordAuthentication=no -o KbdInteractiveAuthentication=no polina@192.168.56.20
```

На **каждой** ВМ создайте `/etc/ssh/sshd_config.d/00-library.conf` с содержимым:

```text
PermitRootLogin no
PubkeyAuthentication yes
PasswordAuthentication no
KbdInteractiveAuthentication no
```

Убедитесь, что основной `/etc/ssh/sshd_config` подключает `sshd_config.d/*.conf`, а другие активные настройки или блоки `Match` не переопределяют эти значения. До закрытия резервного сеанса проверьте и примените конфигурацию:

```bash
sudo /usr/sbin/sshd -t
sudo /usr/sbin/sshd -T | grep -E '^(permitrootlogin|pubkeyauthentication|passwordauthentication|kbdinteractiveauthentication) '
sudo systemctl reload ssh
```

Ожидаемые значения: `permitrootlogin no`, `pubkeyauthentication yes`, `passwordauthentication no`, `kbdinteractiveauthentication no`. Откройте **новый** SSH-сеанс по ключу и проверьте `whoami`. Отрицательная проверка из PowerShell:

```powershell
ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password -o NumberOfPasswordPrompts=1 sofia@192.168.56.10
ssh -o PubkeyAuthentication=no -o PreferredAuthentications=password -o NumberOfPasswordPrompts=1 polina@192.168.56.20
```

Ожидается `Permission denied (publickey)` без запроса пароля. `PermitRootLogin no` подтверждается эффективной конфигурацией; добавлять ключ пользователю `root` ради сетевой пробы не требуется. `exit` завершает SSH-сеанс, не выключая ВМ. После проверки штатно выключите каждую ВМ командой `sudo poweroff` (SSH при этом разорвётся) и создайте снимок `02-ssh-keys-only`. Затем запустите машины и ещё раз проверьте вход по ключу, `whoami` и `systemctl is-active ssh`.

## Границы доступа

Описанные ключи сейчас находятся на компьютере Софии. Для подключения Полины со своего компьютера нужен её собственный ключ и доступ к сети ВМ; сеть Host-only сама по себе не доступна с другого физического компьютера. На данном этапе firewall ещё не настроен, PostgreSQL и приложение не установлены. Не используйте этот этап как подтверждение готового развёртывания.
