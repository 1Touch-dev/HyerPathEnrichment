#!/bin/bash
set -euo pipefail
export MLX_EMAIL='james97deller@gmail.com'
export MLX_PASSWORD='ZlatanIDV1!'
export MLX_FOLDER_ID='66382e40-565d-4a0d-bde5-10bb41ee5fdb'
export MLX_WORKSPACE_ID='ce8ce509-3733-4f84-82c8-102c08a8da87'
export MLX_PROFILE_ID='dc015763-a26a-458e-a4e1-fb9fa9cf58d7'

/tmp/mlxverify-venv/bin/python3 /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/scripts/_tmp_retry_start.py
