#!/bin/sh

mkdir -p /tmp/langfarm-sdk
docker compose -f docker/docker-compose-deps.yml -p langfarm-python-sdk up -d
