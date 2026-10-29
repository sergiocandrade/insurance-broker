from dependency_injector import containers, providers
from sqlalchemy.orm import sessionmaker

from application.use_cases.complete_new_password import CompleteNewPasswordUseCase
from application.use_cases.get_current_user import GetCurrentUserUseCase
from application.use_cases.get_current_brokers import GetCurrentBrokersUseCase
from application.use_cases.get_customer_details import GetCustomerDetailsUseCase
from application.use_cases.list_broker_customers import ListBrokerCustomersUseCase
from application.use_cases.list_policies import ListPoliciesUseCase
from application.use_cases.reset_password import ConfirmPasswordResetUseCase, RequestPasswordResetUseCase
from application.use_cases.sign_in import SignInUseCase
from application.use_cases.sign_up import SignUpUseCase
from domain.services.user import UserService
from domain.services.broker import BrokerService
from domain.services.customer import CustomerService
from domain.services.policy import PolicyService
from domain.services.waiting_list import WaitingListService
from infrastructure.authentication.cognito import CognitoAuthenticationEngine
from infrastructure.config.settings import DatabaseSettings, Settings
from infrastructure.persistence.sqlalchemy.database import create_database_engine
from infrastructure.persistence.sqlalchemy.repositories.user_repository import SqlAlchemyUserRepository
from infrastructure.persistence.sqlalchemy.repositories.broker_repository import SqlAlchemyBrokerRepository
from infrastructure.persistence.sqlalchemy.repositories.customer_repository import SqlAlchemyCustomerRepository
from infrastructure.persistence.sqlalchemy.repositories.policy_repository import SqlAlchemyPolicyRepository
from infrastructure.persistence.sqlalchemy.repositories.waiting_list_repository import SqlAlchemyWaitingListRepository


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

    user_service = providers.Factory(
        UserService,
        user_repository=user_repository,
    )

    broker_repository = providers.Factory(
        SqlAlchemyBrokerRepository,
        session_factory=session_factory,
    )

    broker_service = providers.Factory(
        BrokerService,
        broker_repository=broker_repository,
    )

    customer_repository = providers.Factory(
        SqlAlchemyCustomerRepository,
        session_factory=session_factory,
    )

    customer_service = providers.Factory(
        CustomerService,
        customer_repository=customer_repository,
    )

    policy_repository = providers.Factory(
        SqlAlchemyPolicyRepository,
        session_factory=session_factory,
    )

    policy_service = providers.Factory(
        PolicyService,
        policy_repository=policy_repository,
    )

    waiting_list_repository = providers.Factory(
        SqlAlchemyWaitingListRepository,
        session_factory=session_factory,
    )

    waiting_list_service = providers.Factory(
        WaitingListService,
        waiting_list_repository=waiting_list_repository,
    )

    authentication_engine = providers.Factory(
        CognitoAuthenticationEngine,
        region=settings.provided.AWS_REGION,
        client_id=settings.provided.COGNITO_CLIENT_ID,
        client_secret=settings.provided.COGNITO_CLIENT_SECRET.get_secret_value.call(),
        user_pool_id=settings.provided.COGNITO_USER_POOL_ID,
    )

    sign_in_use_case = providers.Factory(
        SignInUseCase,
        authentication_engine=authentication_engine,
    )

    get_current_user_use_case = providers.Factory(
        GetCurrentUserUseCase,
        authentication_engine=authentication_engine,
        user_service=user_service,
    )

    get_current_brokers_use_case = providers.Factory(
        GetCurrentBrokersUseCase,
        authentication_engine=authentication_engine,
        broker_service=broker_service,
        user_service=user_service,
    )

    list_broker_customers_use_case = providers.Factory(
        ListBrokerCustomersUseCase,
        authentication_engine=authentication_engine,
        broker_service=broker_service,
        customer_service=customer_service,
        policy_service=policy_service,
        user_service=user_service,
    )

    get_customer_details_use_case = providers.Factory(
        GetCustomerDetailsUseCase,
        authentication_engine=authentication_engine,
        broker_service=broker_service,
        customer_service=customer_service,
        policy_service=policy_service,
        user_service=user_service,
    )

    list_policies_use_case = providers.Factory(
        ListPoliciesUseCase,
        authentication_engine=authentication_engine,
        broker_service=broker_service,
        customer_service=customer_service,
        policy_service=policy_service,
        user_service=user_service,
    )

    sign_up_use_case = providers.Factory(
        SignUpUseCase,
        waiting_list_service=waiting_list_service,
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