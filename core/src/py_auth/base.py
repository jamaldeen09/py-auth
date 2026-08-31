from abc import ABC, abstractmethod

class BaseProvider(ABC):
    id: str
    def __init__(self):
        self.id = self.__class__.__name__.lower().replace("provider", "")
    @abstractmethod
    async def authenticate(self, *args, **kwargs):
        pass
