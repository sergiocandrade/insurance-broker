
# Real secrets (GOOGLE_MAPS_API_KEY) live in docker/.env, gitignored —
# see docker/.env.example. `-include` so a missing file doesn't break other targets.
-include docker/.env
export

SAM_ARCH := $(shell uname -m | sed 's/x86_64/x86_64/;s/aarch64/arm64/;s/arm64/arm64/')

run:
	docker compose -f docker/docker-compose-development.yaml up -d

generate-migration:
	docker build -t insurance-broker-dev \
	--build-arg ALEMBIC_INI_PATH_ARG="alembic/alembic.ini" \
	--build-arg ALEMBIC_CMD_ARG="revision --autogenerate -m '${message}'" \
	-f docker/Dockerfile_Alembic . \
	&& docker run -v ./src:/app \
	--add-host=host.docker.internal:host-gateway \
	-e DB_HOST=host.docker.internal \
	-e DB_PORT=3310 \
	-e DB_NAME=insurance-broker \
	-e DB_USER=app_user \
	-e DB_PASSWORD=app_password \
	--rm insurance-broker-dev 


run-migration:
	docker build -t insurance-broker-dev \
	--build-arg ALEMBIC_INI_PATH_ARG="alembic/alembic.ini" \
	--build-arg ALEMBIC_CMD_ARG="upgrade head" \
	-f docker/Dockerfile_Alembic . \
	&& docker run -v ./src:/app \
	--add-host=host.docker.internal:host-gateway \
	-e DB_HOST=host.docker.internal \
	-e DB_PORT=3310 \
	-e DB_NAME=insurance-broker \
	-e DB_USER=app_user \
	-e DB_PASSWORD=app_password \
	--rm insurance-broker-dev

# Uso: make downgrade-migration rev=<revision|-1|base>
downgrade-migration:
	docker build -t insurance-broker-dev \
	--build-arg ALEMBIC_INI_PATH_ARG="alembic/alembic.ini" \
	--build-arg ALEMBIC_CMD_ARG="downgrade ${rev}" \
	-f docker/Dockerfile_Alembic . \
	-e DATABASE_URL='${DATABASE_URL:-mysql+pymysql://app_user:app_password@insurance-broker-mysql-local:3306/insurance-broker?charset=utf8mb4}' \
	--add-host=host.docker.internal:host-gateway \
	-e DB_HOST=host.docker.internal \
	-e DB_PORT=3310 \
	-e DB_NAME=insurance-broker \
	-e DB_USER=app_user \
	-e DB_PASSWORD=app_password \
	--rm insurance-broker-dev

build-bff:
	docker build -t insurance-broker-bff -f docker/Dockerfile_BFF .

init-db:
	docker compose -f docker/docker-compose-development.yaml up -d --wait insurance-broker-mysql-local

run-bff:
	docker compose -f docker/docker-compose-development.yaml up insurance-broker-bff