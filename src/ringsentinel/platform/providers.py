"""Optional explanation wiring. No provider requests during startup/readiness."""

from ringsentinel.investigation.investigator import (
    DeterministicProvider,
    OpenAIProvider,
    SummaryProvider,
)
from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.settings import Settings


class DisabledProvider(DeterministicProvider):
    name = "disabled_evidence_only"


class UnavailableProvider:
    name = "openai_unavailable"

    def select_facts(self, question: str, facts: list[dict]) -> list[str]:
        # InvestigatorService converts this into its explicit, grounded fallback warning.
        raise ProductError("PROVIDER_UNAVAILABLE")


def provider_from_settings(settings: Settings) -> SummaryProvider:
    if settings.llm_provider == "disabled":
        return DisabledProvider()
    if settings.llm_provider == "deterministic":
        return DeterministicProvider()
    key = settings.openai_api_key.get_secret_value()
    if not key:
        return UnavailableProvider()
    return OpenAIProvider(
        key,
        settings.openai_model,
        timeout_seconds=settings.llm_timeout_seconds,
        retry_count=settings.llm_retry_count,
        max_output_tokens=settings.llm_max_output_tokens,
    )
