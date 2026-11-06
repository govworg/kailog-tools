#!/bin/bash
# Weekly Pulse update for kailog.org. Run from CloudShell inside the kailog-site folder.
#   1. Refuses to publish if the new record rewrites or drops any published entry (R8).
#   2. Builds the page and Pulse, timestamps the chain head, rebuilds with the proofs.
#   3. Uploads the private record (records bucket) and the public site.
set -euo pipefail
cd "$(dirname "$0")/.."
ACCT=$(aws sts get-caller-identity --query Account --output text); R=us-east-2
SITE_B=kailog-site-$ACCT; REC_B=kailog-records-$ACCT

# 1. Append-only check against the last published record
if aws s3 cp s3://$REC_B/kailog.jsonl /tmp/kailog-published.jsonl --only-show-errors 2>/dev/null; then
  python3 tools/chain.py extends /tmp/kailog-published.jsonl records/kailog.jsonl
else
  echo "no published record yet: first publish"; python3 tools/chain.py verify records/kailog.jsonl
fi

# 2. Earlier proofs, build, timestamp, rebuild
aws s3 sync s3://$SITE_B/pulse/proofs site/pulse/proofs --only-show-errors 2>/dev/null || true
python3 tools/build.py
scripts/stamp.sh "site/pulse/proofs/head-$(date -u +%F).txt"
python3 tools/build.py

# 3. Upload: private record first, then the public site
aws s3 cp records/kailog.jsonl s3://$REC_B/kailog.jsonl --sse AES256 --only-show-errors
up() { aws s3 cp "$1" "s3://$SITE_B/${1#site/}" --content-type "$2" --cache-control "$3" --only-show-errors; }
find site -type f | while read -r f; do
  case "$f" in
    *.html) up "$f" 'text/html; charset=utf-8' 'public, max-age=300' ;;
    *.css) up "$f" 'text/css' 'public, max-age=300' ;;
    *.js) up "$f" 'text/javascript' 'public, max-age=300' ;;
    *.json) up "$f" 'application/json' 'public, max-age=300' ;;
    *.xml) up "$f" 'application/atom+xml' 'public, max-age=300' ;;
    *.png) up "$f" 'image/png' 'public, max-age=86400' ;;
    *.svg) up "$f" 'image/svg+xml' 'public, max-age=86400' ;;
    *.woff2) up "$f" 'font/woff2' 'public, max-age=31536000, immutable' ;;
    *.md) up "$f" 'text/markdown; charset=utf-8' 'public, max-age=300' ;;
    *.ots|*.tsr) up "$f" 'application/octet-stream' 'public, max-age=300' ;;
    *) up "$f" 'text/plain; charset=utf-8' 'public, max-age=300' ;;
  esac
done

DIST=$(aws cloudfront list-distributions --query "DistributionList.Items[?Aliases.Items && contains(Aliases.Items, 'kailog.org')].Id | [0]" --output text)
aws cloudfront create-invalidation --distribution-id "$DIST" --paths '/*' --query Invalidation.Status --output text
echo "PUBLISHED: https://kailog.org"
