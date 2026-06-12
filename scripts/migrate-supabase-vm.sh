#!/usr/bin/env bash
#
# Apply Supabase migrations to the self-hosted DB on the GCE VM, bypassing the
# Supavisor pooler by exec'ing into the raw Postgres container.
#
# Why this (and not the entrypoint boot-migration): the self-hosted stack
# exposes only the pooler (supabase-pooler / supavisor) on the public :5432
# (which requires a tenant-id in the username) and Kong on :8000. The raw
# Postgres (supabase-db) listens only on the VM's internal docker network, so
# neither Cloud Run nor a laptop can psql it directly. Running DDL inside the
# container via `docker exec` is the reliable path for this topology.
#
# This is the canonical way to forward-migrate the demo DB after merging
# schema changes. Migrations are idempotent, so re-running is safe.
#
# Usage:
#   scripts/migrate-supabase-vm.sh                 # apply the batch >= FROM_VERSION
#   FROM_VERSION=0 scripts/migrate-supabase-vm.sh  # apply ALL (fresh DB only)
#
# Env (overridable):
#   GCP_PROJECT   default aijolotbannerstudio
#   VM_NAME       default supabase-vm
#   VM_ZONE       default us-central1-a
#   DB_CONTAINER  default supabase-db
#   FROM_VERSION  default 20260603210001 — apply migrations with version >= this.
#                 The default skips the legacy, non-idempotent baseline
#                 (<= 20260603210000) already present on the demo, applying only
#                 the idempotent 20260608+ batch. Set 0 for a brand-new DB.
set -euo pipefail

PROJECT="${GCP_PROJECT:-aijolotbannerstudio}"
VM="${VM_NAME:-supabase-vm}"
ZONE="${VM_ZONE:-us-central1-a}"
CONTAINER="${DB_CONTAINER:-supabase-db}"
FROM="${FROM_VERSION:-20260603210001}"

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
MIGRATIONS="$SCRIPT_DIR/../supabase/migrations"
REMOTE_DIR="/tmp/aijolot-migrations"

if ! command -v gcloud >/dev/null 2>&1; then
  echo "migrate-supabase-vm: gcloud not found on PATH" >&2
  exit 1
fi

echo "migrate-supabase-vm: copying migrations to $VM:$REMOTE_DIR ..."
gcloud compute scp --recurse --zone "$ZONE" --project "$PROJECT" \
  "$MIGRATIONS" "$VM:$REMOTE_DIR"

echo "migrate-supabase-vm: applying migrations (version >= $FROM) in container $CONTAINER ..."
gcloud compute ssh "$VM" --zone "$ZONE" --project "$PROJECT" --command "
set -e
for f in \$(ls $REMOTE_DIR/*.sql | sort); do
  v=\$(basename \"\$f\" | cut -d_ -f1)
  if [ \"\$v\" -ge $FROM ]; then
    echo \"=== \$(basename \"\$f\") ===\"
    sudo docker exec -i $CONTAINER psql -U postgres -d postgres -v ON_ERROR_STOP=1 < \"\$f\"
  fi
done
echo '=== campaign_revisions_status_check ==='
sudo docker exec $CONTAINER psql -U postgres -d postgres -c \"select pg_get_constraintdef(oid) from pg_constraint where conname='campaign_revisions_status_check';\"
"
echo "migrate-supabase-vm: done"
