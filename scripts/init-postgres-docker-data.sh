#!/bin/sh

# sh scripts/start-docker-compose-deps.sh
# 先启动 docker-compose-deps.yml 后 langfarm-python-sdk-langfuse-1 会初始化 langfuse 相关表结构。
# 体验 langfarm-python-sdk，需要初始化本示例的数据。仅用于本地 docker compose 环境的测试。
docker exec langfarm-python-sdk-postgres-1 psql -U postgres -w postgres -f /init_data.sql
