"""Role-based local model construction; no network calls during construction."""
from threading import RLock
from generation.local_llm import OllamaChat


class ModelFactory:
    def __init__(self, config):
        self.config = config
        self._models = {}
        self._lock = RLock()

    def get_model(self, role):
        names = {
            "generate": self.config.llm_model,
            "grade": self.config.llm_grade_model or self.config.llm_model,
            "rewrite": self.config.llm_rewrite_model or self.config.llm_model,
        }
        if role not in names:
            raise ValueError(f"Unknown model role: {role}")
        name = names[role].strip()
        with self._lock:
            if name not in self._models:
                self._models[name] = OllamaChat(name, self.config.llm_timeout)
            return self._models[name]
