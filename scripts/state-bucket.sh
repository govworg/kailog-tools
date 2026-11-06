#!/bin/bash
# One-time: private, versioned bucket for Kai's encrypted daily state; every object deleted after 365 days.
set -euo pipefail
ACCT=$(aws sts get-caller-identity --query Account --output text); R=us-east-2; B=kai-state-$ACCT
aws s3api head-bucket --bucket $B 2>/dev/null || aws s3api create-bucket --bucket $B --region $R --create-bucket-configuration LocationConstraint=$R >/dev/null
aws s3api put-public-access-block --bucket $B --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --bucket $B --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-bucket-versioning --bucket $B --versioning-configuration Status=Enabled
aws s3api put-bucket-lifecycle-configuration --bucket $B --lifecycle-configuration '{"Rules":[{"ID":"delete-after-1-year","Status":"Enabled","Filter":{},"Expiration":{"Days":365},"NoncurrentVersionExpiration":{"NoncurrentDays":365},"AbortIncompleteMultipartUpload":{"DaysAfterInitiation":7}}]}'
aws s3api put-bucket-tagging --bucket $B --tagging 'TagSet=[{Key=project,Value=kai-state}]'
echo "DONE $B: private, encrypted at rest, versioned, objects deleted after 365 days"
