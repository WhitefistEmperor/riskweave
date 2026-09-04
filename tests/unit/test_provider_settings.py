import io
import json
from urllib.error import HTTPError, URLError

import pytest

from ringsentinel.platform.errors import ProductError
from ringsentinel.platform.providers import provider_from_settings
from ringsentinel.platform.settings import Settings


def test_opt_in_disabled_missing_key_and_secrets():
    settings = Settings(llm_provider="disabled", openai_api_key="unit-test-only")
    provider = provider_from_settings(settings)
    assert provider.name == "disabled_evidence_only"
    assert provider.select_facts("Why?", [{"id": "F001"}]) == ["F001"]
    assert "unit-test-only" not in repr(settings)
    settings = Settings(llm_provider="openai", openai_api_key="")
    with pytest.raises(ProductError) as exc:
        provider_from_settings(settings).select_facts("Why?", [])
    assert exc.value.code == "PROVIDER_UNAVAILABLE"


@pytest.mark.parametrize(
    "origin",
    [
        "*",
        "https://*",
        "https://site.test/path",
        "http://user:pass@site.test",
        "https://site.test:99999",
    ],
)
def test_origin_configuration_rejects_wildcards_paths_and_credentials(origin):
    with pytest.raises(ValueError):
        Settings(frontend_origins=[origin])


@pytest.mark.parametrize("status,attempts", [(429, 3), (503, 3), (401, 1), (400, 1)])
def test_retries_are_bounded_and_do_not_retry_auth(monkeypatch, status, attempts):
    seen = []

    def fail(request, timeout):
        seen.append(timeout)
        assert json.loads(request.data)["max_output_tokens"] == 500
        raise HTTPError(request.full_url, status, "sensitive upstream body", {}, None)

    monkeypatch.setattr("ringsentinel.investigation.investigator.urlopen", fail)
    monkeypatch.setattr("ringsentinel.investigation.investigator.time.sleep", lambda _: None)
    settings = Settings(
        llm_provider="openai",
        openai_api_key="unit-test-only",
        llm_retry_count=2,
        llm_timeout_seconds=0.5,
        llm_max_output_tokens=500,
    )
    with pytest.raises(HTTPError):
        provider_from_settings(settings).select_facts("Why?", [{"id": "F001"}])
    assert seen == [0.5] * attempts


def test_transient_retry_then_structured_success(monkeypatch):
    calls = []

    def transport(request, timeout):
        calls.append(timeout)
        if len(calls) == 1:
            raise URLError("network")
        return io.BytesIO(
            json.dumps(
                {
                    "output": [
                        {
                            "type": "message",
                            "content": [{"type": "output_text", "text": '{"fact_ids":["F001"]}'}],
                        }
                    ]
                }
            ).encode()
        )

    monkeypatch.setattr("ringsentinel.investigation.investigator.urlopen", transport)
    monkeypatch.setattr("ringsentinel.investigation.investigator.time.sleep", lambda _: None)
    settings = Settings(llm_provider="openai", openai_api_key="unit-test-only", llm_retry_count=1)
    assert provider_from_settings(settings).select_facts("Why?", [{"id": "F001"}]) == ["F001"]
    assert len(calls) == 2
