#!/bin/bash
# Test script for embedding worker fix

cd /mnt/g/ThunderMarketingCorp/HyerEnrichment/backend/docker

echo "=== Step 1: Rebuild Workers ==="
sudo docker compose -f docker-compose.yml -f docker-compose.foundation.yml --env-file ../.env.production build worker-document worker-embedding

echo -e "\n=== Step 2: Restart Workers ==="
sudo docker compose -f docker-compose.yml -f docker-compose.foundation.yml --env-file ../.env.production up -d worker-document worker-embedding

echo -e "\n=== Step 3: Wait for Workers to Start ==="
sleep 5

echo -e "\n=== Step 4: Delete Existing Test Document ==="
sudo docker exec docker-postgres-1 psql -U hyrepath -d hyrepath -c \
  "DELETE FROM document_embeddings WHERE document_id IN (SELECT id FROM candidate_documents WHERE original_filename = 'sample_cv.pdf');
   DELETE FROM candidate_documents WHERE original_filename = 'sample_cv.pdf';"

echo -e "\n=== Step 5: Upload Fresh Document ==="
RESPONSE=$(curl -s -X POST http://localhost:8000/api/documents/upload \
  -b cookies.txt \
  -F "file=@../tests/fixtures/sample_cv.pdf")

echo "$RESPONSE" | jq '.'
DOC_ID=$(echo "$RESPONSE" | jq -r '.data.document_id')

echo -e "\nDocument ID: $DOC_ID"

echo -e "\n=== Step 6: Wait for Processing ==="
sleep 15

echo -e "\n=== Step 7: Check Results ==="
sudo docker exec docker-postgres-1 psql -U hyrepath -d hyrepath -c \
  "SELECT
     COUNT(*) as embedding_count,
     MIN(chunk_index) as first_chunk,
     MAX(chunk_index) as last_chunk,
     AVG(token_count)::int as avg_tokens
   FROM document_embeddings
   WHERE document_id = '$DOC_ID';"

echo -e "\n=== Step 8: Check Worker Logs ==="
echo "Document Worker (last 10 lines):"
sudo docker logs docker-worker-document-1 --tail=10

echo -e "\nEmbedding Worker (last 20 lines):"
sudo docker logs docker-worker-embedding-1 --tail=20

echo -e "\n=== Test Complete ==="
