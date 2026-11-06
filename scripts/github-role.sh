#!/bin/bash
# One-time: let the private GitHub repo publish kailog.org through OIDC (no stored AWS keys).
# Run from CloudShell:  bash scripts/github-role.sh <github-org>/<private-repo>
# Creates (only if missing): the GitHub OIDC identity provider, and role kailog-publish that
#   - can be assumed ONLY by workflows on the main branch of that one repo
#   - can write ONLY the two kailog buckets, add (not read or delete) Kai state backups,
#     and invalidate ONLY the kailog.org distribution
set -euo pipefail
REPO="${1:?usage: github-role.sh org/repo}"
ACCT=$(aws sts get-caller-identity --query Account --output text); ROLE=kailog-publish
SITE_B=kailog-site-$ACCT; REC_B=kailog-records-$ACCT
P=arn:aws:iam::$ACCT:oidc-provider/token.actions.githubusercontent.com
aws iam get-open-id-connect-provider --open-id-connect-provider-arn $P >/dev/null 2>&1 || \
  aws iam create-open-id-connect-provider --url https://token.actions.githubusercontent.com --client-id-list sts.amazonaws.com >/dev/null
DIST=$(aws cloudfront list-distributions --query "DistributionList.Items[?Aliases.Items && contains(Aliases.Items, 'kailog.org')].Id | [0]" --output text)

cat > /tmp/kl-trust.json <<EOF
{"Version":"2012-10-17","Statement":[{"Effect":"Allow","Principal":{"Federated":"$P"},"Action":"sts:AssumeRoleWithWebIdentity",
 "Condition":{"StringEquals":{"token.actions.githubusercontent.com:aud":"sts.amazonaws.com",
  "token.actions.githubusercontent.com:sub":"repo:$REPO:ref:refs/heads/main"}}}]}
EOF
cat > /tmp/kl-perms.json <<EOF
{"Version":"2012-10-17","Statement":[
 {"Sid":"SiteWrite","Effect":"Allow","Action":["s3:PutObject","s3:GetObject","s3:ListBucket"],"Resource":["arn:aws:s3:::$SITE_B","arn:aws:s3:::$SITE_B/*"]},
 {"Sid":"RecordsReadWrite","Effect":"Allow","Action":["s3:PutObject","s3:GetObject"],"Resource":"arn:aws:s3:::$REC_B/kailog.jsonl"},
 {"Sid":"StateWriteOnly","Effect":"Allow","Action":"s3:PutObject","Resource":"arn:aws:s3:::kai-state-$ACCT/*"},
 {"Sid":"Invalidate","Effect":"Allow","Action":"cloudfront:CreateInvalidation","Resource":"arn:aws:cloudfront::$ACCT:distribution/$DIST"},
 {"Sid":"FindDistribution","Effect":"Allow","Action":"cloudfront:ListDistributions","Resource":"*"}]}
EOF
aws iam get-role --role-name $ROLE >/dev/null 2>&1 || \
  aws iam create-role --role-name $ROLE --assume-role-policy-document file:///tmp/kl-trust.json --max-session-duration 3600 --tags Key=project,Value=kailog >/dev/null
aws iam update-assume-role-policy --role-name $ROLE --policy-document file:///tmp/kl-trust.json
aws iam put-role-policy --role-name $ROLE --policy-name kailog-publish --policy-document file:///tmp/kl-perms.json
echo "ROLE ARN (put it in the repo secret AWS_ROLE_ARN): arn:aws:iam::$ACCT:role/$ROLE"
