#!/usr/bin/env bash
# Discover NVIDIA Isaac Sim Development Workstation Marketplace AMI IDs.
# Prerequisite: Accept Marketplace terms in the AWS console first.
set -euo pipefail

REGION="${1:-ap-south-1}"

echo "Region: ${REGION}"
echo "Listing Marketplace AMIs matching Isaac Sim Development Workstation..."
echo

aws ec2 describe-images \
  --region "${REGION}" \
  --owners aws-marketplace \
  --filters \
    "Name=name,Values=*Isaac*Sim*Development*Workstation*" \
    "Name=state,Values=available" \
    "Name=architecture,Values=x86_64" \
  --query 'sort_by(Images,&CreationDate)[*].[CreationDate,ImageId,Name]' \
  --output table

echo
echo "Copy the newest ImageId into infra/terraform/terraform.tfvars as ami_id if auto-discover fails."
echo "Marketplace product: https://aws.amazon.com/marketplace/pp/prodview-bl35herdyozhw"
