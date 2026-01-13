#!/usr/bin/env bash

# This scripts assumes you are alredy running as the root user
set -e

# Validate arguments
if [ "$#" -ne 2 ]; then
  echo "Usage: $0 <user> <cmc_ip>"
  exit 1
fi

CMC_USER="$1"
CMC_IP="$2"

BACKUPS_DIR="/data/backups"
REMOTE_DIR="/data/tmp"

# echo "[*] Listing existing backups:"
# ls -lht

ls -t  "$BACKUPS_DIR"/*.nozomi_backup 2>/dev/null | head -n 1

latest_backup=$(ls -t  "$BACKUPS_DIR"/*.nozomi_backup 2>/dev/null | head -n 1)

if [ -n "$latest_backup" ]; then
  echo "[*] Found latest backup: $latest_backup"
  # Here you'd skip the prompt for automation
  echo "[*] Generating new backup anyway..."
else
  echo "[*] No backups found. Generating one..."
fi

# Run the backup and capture its output
backup_output=$(n2os-fullbackup -d "$BACKUPS_DIR")

echo "$backup_output"
echo "[*] backup created (no errors)"

# Extract filename
# we have to use seed beacuse nozomi grep command does not support -p
backup_file=$(echo "$backup_output" | awk '/Save[ \t]+.*\.nozomi_backup/ { for (i=1;i<=NF;i++) if ($i ~ /\.nozomi_backup$/) print $i }')

# backup_file=$(echo "$backup_output" | grep -oP '(?<=Save\s+).+?\.nozomi_backup')

# Extract hash
backup_hash=$(
  echo "$backup_output" | awk '
    /Starting auditd\./ {
      getline  # move to the next line
      # check if the next line is a 128-character hex string (case-insensitive)
      if (tolower($0) ~ /^[a-f0-9]{128}$/) {
        print $0
      }
    }
  '
)

echo "[*] Backup file: $backup_file"
echo "[*] Backup hash: $backup_hash"

echo "copy to CMC"
if [ -n "$backup_file" ]; then
  echo "[*] Copying \"$backup_file\" to ${CMC_USER}@${CMC_IP}..."

  if scp "$backup_file" "${CMC_USER}@${CMC_IP}:${REMOTE_DIR}/"; then
    echo "[*] Backup file successfully copied to ${CMC_USER}@${CMC_IP}:${REMOTE_DIR}/$(basename "$backup_file")"
  else
    echo "[!] Failed to copy backup file to remote host."
    exit 1
  fi

else
  echo "[!] Could not determine backup file name."
  exit 1
fi