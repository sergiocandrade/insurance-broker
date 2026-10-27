from dependency_injector import containers, providers

from application.use_cases.complete_new_password import CompleteNewPasswordUseCase
from application.use_cases.sign_in import SignInUseCase
from infrastructure.authentication.cognito import CognitoAuthenticationEngine
from infrastructure.config.settings import Settings


class Container(containers.DeclarativeContainer):


    settings = providers.Singleton(Settings)


    authentication_engine = providers.Factory(
        CognitoAuthenticationEngine,
        region=settings.provided.AWS_REGION,
        client_id=settings.provided.COGNITO_CLIENT_ID,
        client_secret=settings.provided.COGNITO_CLIENT_SECRET.get_secret_value.call(),
    )

    sign_in_use_case = providers.Factory(
        SignInUseCase,
        authentication_engine=authentication_engine,
    )

    complete_new_password_use_case = providers.Factory(
        CompleteNewPasswordUseCase,
        authentication_engine=authentication_engine,
    )