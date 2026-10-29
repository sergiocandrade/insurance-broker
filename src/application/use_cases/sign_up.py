from domain.models.waiting_list import WaitingListEntryModel
from domain.services.waiting_list import WaitingListService


class SignUpUseCase:
    def __init__(self, waiting_list_service: WaitingListService) -> None:
        self.waiting_list_service = waiting_list_service

    def execute(
        self, email: str, phone: str, region: str, insurance_categories: list[str],
    ) -> WaitingListEntryModel:
        return self.waiting_list_service.join(
            email=email,
            phone=phone,
            region=region,
            insurance_categories=insurance_categories,
        )
