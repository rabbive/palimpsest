"""Library facade: one end user's memory on top of HydraDB."""
import asyncio

from palimpsest import config, ledger
from palimpsest.models import Answer, Fact
from palimpsest.read_path import answer_question
from palimpsest.write_path import process_dialogue


class Memory:
    """One end user's memory.

    `collection` is the HydraDB collection and the ledger `dialogue_id`. The
    database comes from `HYDRADB_DATABASE`; create its schema once with
    `palimpsest create-db`.
    """

    def __init__(self, collection: str):
        self.collection = collection
        self._lock = asyncio.Lock()

    async def add_session(self, text: str, timestamp: str = "") -> dict:
        """Reconcile one session into memory and return `process_dialogue` stats.

        The instance lock is held from reading the next session index until the
        write returns, so concurrent calls get distinct indexes (fact IDs embed
        the index; a collision would silently skip facts). It does not protect
        against two processes writing to one collection.
        """
        async with self._lock:
            with ledger.connect(config.LEDGER_PATH) as conn:
                idx = ledger.next_session_idx(conn, self.collection)
            return await process_dialogue(self.collection, [(idx, timestamp, text)])

    async def ask(self, question: str) -> Answer:
        return await answer_question(self.collection, question)

    def history(self) -> list[Fact]:
        """Every ledger fact, superseded ones included. Inspection only; never used to answer."""
        with ledger.connect(config.LEDGER_PATH) as conn:
            return ledger.all_facts(conn, self.collection)
