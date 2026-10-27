
# Real secrets (GOOGLE_MAPS_API_KEY) live in docker/.env, gitignored —
# see docker/.env.example. `-include` so a missing file doesn't break other targets.
-include docker/.env
export

SAM_ARCH := $(shell uname -m | sed 's/x86_64/x86_64/;s/aarch64/arm64/;s/arm64/arm64/')

run:
	docker compose -f docker/docker-compose-development.yaml up -d

generate-migration:
	docker build -t fleet-migrations-dev \
	--build-arg ALEMBIC_INI_PATH_ARG="alembic/alembic.ini" \
	--build-arg ALEMBIC_CMD_ARG="revision --autogenerate -m '${message}'" \
	-f docker/Dockerfile_Alembic . \
	&& docker run -v ./src:/app \
	--add-host=host.docker.internal:host-gateway \
	-e DB_HOST=host.docker.internal \
	-e DB_PORT=3307 \
	-e DB_NAME=fleet \
	-e DB_USER=app_user \
	-e DB_PASSWORD=app_password \
	--rm fleet-migrations-dev 


run-migration:
	docker build -t fleet-migrations-dev \
	--build-arg ALEMBIC_INI_PATH_ARG="alembic/alembic.ini" \
	--build-arg ALEMBIC_CMD_ARG="upgrade head" \
	-f docker/Dockerfile_Alembic . \
	&& docker run -v ./src:/app \
	--add-host=host.docker.internal:host-gateway \
	-e DB_HOST=host.docker.internal \
	-e DB_PORT=3307 \
	-e DB_NAME=fleet \
	-e DB_USER=app_user \
	-e DB_PASSWORD=app_password \
	--rm fleet-migrations-dev

# Uso: make downgrade-migration rev=<revision|-1|base>
downgrade-migration:
	docker build -t fleet-migrations-dev \
	--build-arg ALEMBIC_INI_PATH_ARG="alembic/alembic.ini" \
	--build-arg ALEMBIC_CMD_ARG="downgrade ${rev}" \
	-f docker/Dockerfile_Alembic . \
	&& docker run -v ./src:/app \
	--add-host=host.docker.internal:host-gateway \
	-e DB_HOST=host.docker.internal \
	-e DB_PORT=3307 \
	-e DB_NAME=fleet \
	-e DB_USER=app_user \
	-e DB_PASSWORD=app_password \
	--rm fleet-migrations-dev

build-bff:
	docker build -t insurance-broker-bff -f docker/Dockerfile_BFF .

run-bff:
	docker compose -f docker/docker-compose-development.yaml up insurance-broker-bff