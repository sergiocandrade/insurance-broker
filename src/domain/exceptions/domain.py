class DomainException(Exception):
    def __init__(self, message: str) -> None:
        super().__init__(message)

class NotFoundException(DomainException):
    def __init__(self, resource: str) -> None:
        message = f"{resource} not found"
        super().__init__(message)

class ForbiddenException(DomainException):
    def __init__(self, message: str) -> None:
        super().__init__(message)