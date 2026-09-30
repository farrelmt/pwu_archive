#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
readonly KEY_FILE="${BACKUP_KEY_FILE:-/home/itpwu/.config/pwu-archive/backup.key}"
readonly DB_CONTAINER="${DB_CONTAINER:-archiveproject-db-1}"
readonly DB_USER="${DB_USER:-farrel}"
readonly DB_NAME="${DB_NAME:-pwu_archive_db}"
readonly MEDIA_VOLUME="${MEDIA_VOLUME:-archiveproject_media_volume}"

usage() {
    echo "Usage: $0 BACKUP_DIRECTORY [--verify-only] [--yes]" >&2
    exit 2
}

[[ $# -ge 1 && $# -le 3 ]] || usage
readonly BACKUP_DIR="$(realpath -- "$1")"
shift

VERIFY_ONLY=false
ASSUME_YES=false
for option in "$@"; do
    case "$option" in
        --verify-only) VERIFY_ONLY=true ;;
        --yes) ASSUME_YES=true ;;
        *) usage ;;
    esac
done

[[ -d "$BACKUP_DIR" ]] || { echo "Backup directory not found: $BACKUP_DIR" >&2; exit 1; }
[[ -s "$KEY_FILE" ]] || { echo "Encryption key not found: $KEY_FILE" >&2; exit 1; }
[[ "$MEDIA_VOLUME" =~ ^[A-Za-z0-9][A-Za-z0-9_.-]+$ ]] || {
    echo "Unsafe media volume name." >&2
    exit 1
}

if [[ -f "$BACKUP_DIR/SHA256SUMS" ]]; then
    (cd "$BACKUP_DIR" && sha256sum --check SHA256SUMS)
else
    echo "Warning: legacy backup has no checksum manifest." >&2
fi

decrypt_file() {
    local input_file="$1"
    case "$input_file" in
        *.gpg)
            gpg --batch --quiet --pinentry-mode loopback \
                --passphrase-file "$KEY_FILE" --decrypt "$input_file"
            ;;
        *.enc)
            openssl enc -d -aes-256-cbc -pbkdf2 -iter 200000 \
                -pass "file:$KEY_FILE" -in "$input_file"
            ;;
        *)
            echo "Unsupported encrypted backup format: $input_file" >&2
            return 1
            ;;
    esac
}

if [[ -f "$BACKUP_DIR/db.dump.gpg" ]]; then
    DB_BACKUP="$BACKUP_DIR/db.dump.gpg"
elif [[ -f "$BACKUP_DIR/db.dump.enc" ]]; then
    DB_BACKUP="$BACKUP_DIR/db.dump.enc"
else
    echo "Database backup is missing." >&2
    exit 1
fi

if [[ -f "$BACKUP_DIR/media.tar.gz.gpg" ]]; then
    MEDIA_BACKUP="$BACKUP_DIR/media.tar.gz.gpg"
elif [[ -f "$BACKUP_DIR/media.tar.gz.enc" ]]; then
    MEDIA_BACKUP="$BACKUP_DIR/media.tar.gz.enc"
else
    echo "Media backup is missing." >&2
    exit 1
fi

echo "Validating encrypted database archive..."
decrypt_file "$DB_BACKUP" \
    | docker exec -i "$DB_CONTAINER" pg_restore --list >/dev/null
echo "Validating encrypted media archive..."
decrypt_file "$MEDIA_BACKUP" \
    | docker run --rm -i alpine:3.22 tar -tzf - >/dev/null
echo "Backup validation passed: $BACKUP_DIR"

if [[ "$VERIFY_ONLY" == true ]]; then
    exit 0
fi

if [[ "$ASSUME_YES" != true ]]; then
    echo
    echo "WARNING: this replaces database '$DB_NAME' and all files in '$MEDIA_VOLUME'."
    read -r -p "Type RESTORE to continue: " confirmation
    [[ "$confirmation" == "RESTORE" ]] || { echo "Restore cancelled."; exit 1; }
fi

if [[ "${RESTORE_SKIP_SAFETY_BACKUP:-false}" != true ]]; then
    echo "Creating a safety backup of the current state before restore..."
    "$SCRIPT_DIR/backup.sh"
fi

restart_services() {
    cd "$PROJECT_DIR"
    docker compose up -d web nginx
}
trap restart_services EXIT

cd "$PROJECT_DIR"
docker compose stop web nginx

docker exec "$DB_CONTAINER" dropdb --if-exists --force -U "$DB_USER" "$DB_NAME"
docker exec "$DB_CONTAINER" createdb -U "$DB_USER" -O "$DB_USER" "$DB_NAME"
decrypt_file "$DB_BACKUP" \
    | docker exec -i "$DB_CONTAINER" pg_restore \
        --exit-on-error --no-owner --no-privileges \
        -U "$DB_USER" -d "$DB_NAME"

decrypt_file "$MEDIA_BACKUP" \
    | docker run --rm -i -v "$MEDIA_VOLUME:/media_data" alpine:3.22 \
        sh -c 'find /media_data -mindepth 1 -maxdepth 1 -exec rm -rf -- {} + && tar -xzf - -C /media_data'

docker compose run --rm web python manage.py migrate --noinput
trap - EXIT
restart_services
echo "Restore completed successfully from: $BACKUP_DIR"
