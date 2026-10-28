from domain.exceptions.domain import ForbiddenException, NotFoundException


class UserNotFoundException(NotFoundException):
    def __init__(self) -> None:
        super().__init__("User")

class UserNotPreRegistredException(ForbiddenException):
    def __init__(self) -> None:
        super().__init__("User not pre-registered")

class UserAlreadyRegistredException(ForbiddenException):
    def __init__(self) -> None:
        super().__init__("User already registered")

