from typing import get_type_hints

import pytest

from ringsentinel.platform.models import AnalysisRun, Artifact, Investigation
from ringsentinel.platform.service import InvestigationService


@pytest.mark.parametrize(
    ("method", "record"),
    [("list", Investigation), ("artifacts", Artifact), ("runs", AnalysisRun)],
)
def test_service_collection_annotations_resolve_builtin_list(method, record):
    # Python 3.13 evaluates eagerly; 3.14 also needs explicit lazy-hint resolution
    # to catch a class method named "list" shadowing the collection annotation.
    hints = get_type_hints(getattr(InvestigationService, method))
    assert hints["return"] == list[record]
