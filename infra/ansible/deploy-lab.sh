#!/bin/sh
set -eu

if [ "$#" -ne 1 ]; then
    printf 'Usage: %s <published-image-commit-sha>\n' "$0" >&2
    exit 2
fi

revision=$1
case "$revision" in
    *[!0123456789abcdef]*)
        printf '%s\n' 'The image revision must be a lowercase, 40-character commit SHA.' >&2
        exit 2
        ;;
esac
if [ "${#revision}" -ne 40 ]; then
    printf '%s\n' 'The image revision must be a lowercase, 40-character commit SHA.' >&2
    exit 2
fi

: "${LIBRARY_LAB_HOST:?Set LIBRARY_LAB_HOST to the Host-only address of library-lab.}"
: "${LIBRARY_LAB_SSH_USER:?Set LIBRARY_LAB_SSH_USER to the lab administrator.}"

ansible_playbook="$HOME/.venvs/library-ansible/bin/ansible-playbook"
ssh_key="$HOME/.ssh/library_lab_ansible"
vault_file="$HOME/.config/library-lab/vault.yml"

if [ ! -x "$ansible_playbook" ] || [ ! -r "$ssh_key" ] || [ ! -s "$vault_file" ]; then
    printf '%s\n' 'Prepare the Ansible virtual environment, SSH key and lab Vault on the controller.' >&2
    exit 2
fi

playbook_dir=$(CDPATH= cd -- "$(dirname -- "$0")" && pwd)
cd -- "$playbook_dir"

image="ghcr.io/ssofpv/library-devops:$revision"
printf 'Checking published image %s\n' "$image"
docker manifest inspect "$image" >/dev/null

printf 'Applying Ansible and verifying the release on library-lab (%s)\n' "$LIBRARY_LAB_HOST"
exec "$ansible_playbook" \
    -i inventories/lab/hosts.yml site.yml \
    --limit library_lab \
    --private-key "$ssh_key" \
    --ask-become-pass --ask-vault-pass \
    -e library_deploy_app=true \
    -e "library_app_image_tag=$revision"
