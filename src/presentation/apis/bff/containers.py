from dependency_injector import containers, providers
from sqlalchemy.orm import sessionmaker

from application.use_cases.complete_new_password import CompleteNewPasswordUseCase
from application.use_cases.confirm_sign_up import ConfirmSignUpUseCase
from application.use_cases.reset_password import ConfirmPasswordResetUseCase, RequestPasswordResetUseCase
from application.use_cases.sign_in import SignInUseCase
from application.use_cases.sign_up import SignUpUseCase
from infrastructure.authentication.cognito import CognitoAuthenticationEngine
from infrastructure.config.settings import DatabaseSettings, Settings
from infrastructure.persistence.database import create_database_engine
from infrastructure.persistence.user_repository import SqlAlchemyUserRepository


class Container(containers.DeclarativeContainer):


    settings = providers.Singleton(Settings)

    database_settings = providers.Singleton(DatabaseSettings)

    database_engine = providers.Singleton(
        create_database_engine,
        database_url=database_settings.provided.DATABASE_URL.get_secret_value.call(),
    )

    session_factory = providers.Singleton(
        sessionmaker,
        bind=database_engine,
        expire_on_commit=False,
    )

    user_repository = providers.Factory(
        SqlAlchemyUserRepository,
        session_factory=session_factory,
    )

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

    sign_up_use_case = providers.Factory(
        SignUpUseCase,
        authentication_engine=authentication_engine,
        user_repository=user_repository,
    )

    confirm_sign_up_use_case = providers.Factory(
        ConfirmSignUpUseCase,
        authentication_engine=authentication_engine,
    )

    complete_new_password_use_case = providers.Factory(
        CompleteNewPasswordUseCase,
        authentication_engine=authentication_engine,
    )

    request_password_reset_use_case = providers.Factory(
        RequestPasswordResetUseCase,
        authentication_engine=authentication_engine,
    )

    confirm_password_reset_use_case = providers.Factory(
        ConfirmPasswordResetUseCase,
        authentication_engine=authentication_engine,
    )