#!/bin/bash
# Script to rebuild PostgreSQL with pgvector and restart services

set -e

echo "==> Rebuilding PostgreSQL image with pgvector (skipping bitcode)..."
docker compose build postgres --no-cache

echo ""
echo "==> Stopping services..."
docker compose down

echo ""
echo "==> Starting services with .env.production..."
docker compose --env-file ../.env.production up -d

echo ""
echo "==> Waiting for services to be healthy..."
sleep 10

echo ""
echo "==> Checking container status..."
docker compose ps

echo ""
echo "==> Checking PostgreSQL logs for pgvector extension..."
docker compose logs postgres | tail -20

echo ""
echo "==> Done! PostgreSQL should now have pgvector extension installed."
echo "==> Run 'docker compose logs postgres' to see full logs if needed."
