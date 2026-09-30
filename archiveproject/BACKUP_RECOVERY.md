# Database encryption, backup, and recovery

## Protection model

- The live PostgreSQL Docker volume is stored under `/var/lib/docker` on the
  host's LUKS-encrypted root volume. Database files are encrypted while the
  machine is powered off or the LUKS volume is locked.
- PostgreSQL is reachable only through Docker's private `backend` network; it
  has no published host port.
- Nightly database and media backups use OpenPGP symmetric encryption with
  AES-256. Each completed backup includes SHA-256 checksums and is validated
  immediately after creation.
- Django passwords use one-way password hashing and are not stored as plain
  text.

LUKS and backup encryption do not protect data after an attacker has gained
root access to the unlocked, running host. Keep the operating system patched,
limit SSH access, and protect administrative credentials.

## Encryption key

The backup key is stored at:

```text
/home/itpwu/.config/pwu-archive/backup.key
```

It must remain mode `0600`. Keep at least one offline copy in a password
manager or encrypted removable drive. Do not store an off-site backup and its
only key copy in the same location. Losing the key makes every encrypted
backup unrecoverable.

## Create a backup

```bash
/home/itpwu/pwu_archive/archiveproject/scripts/backup.sh
```

Backups are written below `/home/itpwu/pwu_archive/backups`. A backup is usable
only when its directory contains `COMPLETE`.

## Verify a backup without changing data

```bash
/home/itpwu/pwu_archive/archiveproject/scripts/restore.sh \
  /home/itpwu/pwu_archive/backups/YYYY-MM-DD_HH-MM-SS \
  --verify-only
```

Run this regularly and after copying a backup to another device.

## Restore

```bash
/home/itpwu/pwu_archive/archiveproject/scripts/restore.sh \
  /home/itpwu/pwu_archive/backups/YYYY-MM-DD_HH-MM-SS
```

The script validates both encrypted archives before asking for confirmation.
It creates one final safety backup, then stops the web services, replaces the
database and media volume, runs pending migrations, and restarts the services.
Older OpenSSL `.enc` backups remain supported. If the current database is too
damaged to create the safety backup, set `RESTORE_SKIP_SAFETY_BACKUP=true` only
after confirming that the selected historical backup passes `--verify-only`.

Test recovery periodically on a separate host. A backup is not proven until a
restore test succeeds.
