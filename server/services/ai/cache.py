from typing import Any, Mapping


class MusicAnalysisCache:
    def __init__(self, repository, version: int = 1):
        self.repository = repository
        self.version = version

    def get_cached(self, release: Mapping[str, Any]) -> dict[str, Any] | None:
        ai_metadata = release.get('ai')
        if isinstance(ai_metadata, dict) and ai_metadata.get('version') == self.version:
            return ai_metadata
        return None

    def save(self, release_id: int, ai_metadata: dict[str, Any]) -> dict[str, Any] | None:
        return self.repository.save_release_ai(release_id, ai_metadata)