from domain.exceptions.domain import DomainException, NotFoundException


class BrokerNotFoundException(NotFoundException):
    def __init__(self):
        super().__init__("Broker")


class BrokerAlreadyActiveException(DomainException):
    pass