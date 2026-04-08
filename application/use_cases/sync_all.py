import logging
from datetime import date, timedelta

from application.dto import ImportResultDTO, SyncAllItemResult, SyncAllResultDTO, TANRequiredDTO
from application.use_cases.import_transactions import ImportTransactionsUseCase

logger = logging.getLogger(__name__)


class SyncAllUseCase:
    def __init__(self, import_use_case: ImportTransactionsUseCase):
        self._import_use_case = import_use_case

    def execute(self, start_date: date | None = None) -> SyncAllResultDTO:
        if start_date is None:
            start_date = date.today() - timedelta(days=30)

        mappings = self._import_use_case._mappings.get_all()
        results: list[SyncAllItemResult] = []

        for mapping in mappings:
            try:
                result = self._import_use_case.execute(
                    mapping_id=mapping.id,
                    start_date=start_date,
                )
                if isinstance(result, TANRequiredDTO):
                    results.append(SyncAllItemResult(
                        mapping_id=mapping.id, status="tan_required", session_id=result.session_id,
                    ))
                elif isinstance(result, ImportResultDTO):
                    results.append(SyncAllItemResult(
                        mapping_id=mapping.id, status="completed", imported=result.imported,
                    ))
            except Exception as e:
                logger.exception("Sync failed for mapping %s", mapping.id)
                results.append(SyncAllItemResult(
                    mapping_id=mapping.id, status="failed", error=str(e),
                ))

        return SyncAllResultDTO(results=results)
