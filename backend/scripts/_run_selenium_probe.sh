#!/usr/bin/env bash
set -euo pipefail
sed -i 's/\r$//' /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/scripts/_tier1_selenium_probe.sh
export MULTILOGIN_HOST_IP=$(ip route show default | awk '{print $3}')
echo "exported MULTILOGIN_HOST_IP=$MULTILOGIN_HOST_IP"
bash /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/scripts/_tier1_selenium_probe.sh
