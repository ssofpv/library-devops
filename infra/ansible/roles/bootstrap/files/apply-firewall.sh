#!/bin/sh
set -eu

# Validate both rule files before applying them.
/usr/sbin/iptables-restore --wait 5 --noflush --test /etc/library-firewall/v4.rules
/usr/sbin/ip6tables-restore --wait 5 --noflush --test /etc/library-firewall/v6.rules

# Replace the managed chains.
/usr/sbin/iptables-restore --wait 5 --noflush /etc/library-firewall/v4.rules
/usr/sbin/ip6tables-restore --wait 5 --noflush /etc/library-firewall/v6.rules

ensure_jump() {
    if ! "$1" -w 5 -C "$2" -j "$3" >/dev/null 2>&1; then
        "$1" -w 5 -I "$2" 1 -j "$3"
    fi
}

for tool in /usr/sbin/iptables /usr/sbin/ip6tables; do
    if ! "$tool" -w 5 -S DOCKER-USER >/dev/null 2>&1; then
        "$tool" -w 5 -N DOCKER-USER
    fi

    ensure_jump "$tool" INPUT LIBRARY-INPUT
    ensure_jump "$tool" DOCKER-USER LIBRARY-DOCKER
    ensure_jump "$tool" FORWARD DOCKER-USER
done