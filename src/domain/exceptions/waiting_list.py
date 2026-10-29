from domain.exceptions.domain import ConflictException


class WaitingListEntryAlreadyExistsException(ConflictException):
    def __init__(self) -> None:
        super().__init__("Email already on the waiting list")
