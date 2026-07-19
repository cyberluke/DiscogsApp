import importlib
import os


class AzureOpenAIClient:
    def __init__(self, endpoint: str | None = None, api_key: str | None = None, model: str | None = None):
        self.endpoint = endpoint or os.getenv('AZURE_AI_ENDPOINT') or os.getenv('AZURE_OPENAI_ENDPOINT')
        self.api_key = api_key or os.getenv('AZURE_AI_API_KEY') or os.getenv('AZURE_OPENAI_API_KEY')
        self.model = model or os.getenv('AZURE_OPENAI_MODEL') or os.getenv('AZURE_OPENAI_DEPLOYMENT')
        self._client = None

    def analyze(self, system_prompt: str, user_prompt: str) -> str:
        if not self.endpoint:
            raise RuntimeError('AZURE_AI_ENDPOINT or AZURE_OPENAI_ENDPOINT is not configured')
        if not self.api_key:
            raise RuntimeError('AZURE_AI_API_KEY or AZURE_OPENAI_API_KEY is not configured')
        if not self.model:
            raise RuntimeError('AZURE_OPENAI_MODEL or AZURE_OPENAI_DEPLOYMENT is not configured')

        try:
            response = self._openai_client().chat.completions.create(
                model=self.model,
                messages=[
                    {'role': 'system', 'content': system_prompt},
                    {'role': 'user', 'content': user_prompt},
                ],
                response_format={'type': 'json_object'},
            )
        except Exception as exc:
            raise RuntimeError(self._azure_error_message(exc)) from exc
        return response.choices[0].message.content or '{}'

    def _azure_error_message(self, error: Exception) -> str:
        response = getattr(error, 'response', None)
        if response is not None:
            try:
                payload = response.json()
                message = payload.get('error', {}).get('message')
                if message:
                    return f'Azure OpenAI request failed: {message}'
            except Exception:
                pass
        return f'Azure OpenAI request failed: {error}'

    def _openai_client(self):
        if self._client is None:
            try:
                openai_module = importlib.import_module('openai')
            except ImportError as exc:
                raise RuntimeError('The openai package is required for Azure OpenAI analysis') from exc
            self._client = openai_module.OpenAI(base_url=self.endpoint, api_key=self.api_key)
        return self._client