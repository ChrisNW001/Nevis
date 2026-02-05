"""Tests for memory systems."""

import pytest
from nevis.memory.working import WorkingMemory
from nevis.memory.episodic import EpisodicMemory
from nevis.memory.semantic import SemanticMemory
from nevis.memory.procedural import ProceduralMemory, Skill


class TestWorkingMemory:
    def test_scratchpad(self):
        wm = WorkingMemory()
        wm.write_scratchpad("step 1")
        wm.write_scratchpad("step 2")
        assert "step 1" in wm.scratchpad
        assert "step 2" in wm.scratchpad

    def test_variables(self):
        wm = WorkingMemory()
        wm.set("count", 42)
        assert wm.get("count") == 42
        assert wm.get("missing", "default") == "default"

    def test_task_stack(self):
        wm = WorkingMemory()
        wm.push_task("task A")
        wm.push_task("task B")
        assert wm.current_task() == "task B"
        assert wm.pop_task() == "task B"
        assert wm.current_task() == "task A"


class TestEpisodicMemory:
    async def test_store_and_retrieve(self, tmp_path):
        mem = EpisodicMemory(storage_path=str(tmp_path / "ep.jsonl"))
        entry_id = await mem.store_event("test_action", "success", True)
        entry = await mem.retrieve(entry_id)
        assert entry is not None
        assert "test_action" in entry.content

    async def test_search(self, tmp_path):
        mem = EpisodicMemory(storage_path=str(tmp_path / "ep.jsonl"))
        await mem.store_event("deploy", "deployed v1", True)
        await mem.store_event("test", "tests passed", True)
        results = await mem.search("deploy")
        assert len(results) >= 1

    async def test_list_recent(self, tmp_path):
        mem = EpisodicMemory(storage_path=str(tmp_path / "ep.jsonl"))
        await mem.store_event("a", "first", True)
        await mem.store_event("b", "second", True)
        recent = await mem.list_recent(limit=1)
        assert len(recent) == 1


class TestSemanticMemory:
    async def test_store_fact(self, tmp_path):
        mem = SemanticMemory(storage_path=str(tmp_path / "sem.jsonl"))
        entry_id = await mem.store_fact("Python was created by Guido van Rossum")
        assert entry_id
        results = await mem.search("Python")
        assert len(results) >= 1

    async def test_ingest_document(self, tmp_path):
        mem = SemanticMemory(storage_path=str(tmp_path / "sem.jsonl"))
        ids = await mem.ingest_document("A" * 1200, chunk_size=500, source="test.txt")
        assert len(ids) == 3  # 1200 / 500 = 3 chunks


class TestProceduralMemory:
    async def test_save_and_find_skill(self, tmp_path):
        mem = ProceduralMemory(storage_path=str(tmp_path / "proc.jsonl"))
        skill = Skill(
            name="deploy_app",
            description="Deploy the application",
            steps=[{"tool": "code_exec", "arguments": {"code": "deploy()"}}],
            tags=["deploy"],
        )
        await mem.save_skill(skill)
        found = await mem.find_skill("deploy")
        assert len(found) == 1
        assert found[0].name == "deploy_app"

    async def test_record_outcome(self, tmp_path):
        mem = ProceduralMemory(storage_path=str(tmp_path / "proc.jsonl"))
        skill = Skill(name="test_skill", description="Test", steps=[])
        await mem.save_skill(skill)
        await mem.record_outcome("test_skill", success=True)
        s = await mem.get_skill("test_skill")
        assert s is not None
        assert s.success_count == 1
