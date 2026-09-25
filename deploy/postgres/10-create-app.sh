#!/bin/sh
set -eu

# 仅在新的数据库卷首次初始化时执行；应用账号不使用 postgres 超级用户。
psql --username "$POSTGRES_USER" --dbname postgres --set ON_ERROR_STOP=1 \
    --set app_user="$DB_USER" --set app_password="$DB_PASSWORD" \
    --set app_database="$DB_NAME" <<'SQL'
CREATE ROLE :"app_user" WITH LOGIN PASSWORD :'app_password' NOSUPERUSER NOCREATEDB NOCREATEROLE;
CREATE DATABASE :"app_database" OWNER :"app_user";
SQL

