#!/bin/bash
# Complete test for embedding worker with ORM fix

cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

echo "=========================================="
echo "EMBEDDING WORKER COMPLETE TEST"
echo "=========================================="

echo -e "\n=== Step 1: Rebuild Embedding Worker ==="
sudo docker compose -f docker-compose.yml -f docker-compose.foundation.yml --env-file ../.env.production build worker-embedding

echo -e "\n=== Step 2: Restart Embedding Worker ==="
sudo docker compose -f docker-compose.yml -f docker-compose.foundation.yml --env-file ../.env.production up -d worker-embedding

echo -e "\n=== Step 3: Wait for Worker to Start ==="
sleep 5

echo -e "\n=== Step 4: Clean Up Old Test Data ==="
sudo docker exec docker-postgres-1 psql -U hyrepath -d hyrepath -c \
  "DELETE FROM document_embeddings WHERE document_id IN (SELECT id FROM candidate_documents WHERE original_filename = 'sample_cv.pdf');
   DELETE FROM candidate_documents WHERE original_filename = 'sample_cv.pdf';"

echo -e "\n=== Step 5: Upload Fresh Document ==="
RESPONSE=$(curl -s -X POST http://localhost:8000/api/documents/upload \
  -b cookies.txt \
  -F "file=@../tests/fixtures/sample_cv.pdf")

echo "$RESPONSE" | jq '.'
DOC_ID=$(echo "$RESPONSE" | jq -r '.data.document_id')
JOB_ID=$(echo "$RESPONSE" | jq -r '.data.job_id')

echo -e "\nDocument ID: $DOC_ID"
echo "Job ID: $JOB_ID"

echo -e "\n=== Step 6: Wait for Processing (20 seconds) ==="
sleep 20

echo -e "\n=== Step 7: Check Embeddings ==="
sudo docker exec docker-postgres-1 psql -U hyrepath -d hyrepath -c \
  "SELECT
     COUNT(*) as total_embeddings,
     MIN(chunk_index) as first_chunk,
     MAX(chunk_index) as last_chunk,
     AVG(token_count)::int as avg_tokens,
     MAX(created_at) as latest_created
   FROM document_embeddings
   WHERE document_id = '$DOC_ID';"

echo -e "\n=== Step 8: Check Document Status ==="
sudo docker exec docker-postgres-1 psql -U hyrepath -d hyrepath -c \
  "SELECT processing_status FROM candidate_documents WHERE id = '$DOC_ID';"

echo -e "\n=== Step 9: Check for Errors in Logs ==="
echo "Last 30 lines of embedding worker logs:"
sudo docker logs docker-worker-embedding-1 --tail=30

echo -e "\n=========================================="
echo "TEST COMPLETE"
echo "=========================================="

# Check if embeddings were created
EMBED_COUNT=$(sudo docker exec docker-postgres-1 psql -U hyrepath -d hyrepath -t -c \
  "SELECT COUNT(*) FROM document_embeddings WHERE document_id = '$DOC_ID';")

if [ "$EMBED_COUNT" -gt 0 ]; then
    echo -e "\n✅ SUCCESS! Generated $EMBED_COUNT embeddings"
    echo "The embedding worker is now functioning correctly!"
else
    echo -e "\n❌ FAILED! No embeddings generated"
    echo "Check the logs above for errors"
    exit 1
fi
