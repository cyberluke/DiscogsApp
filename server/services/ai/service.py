from datetime import datetime, timezone
from typing import Any

from .cache import MusicAnalysisCache
from .client import AzureOpenAIClient
from .parser import MusicAnalysisParser
from .prompt import MusicAnalysisPrompt


class MusicAnalysisService:
    def __init__(
        self,
        repository,
        client: AzureOpenAIClient | None = None,
        prompt: MusicAnalysisPrompt | None = None,
        parser: MusicAnalysisParser | None = None,
        cache: MusicAnalysisCache | None = None,
        version: int = 1,
    ):
        self.repository = repository
        self.version = version
        self.client = client or AzureOpenAIClient()
        self.prompt = prompt or MusicAnalysisPrompt()
        self.parser = parser or MusicAnalysisParser()
        self.cache = cache or MusicAnalysisCache(repository, version=version)

    def get_release_ai(self, release_id: int) -> dict[str, Any] | None:
        release = self.repository.get_release_by_id(release_id)
        if release is None:
            return None
        return self.cache.get_cached(release)

    def enrich_release(self, release_id: int, force: bool = False) -> dict[str, Any] | None:
        release = self.repository.get_release_by_id(release_id)
        if release is None:
            return None

        cached = self.cache.get_cached(release)
        if cached and not force:
            self.cache.save(release_id, cached)
            return cached

        system_prompt, user_prompt = self.prompt.build(release)
        analysis = self.parser.parse(self.client.analyze(system_prompt, user_prompt))
        ai_metadata = {
            'version': self.version,
            'generated_at': datetime.now(timezone.utc).isoformat(),
            **analysis,
        }
        self.cache.save(release_id, ai_metadata)
        return ai_metadata

    def enrich_all(self, force: bool = False, limit: int | None = None) -> dict[str, Any]:
        enriched = 0
        skipped = 0
        missing = 0
        errors = []

        releases = self.repository.all_releases()
        if limit is not None:
            releases = releases[:limit]

        for release in releases:
            release_id = release.get('release_id')
            if release_id is None:
                missing += 1
                continue
            if self.cache.get_cached(release) and not force:
                skipped += 1
                continue
            try:
                self.enrich_release(int(release_id), force=force)
                enriched += 1
            except Exception as exc:
                errors.append({'release_id': release_id, 'error': str(exc)})

        return {
            'enriched': enriched,
            'skipped': skipped,
            'missing': missing,
            'errors': errors,
        }