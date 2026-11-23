from src.utils import normalize_name, parse_date
from src.processors.resolution import EntityResolver

def test_normalize_company_suffix():
    assert normalize_name("OpenAI, Inc.") == normalize_name("Open AI")

def test_entity_resolution_seed():
    resolver = EntityResolver(["OpenAI"])
    assert resolver.resolve("Open AI, Inc.") == "OpenAI"

def test_relative_date():
    assert parse_date("2 hours ago") is not None
