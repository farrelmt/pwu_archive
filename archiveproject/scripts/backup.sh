#!/usr/bin/env bash
set -Eeuo pipefail
umask 077

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly PROJECT_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"
readonly BACKUP_BASE="${BACKUP_BASE:-/home/itpwu/pwu_archive/backups}"
readonly KEY_FILE="${BACKUP_KEY_FILE:-/home/itpwu/.config/pwu-archive/backup.key}"
readonly DB_CONTAINER="${DB_CONTAINER:-archiveproject-db-1}"
readonly DB_USER="${DB_USER:-farrel}"
readonly DB_NAME="${DB_NAME:-pwu_archive_db}"
readonly MEDIA_VOLUME="${MEDIA_VOLUME:-archiveproject_media_volume}"
readonly RETENTION_DAYS="${BACKUP_RETENTION_DAYS:-7}"
readonly CREATED_AT="$(date --iso-8601=seconds)"
readonly BACKUP_ID="$(date +"%Y-%m-%d_%H-%M-%S")"
readonly RUN_DIR="$BACKUP_BASE/$BACKUP_ID"
readonly LOCK_FILE="$BACKUP_BASE/.backup.lock"

for command_name in docker gpg sha256sum flock; do
    command -v "$command_name" >/dev/null
done

install -d -m 700 "$BACKUP_BASE" "$(dirname -- "$KEY_FILE")"
exec 9>"$LOCK_FILE"
flock -n 9 || {
    echo "Another backup is already running." >&2
    exit 1
}

if [[ ! -s "$KEY_FILE" ]]; then
    install -m 600 /dev/null "$KEY_FILE"
    openssl rand -hex 32 >"$KEY_FILE"
fi
chmod 600 "$KEY_FILE"
install -d -m 700 "$RUN_DIR"

cleanup_partial() {
    find "$RUN_DIR" -maxdepth 1 -type f -name '*.partial' -delete
}
trap cleanup_partial EXIT

encrypt_stream() {
    local output_file="$1"
    gpg --batch --yes --quiet --pinentry-mode loopback \
        --passphrase-file "$KEY_FILE" \
        --symmetric --cipher-algo AES256 \
        --output "$output_file"
}

decrypt_file() {
    local input_file="$1"
    gpg --batch --quiet --pinentry-mode loopback \
        --passphrase-file "$KEY_FILE" \
        --decrypt "$input_file"
}

echo "Creating encrypted backup $BACKUP_ID..."

docker exec "$DB_CONTAINER" pg_dump -Fc -U "$DB_USER" "$DB_NAME" \
    | encrypt_stream "$RUN_DIR/db.dump.gpg.partial"
decrypt_file "$RUN_DIR/db.dump.gpg.partial" \
    | docker exec -i "$DB_CONTAINER" pg_restore --list >/dev/null
mv "$RUN_DIR/db.dump.gpg.partial" "$RUN_DIR/db.dump.gpg"

docker run --rm \
    -v "$MEDIA_VOLUME:/media_data:ro" \
    alpine:3.22 tar -czf - -C /media_data . \
    | encrypt_stream "$RUN_DIR/media.tar.gz.gpg.partial"
decrypt_file "$RUN_DIR/media.tar.gz.gpg.partial" \
    | docker run --rm -i alpine:3.22 tar -tzf - >/dev/null
mv "$RUN_DIR/media.tar.gz.gpg.partial" "$RUN_DIR/media.tar.gz.gpg"

(
    cd "$RUN_DIR"
    sha256sum db.dump.gpg media.tar.gz.gpg >SHA256SUMS
)

cat >"$RUN_DIR/MANIFEST" <<EOF
format=pwu-archive-backup-v2
created_at=$CREATED_AT
database=$DB_NAME
database_format=postgresql-custom
encryption=openpgp-aes256
media_format=tar-gzip
EOF

chmod 600 "$RUN_DIR"/*
touch "$RUN_DIR/COMPLETE"
chmod 600 "$RUN_DIR/COMPLETE"

find "$BACKUP_BASE" -mindepth 1 -maxdepth 1 -type d \
    -name '????-??-??_??-??-??' -mtime "+$RETENTION_DAYS" \
    -exec test -f '{}/COMPLETE' \; -exec rm -rf -- '{}' +

echo "Encrypted backup completed: $RUN_DIR"
echo "Keep a protected offline copy of $KEY_FILE; backups cannot be restored without it."
