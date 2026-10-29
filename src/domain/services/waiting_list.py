from uuid import uuid4

from domain.exceptions.waiting_list import WaitingListEntryAlreadyExistsException
from domain.models.waiting_list import WaitingListEntryModel
from domain.repositories.waiting_list import WaitingListRepository


class WaitingListService:
    def __init__(self, waiting_list_repository: WaitingListRepository) -> None:
        self.waiting_list_repository = waiting_list_repository

    def join(
        self, email: str, phone: str, region: str, insurance_categories: list[str],
    ) -> WaitingListEntryModel:
        email = email.strip().lower()
        if self.waiting_list_repository.exists_by_email(email=email):
            raise WaitingListEntryAlreadyExistsException()

        entry = WaitingListEntryModel(
            id=str(uuid4()),
            email=email,
            phone=phone,
            region=region,
            insurance_categories=tuple(dict.fromkeys(insurance_categories)),
        )
        self.waiting_list_repository.add(entry)
        return entry
