#!/bin/bash
# kailog.org one-time setup, run from CloudShell: private site bucket + CloudFront (OAC) + ACM + Route 53
# (same setup as reportcheck.org and brightpost.org), plus a private, versioned records bucket.
# Content goes up with scripts/publish.sh, not here.
set -euo pipefail
ACCT=$(aws sts get-caller-identity --query Account --output text)
D=kailog.org; B=kailog-site-$ACCT; R=us-east-2; REC=kailog-records-$ACCT
ZONE=$(aws route53 list-hosted-zones-by-name --dns-name $D --query "HostedZones[?Name=='$D.'].Id | [0]" --output text | sed 's|/hostedzone/||')
echo "zone $ZONE"

# 1. Certificate (us-east-1 for CloudFront), validated through Route 53
CERT=$(aws acm list-certificates --region us-east-1 --query "CertificateSummaryList[?DomainName=='$D'].CertificateArn | [0]" --output text)
if [ "$CERT" = "None" ]; then
  CERT=$(aws acm request-certificate --region us-east-1 --domain-name $D --subject-alternative-names www.$D --validation-method DNS --tags Key=project,Value=kailog --query CertificateArn --output text)
  sleep 10
fi
echo "cert $CERT"
aws acm describe-certificate --region us-east-1 --certificate-arn $CERT --query 'Certificate.DomainValidationOptions[].ResourceRecord' --output json > /tmp/klval.json
python3 - <<'PY' > /tmp/klchg.json
import json
recs = {(r['Name'], r['Value']) for r in json.load(open('/tmp/klval.json')) if r}
print(json.dumps({"Changes": [{"Action": "UPSERT", "ResourceRecordSet": {"Name": n, "Type": "CNAME", "TTL": 300, "ResourceRecords": [{"Value": v}]}} for n, v in recs]}))
PY
aws route53 change-resource-record-sets --hosted-zone-id $ZONE --change-batch file:///tmp/klchg.json --query ChangeInfo.Status --output text
echo "waiting for the certificate..."
aws acm wait certificate-validated --region us-east-1 --certificate-arn $CERT
echo "cert ISSUED"

# 2. Bucket
aws s3api head-bucket --bucket $B 2>/dev/null || aws s3api create-bucket --bucket $B --region $R --create-bucket-configuration LocationConstraint=$R >/dev/null
aws s3api put-public-access-block --bucket $B --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --bucket $B --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-bucket-tagging --bucket $B --tagging 'TagSet=[{Key=project,Value=kailog}]'

# 2b. Records bucket: private, encrypted, versioned (every overwrite keeps the old version), never public
aws s3api head-bucket --bucket $REC 2>/dev/null || aws s3api create-bucket --bucket $REC --region $R --create-bucket-configuration LocationConstraint=$R >/dev/null
aws s3api put-public-access-block --bucket $REC --public-access-block-configuration BlockPublicAcls=true,IgnorePublicAcls=true,BlockPublicPolicy=true,RestrictPublicBuckets=true
aws s3api put-bucket-encryption --bucket $REC --server-side-encryption-configuration '{"Rules":[{"ApplyServerSideEncryptionByDefault":{"SSEAlgorithm":"AES256"}}]}'
aws s3api put-bucket-versioning --bucket $REC --versioning-configuration Status=Enabled
aws s3api put-bucket-tagging --bucket $REC --tagging 'TagSet=[{Key=project,Value=kailog}]'

# 3. CloudFront: OAC + the same strict headers policy as reportcheck.org
OAC=$(aws cloudfront list-origin-access-controls --query "OriginAccessControlList.Items[?Name=='kailog-site-oac'].Id | [0]" --output text)
[ "$OAC" = "None" ] && OAC=$(aws cloudfront create-origin-access-control --origin-access-control-config Name=kailog-site-oac,SigningProtocol=sigv4,SigningBehavior=always,OriginAccessControlOriginType=s3 --query OriginAccessControl.Id --output text)
HP=$(aws cloudfront list-response-headers-policies --type custom --query "ResponseHeadersPolicyList.Items[?ResponseHeadersPolicy.ResponseHeadersPolicyConfig.Name=='reportcheck-site-headers'].ResponseHeadersPolicy.Id | [0]" --output text)
echo "oac $OAC headers $HP"
DIST=$(aws cloudfront list-distributions --query "DistributionList.Items[?Aliases.Items && contains(Aliases.Items, '$D')].Id | [0]" --output text)
if [ "$DIST" = "None" ]; then
cat > /tmp/kldist.json <<EOF
{"CallerReference":"kailog-$(date +%s)","Aliases":{"Quantity":2,"Items":["$D","www.$D"]},"DefaultRootObject":"index.html",
"Origins":{"Quantity":1,"Items":[{"Id":"s3","DomainName":"$B.s3.$R.amazonaws.com","OriginAccessControlId":"$OAC","S3OriginConfig":{"OriginAccessIdentity":""}}]},
"DefaultCacheBehavior":{"TargetOriginId":"s3","ViewerProtocolPolicy":"redirect-to-https","Compress":true,
 "AllowedMethods":{"Quantity":2,"Items":["GET","HEAD"],"CachedMethods":{"Quantity":2,"Items":["GET","HEAD"]}},
 "CachePolicyId":"658327ea-f89d-4fab-a63d-7e88639e58f6","ResponseHeadersPolicyId":"$HP"},
"CustomErrorResponses":{"Quantity":1,"Items":[{"ErrorCode":403,"ResponsePagePath":"/404.html","ResponseCode":"404","ErrorCachingMinTTL":60}]},
"Comment":"kailog.org","Enabled":true,"PriceClass":"PriceClass_100","HttpVersion":"http2and3","IsIPV6Enabled":true,
"ViewerCertificate":{"ACMCertificateArn":"$CERT","SSLSupportMethod":"sni-only","MinimumProtocolVersion":"TLSv1.2_2021"}}
EOF
DIST=$(aws cloudfront create-distribution --distribution-config file:///tmp/kldist.json --query Distribution.Id --output text)
fi
CFD=$(aws cloudfront get-distribution --id $DIST --query Distribution.DomainName --output text)
echo "dist $DIST $CFD"

# 4. Only this distribution may read the bucket
cat > /tmp/klpol.json <<EOF
{"Version":"2012-10-17","Statement":[{"Sid":"CloudFrontOnly","Effect":"Allow","Principal":{"Service":"cloudfront.amazonaws.com"},"Action":"s3:GetObject","Resource":"arn:aws:s3:::$B/*","Condition":{"StringEquals":{"AWS:SourceArn":"arn:aws:cloudfront::$ACCT:distribution/$DIST"}}}]}
EOF
aws s3api put-bucket-policy --bucket $B --policy file:///tmp/klpol.json

# 5. DNS: apex and www as aliases to CloudFront (A + AAAA)
python3 - "$CFD" <<'PY' > /tmp/kldns.json
import json, sys
cfd = sys.argv[1]
ch = [{"Action": "UPSERT", "ResourceRecordSet": {"Name": n, "Type": t, "AliasTarget": {"HostedZoneId": "Z2FDTNDATAQYW2", "DNSName": cfd, "EvaluateTargetHealth": False}}}
      for n in ("kailog.org.", "www.kailog.org.") for t in ("A", "AAAA")]
print(json.dumps({"Changes": ch}))
PY
aws route53 change-resource-record-sets --hosted-zone-id $ZONE --change-batch file:///tmp/kldns.json --query ChangeInfo.Status --output text
echo "DONE dist=$DIST cfd=$CFD"
