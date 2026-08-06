#!/bin/bash
# Run pytest with local PostgreSQL (Docker)

set -e

echo "Starting PostgreSQL and Redis with Docker Compose..."
cd docker
docker compose -f docker-compose.yml up -d postgres redis

echo "Waiting for PostgreSQL to be ready..."
sleep 5

# Check if PostgreSQL is healthy
until docker exec hyer-postgres pg_isready -U hyrepath; do
  echo "Waiting for PostgreSQL..."
  sleep 2
done

echo "Running migrations..."
cd ..
python -m alembic upgrade head

echo "Running tests with PostgreSQL..."
export $(cat .env.test.postgres | xargs)
python -m pytest tests/test_foundation_week1_integration.py -v --tb=short

echo "Tests complete!"
