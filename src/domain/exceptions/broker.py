from domain.exceptions.domain import DomainException


class BrokerNotFoundError(Exception):
    pass


class BrokerAccessDeniedError(Exception):
    pass


class BrokerAlreadyActiveException(DomainException):
    pass