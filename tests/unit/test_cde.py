"""Unit tests for the CDE module."""

from __future__ import annotations

import pytest

from src.agents.base_agent import AgentConfig, AgentType
from src.cde.cde_agent import CDEAgent
from src.cde.cde_environment import CDEEnvironment, CDEResources, CDERuntime, CDEStatus
from src.cde.cde_manager import CDEManager


# ---------------------------------------------------------------------------
# CDEEnvironment
# ---------------------------------------------------------------------------

class TestCDEEnvironment:
    def test_defaults(self):
        env = CDEEnvironment(name="test")
        assert env.name == "test"
        assert env.runtime == CDERuntime.PYTHON
        assert env.status == CDEStatus.PROVISIONING

    def test_transition_to(self):
        env = CDEEnvironment()
        env.transition_to(CDEStatus.RUNNING)
        assert env.status == CDEStatus.RUNNING

    def test_to_dict(self):
        env = CDEEnvironment(name="my-env", owner="alice")
        d = env.to_dict()
        assert d["name"] == "my-env"
        assert d["owner"] == "alice"
        assert "env_id" in d
        assert "resources" in d


# ---------------------------------------------------------------------------
# CDEResources
# ---------------------------------------------------------------------------

class TestCDEResources:
    def test_defaults(self):
        r = CDEResources()
        assert r.cpu_cores == 1.0
        assert r.memory_gb == 2.0

    def test_to_dict(self):
        r = CDEResources(cpu_cores=4.0, memory_gb=8.0)
        d = r.to_dict()
        assert d["cpu_cores"] == 4.0
        assert d["memory_gb"] == 8.0


# ---------------------------------------------------------------------------
# CDEManager
# ---------------------------------------------------------------------------

class TestCDEManager:
    def test_create_environment(self):
        mgr = CDEManager()
        env = mgr.create_environment(name="dev", owner="bob")
        assert env.status == CDEStatus.RUNNING
        assert mgr.get_environment(env.env_id) is env

    def test_list_environments(self):
        mgr = CDEManager()
        mgr.create_environment(name="env1", owner="alice")
        mgr.create_environment(name="env2", owner="bob")
        assert len(mgr.list_environments()) == 2

    def test_list_filter_owner(self):
        mgr = CDEManager()
        mgr.create_environment(name="env1", owner="alice")
        mgr.create_environment(name="env2", owner="bob")
        assert len(mgr.list_environments(owner="alice")) == 1

    def test_list_filter_status(self):
        mgr = CDEManager()
        e = mgr.create_environment(name="e1")
        mgr.stop_environment(e.env_id)
        running = mgr.list_environments(status=CDEStatus.RUNNING)
        assert len(running) == 0

    def test_stop_and_start(self):
        mgr = CDEManager()
        env = mgr.create_environment(name="e")
        assert mgr.stop_environment(env.env_id) is True
        assert env.status == CDEStatus.STOPPED
        assert mgr.start_environment(env.env_id) is True
        assert env.status == CDEStatus.RUNNING

    def test_stop_nonexistent(self):
        mgr = CDEManager()
        assert mgr.stop_environment("bad-id") is False

    def test_start_requires_stopped(self):
        mgr = CDEManager()
        env = mgr.create_environment(name="e")
        # Already running — start should return False
        assert mgr.start_environment(env.env_id) is False

    def test_delete_environment(self):
        mgr = CDEManager()
        env = mgr.create_environment(name="e")
        assert mgr.delete_environment(env.env_id) is True
        assert mgr.get_environment(env.env_id) is None

    def test_running_count(self):
        mgr = CDEManager()
        e1 = mgr.create_environment(name="e1")
        mgr.create_environment(name="e2")
        mgr.stop_environment(e1.env_id)
        assert mgr.running_count() == 1

    def test_total_count(self):
        mgr = CDEManager()
        mgr.create_environment(name="e1")
        mgr.create_environment(name="e2")
        assert mgr.total_count() == 2


# ---------------------------------------------------------------------------
# CDEAgent
# ---------------------------------------------------------------------------

class TestCDEAgent:
    def _make_agent(self) -> CDEAgent:
        config = AgentConfig(name="cde", agent_type=AgentType.CDE)
        return CDEAgent(config)

    @pytest.mark.asyncio
    async def test_create_action(self):
        agent = self._make_agent()
        result = await agent.process_task({"action": "create", "name": "my-env", "runtime": "python"})
        assert result["status"] == "completed"
        assert result["action"] == "create"
        assert result["environment"]["name"] == "my-env"

    @pytest.mark.asyncio
    async def test_list_action(self):
        agent = self._make_agent()
        await agent.process_task({"action": "create", "name": "e1"})
        await agent.process_task({"action": "create", "name": "e2"})
        result = await agent.process_task({"action": "list"})
        assert result["total"] == 2

    @pytest.mark.asyncio
    async def test_status_action(self):
        agent = self._make_agent()
        create_res = await agent.process_task({"action": "create", "name": "e"})
        env_id = create_res["environment"]["env_id"]
        result = await agent.process_task({"action": "status", "env_id": env_id})
        assert result["status"] == "completed"
        assert result["environment"]["env_id"] == env_id

    @pytest.mark.asyncio
    async def test_stop_and_start_action(self):
        agent = self._make_agent()
        create_res = await agent.process_task({"action": "create", "name": "e"})
        env_id = create_res["environment"]["env_id"]

        stop_res = await agent.process_task({"action": "stop", "env_id": env_id})
        assert stop_res["stopped"] is True

        start_res = await agent.process_task({"action": "start", "env_id": env_id})
        assert start_res["started"] is True

    @pytest.mark.asyncio
    async def test_delete_action(self):
        agent = self._make_agent()
        create_res = await agent.process_task({"action": "create", "name": "e"})
        env_id = create_res["environment"]["env_id"]
        del_res = await agent.process_task({"action": "delete", "env_id": env_id})
        assert del_res["deleted"] is True

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        agent = self._make_agent()
        result = await agent.process_task({"action": "fly"})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_invalid_runtime_falls_back(self):
        agent = self._make_agent()
        result = await agent.process_task({"action": "create", "runtime": "cobol"})
        assert result["status"] == "completed"
        assert result["environment"]["runtime"] == "generic"
