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

Returns `201` with `user_id`, `user_confirmed`, and optional masked
`confirmation_destination` and `confirmation_delivery_medium`. It does not
return authentication tokens. When `user_confirmed` is false, complete Cognito's
signup-confirmation flow with `POST /auth/sign-up/confirm` before signing in.

Configure the user pool to verify email during signup. Submit the code sent by
Cognito along with the same email address used to register. No access token is
required:

```sh
curl -X POST http://localhost:5002/auth/sign-up/confirm \
	-H 'Content-Type: application/json' \
	-d '{"email":"user@example.com","code":"123456"}'
```

Successful confirmation returns `200`; sign in separately with the email and
password. Invalid or expired codes return `400`; email alias conflicts return
`409`; throttling returns `429`. Confirmation never forcibly transfers an email
alias from another account. Do not log confirmation codes.

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

## Dependency Injection

`src/containers.py` defines the `dependency-injector` container for the API:
settings are a lazy singleton, while the authentication engine and sign-in use
case use factory providers. The FastAPI entry point wires the route module and
stores the container at `app.state.container`. Restart the application after
changing environment settings that have already been loaded.

Tests can replace dependencies using provider overrides, for example
`with app.state.container.authentication_engine.override(fake_engine):`.
Domain interfaces and use cases do not depend on the container or FastAPI.

## Tests

```sh
python -m pip install -r requirements-dev.txt
PYTHONPATH=src python -m unittest discover -s tests/presentation -p 'test_*.py' -v
```