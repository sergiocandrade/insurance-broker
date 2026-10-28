from domain.exceptions.domain import NotFoundException


class CustomerNotFoundException(NotFoundException):
    def __init__(self) -> None:
        super().__init__("Customer")