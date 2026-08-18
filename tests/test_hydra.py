import asyncio

from palimpsest import hydra


class _FakeContext:
    def __init__(self):
        self.calls = []

    async def relations(self, **kwargs):
        self.calls.append(kwargs)
        return "ok"


class _FakeClient:
    def __init__(self, context):
        self.context = context


def test_relations_omits_zero_cursor_on_first_page(monkeypatch):
    context = _FakeContext()
    monkeypatch.setattr(hydra, "_client", lambda: _FakeClient(context))

    async def run():
        assert await hydra.relations(collection="8", id="fact-1") == "ok"
        assert await hydra.relations(collection="8", id="fact-1", cursor=123.0) == "ok"

    asyncio.run(run())

    assert "cursor" not in context.calls[0]
    assert context.calls[1]["cursor"] == 123.0
