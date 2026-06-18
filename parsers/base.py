from abc import ABC, abstractmethod
from typing import Any


class BaseParser(ABC):
    name = "base"

    @abstractmethod
    def can_handle(self, url: str, html: str | None = None) -> bool:
        raise NotImplementedError

    @abstractmethod
    async def parse(self, url: str, session, html: str | None = None, title_from_page: str | None = None) -> dict[str, Any] | None:
        raise NotImplementedError