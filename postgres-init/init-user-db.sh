set -e

echo "[SQL INIT] Configurando accesos para el entorno corporativo de alta concurrencia..."

psql -v ON_ERROR_STOP=1 --username "$POSTGRES_USER" --dbname "$POSTGRES_DB" <<-EOSQL
    DO \$$
    BEGIN
        IF NOT EXISTS (SELECT FROM pg_catalog.pg_roles WHERE rolname = '$APP_DB_USER') THEN
            CREATE ROLE $APP_DB_USER WITH LOGIN PASSWORD '$APP_DB_PASS';
        END IF;
    END
    \$$;
    
    ALTER ROLE $APP_DB_USER WITH SUPERUSER; -- Concede permisos totales para gestionar migraciones de Django
    GRANT ALL PRIVILEGES ON DATABASE $APP_DB_NAME TO $APP_DB_USER;
EOSQL

echo "[SQL INIT] Usuario '$APP_DB_USER' sincronizado con éxito."
