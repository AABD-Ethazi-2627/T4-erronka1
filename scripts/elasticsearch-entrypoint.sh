#!/usr/bin/env bash
set -euo pipefail

# Desktop exposes Windows bind mounts as 0777. Elasticsearch's file_env rejects
# that mode, so copy just this password to container tmpfs with Unix permissions.
umask 077
cp /run/secrets/elastic_password /run/cnc-secrets/elastic_password
chmod 600 /run/cnc-secrets/elastic_password
export ELASTIC_PASSWORD_FILE=/run/cnc-secrets/elastic_password
exec /usr/local/bin/docker-entrypoint.sh "$@"
