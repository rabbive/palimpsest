import importlib.util
from pathlib import Path

SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "repro_byog_infer_false.py"


def test_repro_payloads_have_documented_keys():
    spec = importlib.util.spec_from_file_location("repro_byog", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    memories, graph = mod.build_payloads()

    assert [m["id"] for m in memories] == ["mem-a", "mem-b"]
    assert set(graph) == {"mem-a", "mem-b"}
    for entry in graph.values():
        assert set(entry) == {"entities", "relations"}
        for rel in entry["relations"]:
            assert rel["source"] in entry["entities"] and rel["target"] in entry["entities"]
    assert [r["predicate"] for r in graph["mem-b"]["relations"]] == ["LIVES_IN", "SUPERSEDES"]
    assert len(graph["mem-a"]["relations"]) == 1
