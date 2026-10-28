# sergiocandrade-insurance-broker-bff

## Run locally

```sh
python3 -m venv .venv
source .venv/bin/activate
python -m pip install -r requirements.txt
python -m uvicorn presentation.apis.bff.main:app --app-dir src --host 127.0.0.1 --port 8510 --reload
```

- Health: http://localhost:8510/health
- Swagger UI: http://localhost:8510/docs
- OpenAPI schema: http://localhost:8510/openapi.json

## Run with Docker

```sh
docker build -f docker/Dockerfile_BFF -t insurance-broker-bff .
docker run --rm -p 8510:8510 insurance-broker-bff
```

## User Database

Sign-up creates a domain user and persists it through a SQLAlchemy repository in
MySQL. The `users` table stores Cognito's user ID as its primary key, a unique
email, and a UTC creation timestamp. Passwords and tokens are never stored here.
The signup response and confirmation flow remain unchanged.

`DatabaseSettings` requires `DATABASE_URL`. Compose supplies a development URL
for the existing MySQL service; override it in the environment or `docker/.env`
for another database. Keep real database credentials in your secret manager.

Create the initial tables before accepting registrations:

```sh
make build-bff
make init-bff-db
make run-bff
```

For local Python execution against Compose's MySQL:

```sh
export DATABASE_URL='mysql+pymysql://app_user:app_password@127.0.0.1:3307/fleet?charset=utf8mb4'
PYTHONPATH=src python -m infrastructure.persistence.database
```

The schema command creates missing tables without deleting data. It is an
initial bootstrap, not a migration system for later column changes. Back up
production data and use reviewed migrations when changing an existing schema.

Cognito registration and the MySQL commit are not a distributed transaction.
The API returns success only after both complete. If MySQL fails after Cognito
creates the account, the API returns `503` and explicitly reports partial
registration. Support must reconcile the missing profile using the Cognito user
ID and email before retrying; this flow does not automatically delete the
Cognito account or store its password for recovery. Other auth endpoints do not
require database configuration.

## Cognito Sign-Up

Enable self-service sign-up on the user pool and allow the app client to write
the `email` attribute. This endpoint accepts email and password and uses the
email as the Cognito username. Email is limited to 128 characters to match the
username limit. Use the same email as `username` when signing in. Any other
required user-pool attributes must be supplied by your Cognito setup.

```sh
curl -X POST http://localhost:5002/auth/sign-up \
	-H 'Content-Type: application/json' \
	-d '{"email":"user@example.com","password":"Example-Password123!"}'
```

Returns `201` with `user_id` and `user_confirmed`. Email is automatically
confirmed during signup. The response does not contain authentication tokens;
sign in separately with the registered email and password.

Existing usernames return `409`; password-policy failures and invalid signup
details return `400`; disabled sign-up returns `403`; throttling returns `429`.
Use HTTPS in production and never log passwords. Rebuild the Docker image with
`make build-bff` to install the email-validation dependency. Local Uvicorn uses
port `8510` instead of Compose's `5002`.

## Cognito Sign-In

Enable `ALLOW_USER_PASSWORD_AUTH` on your Cognito user pool app client.
Enable the app client's `PreventUserExistenceErrors` option to avoid revealing
whether a username exists. Use HTTPS when deploying this password-based endpoint.

Configure the application environment before starting the server:

Configuration is centralized in `src/infrastructure/config/settings.py` using
Pydantic Settings and injected into the sign-in endpoint. It reads `AWS_REGION`
(falling back to `AWS_DEFAULT_REGION`), `COGNITO_CLIENT_ID`, and
`COGNITO_CLIENT_SECRET` from the environment. Empty values are treated as unset,
and the client secret is masked in the settings object's representation. All
three fields are uppercase, required, and nonempty. Environment variable names
are case-sensitive.

```sh
export AWS_REGION=us-east-1
export COGNITO_CLIENT_ID=your-app-client-id
export COGNITO_CLIENT_SECRET=your-app-client-secret
```

Use a Cognito app client with a secret and provide `COGNITO_CLIENT_SECRET` through
your environment or secret manager. The server computes Cognito's `SECRET_HASH`;
the client secret must never be sent by the frontend. A user pool ID is not
required for this authentication flow.

For Compose, these variables can also be configured in `docker/.env`, which
the Makefile loads. Rebuild the image to install the Cognito SDK:

```sh
make build-bff
make run-bff
```

Compose exposes the API at http://localhost:5002. Local Uvicorn and the direct
Docker command above use port `8510` instead.

```sh
curl -X POST http://localhost:5002/auth/sign-in \
	-H 'Content-Type: application/json' \
	-d '{"username":"user@example.com","password":"example-password"}'
```

Successful authentication returns `access_token`, `id_token`, `refresh_token`,
`token_type`, and `expires_in`. If Cognito requires MFA or a new password,
the response instead contains `challenge_name`, `challenge_parameters`, and
`session`. This endpoint does not complete challenges; the caller must not
treat a challenge response as completed authentication.

Errors return `401` for invalid credentials, `403` for required account
verification or password reset, `429` for throttling, `502` for other Cognito
errors, or `503` for missing configuration or an unavailable service.

## Current User

Retrieve the logged-in user's local profile with the Cognito access token
returned by sign-in, not the ID token. The access token must include the
`aws.cognito.signin.user.admin` scope for Cognito's `GetUser` API.

```sh
curl http://localhost:5002/auth/me \
	-H 'Authorization: Bearer YOUR_ACCESS_TOKEN'
```

Returns `id`, `email`, `external_id`, `status`, and UTC `created_at`. Cognito
validates the token before the API looks up the profile using its trusted `sub`.
The caller cannot select a different user by supplying an email or user ID.
Passwords, access tokens, and refresh tokens are not returned or cached.

Status is `REGISTERED` after sign-up or `EMAIL_CONFIRMED` after successful signup
confirmation. `COMPLETED` is reserved for the future profile-completion flow;
reading the profile does not change it. Apply pending database migrations with
`make run-migration` before using this endpoint.

Missing, invalid, expired, or revoked tokens return `401`; an authenticated user
without a local profile receives `404`. Database failures or ambiguous profiles
with the same external ID return `503` rather than choosing an arbitrary user.
Use HTTPS in production and never log bearer tokens. Local Uvicorn uses port
`8510` instead of Compose's `5002`.

## Dependency Injection

`src/presentation/apis/bff/containers.py` defines the `dependency-injector`
container for the API. Settings, the SQLAlchemy engine, and the session factory
are lazy singletons; authentication engines, user repositories, and use cases
use factory providers. Each repository write gets its own transaction and
session. The FastAPI entry point wires the route module and
stores the container at `app.state.container`. Restart the application after
changing environment settings that have already been loaded.

Tests can replace dependencies using provider overrides, for example
`with app.state.container.authentication_engine.override(fake_engine):`.
Domain interfaces and use cases do not depend on the container or FastAPI.

## Tests

```sh
python -m pip install -r requirements-dev.txt
PYTHONPATH=src python -m unittest discover -s tests/presentation -p 'test_*.py' -v
PYTHONPATH=src python -m unittest discover -s tests/infrastructure -p 'test_*.py' -v
```

Repository tests use SQLite by default and compile the schema for MySQL. Set
`TEST_MYSQL_URL` to run the MySQL integration check, which uses a temporary
`users` table visible only on the test connection and leaves persistent tables
and records unchanged.