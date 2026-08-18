from palimpsest.coverage import _normalize_entity


def test_normalize_first_person_entities_to_user():
    for entity in ("I", "me", "My", "myself", "the user"):
        assert _normalize_entity(entity) == "user"


def test_normalize_named_entity():
    assert _normalize_entity("  Priya Raghavan ") == "priya raghavan"
