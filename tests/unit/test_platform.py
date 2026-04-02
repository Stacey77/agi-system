"""Unit tests for the platform module (tool landscape, developer portal, Kally AI)."""

from __future__ import annotations

import pytest

from src.agents.base_agent import AgentConfig, AgentType
from src.agents.kally_agent import FeedbackSignal, KallyAgent
from src.platform.developer_portal import DeveloperPortal, PortalTier, ServiceStatus
from src.platform.tool_landscape import ToolCategory, ToolLandscape, ToolTier


# ---------------------------------------------------------------------------
# ToolLandscape
# ---------------------------------------------------------------------------

class TestToolLandscape:
    def test_loads_defaults(self):
        landscape = ToolLandscape(load_defaults=True)
        assert landscape.total_count() > 0

    def test_empty_without_defaults(self):
        landscape = ToolLandscape(load_defaults=False)
        assert landscape.total_count() == 0

    def test_register_and_retrieve(self):
        landscape = ToolLandscape(load_defaults=False)
        tool = landscape.register_tool(
            name="MyTool",
            description="A test tool",
            category=ToolCategory.CI_CD,
            tier=ToolTier.INTERNAL,
        )
        assert landscape.get_tool(tool.tool_id) is tool

    def test_list_tools_all(self):
        landscape = ToolLandscape(load_defaults=True)
        tools = landscape.list_tools()
        assert len(tools) > 0

    def test_list_tools_by_category(self):
        landscape = ToolLandscape(load_defaults=True)
        ai_tools = landscape.list_tools(category=ToolCategory.AI_ML)
        assert all(t.category == ToolCategory.AI_ML for t in ai_tools)

    def test_list_tools_by_tier(self):
        landscape = ToolLandscape(load_defaults=False)
        landscape.register_tool("T1", tier=ToolTier.INTERNAL)
        landscape.register_tool("T2", tier=ToolTier.EXTERNAL)
        landscape.register_tool("T3", tier=ToolTier.BOTH)
        internal = landscape.list_tools(tier=ToolTier.INTERNAL)
        # BOTH tools are also included for INTERNAL tier
        names = [t.name for t in internal]
        assert "T1" in names
        assert "T3" in names
        assert "T2" not in names

    def test_search(self):
        landscape = ToolLandscape(load_defaults=True)
        results = landscape.search("prometheus")
        assert len(results) >= 1
        assert any("prometheus" in r.name.lower() for r in results)

    def test_search_no_match(self):
        landscape = ToolLandscape(load_defaults=False)
        landscape.register_tool("Alpha")
        assert landscape.search("zzznomatch") == []

    def test_deactivate_tool(self):
        landscape = ToolLandscape(load_defaults=False)
        tool = landscape.register_tool("ToDeactivate")
        assert landscape.deactivate_tool(tool.tool_id) is True
        # Active-only listing should exclude it
        assert len(landscape.list_tools(active_only=True)) == 0

    def test_categories_summary(self):
        landscape = ToolLandscape(load_defaults=True)
        summary = landscape.categories_summary()
        assert isinstance(summary, dict)
        assert sum(summary.values()) == landscape.total_count()

    def test_to_dict_keys(self):
        landscape = ToolLandscape(load_defaults=False)
        tool = landscape.register_tool("TestTool", description="desc", tags=["a", "b"])
        d = tool.to_dict()
        assert d["name"] == "TestTool"
        assert "tool_id" in d
        assert "tags" in d


# ---------------------------------------------------------------------------
# DeveloperPortal
# ---------------------------------------------------------------------------

class TestDeveloperPortal:
    def test_loads_defaults(self):
        portal = DeveloperPortal(load_defaults=True)
        assert portal.total_count() > 0

    def test_register_service(self):
        portal = DeveloperPortal(load_defaults=False)
        svc = portal.register_service(name="MyAPI", tier=PortalTier.EXTERNAL)
        assert portal.get_service(svc.service_id) is svc

    def test_list_services_by_tier(self):
        portal = DeveloperPortal(load_defaults=False)
        portal.register_service("Internal1", tier=PortalTier.INTERNAL)
        portal.register_service("External1", tier=PortalTier.EXTERNAL)
        internal = portal.list_services(tier=PortalTier.INTERNAL)
        assert len(internal) == 1
        assert internal[0].name == "Internal1"

    def test_search(self):
        portal = DeveloperPortal(load_defaults=True)
        results = portal.search("agents")
        assert len(results) >= 1

    def test_update_status(self):
        portal = DeveloperPortal(load_defaults=False)
        svc = portal.register_service("SVC")
        assert portal.update_status(svc.service_id, ServiceStatus.DEGRADED) is True
        assert portal.get_service(svc.service_id).status == ServiceStatus.DEGRADED

    def test_update_status_nonexistent(self):
        portal = DeveloperPortal(load_defaults=False)
        assert portal.update_status("bad-id", ServiceStatus.OUTAGE) is False

    def test_health_dashboard_all_operational(self):
        portal = DeveloperPortal(load_defaults=False)
        portal.register_service("A")
        portal.register_service("B")
        dashboard = portal.health_dashboard()
        assert dashboard["fully_operational"] is True
        assert dashboard["total_services"] == 2

    def test_health_dashboard_degraded(self):
        portal = DeveloperPortal(load_defaults=False)
        svc = portal.register_service("A")
        portal.update_status(svc.service_id, ServiceStatus.DEGRADED)
        dashboard = portal.health_dashboard()
        assert dashboard["fully_operational"] is False

    def test_to_dict_keys(self):
        portal = DeveloperPortal(load_defaults=False)
        svc = portal.register_service("TestSvc", version="v2", tags=["tag1"])
        d = svc.to_dict()
        assert d["name"] == "TestSvc"
        assert d["version"] == "v2"
        assert "service_id" in d


# ---------------------------------------------------------------------------
# KallyAgent
# ---------------------------------------------------------------------------

class TestKallyAgent:
    def _make_agent(self) -> KallyAgent:
        config = AgentConfig(name="kally", agent_type=AgentType.KALLY)
        return KallyAgent(config)

    @pytest.mark.asyncio
    async def test_ingest_signal(self):
        agent = self._make_agent()
        result = await agent.process_task({
            "action": "ingest",
            "source": "api_gateway",
            "metric": "error_rate",
            "value": 0.05,
            "threshold": 0.01,
            "severity": "warning",
        })
        assert result["status"] == "completed"
        assert result["buffer_size"] == 1

    @pytest.mark.asyncio
    async def test_analyse_no_signals(self):
        agent = self._make_agent()
        result = await agent.process_task({"action": "analyse"})
        assert result["status"] == "completed"
        assert result["health_score"] == 1.0
        assert len(result["recommendations"]) > 0

    @pytest.mark.asyncio
    async def test_analyse_with_anomaly(self):
        agent = self._make_agent()
        # Ingest a signal that breaches threshold
        await agent.process_task({
            "action": "ingest",
            "source": "memory",
            "metric": "usage_gb",
            "value": 15.0,
            "threshold": 10.0,
            "severity": "critical",
        })
        result = await agent.process_task({"action": "analyse"})
        assert result["anomalies_detected"] == 1
        assert result["health_score"] < 1.0

    @pytest.mark.asyncio
    async def test_report_action(self):
        agent = self._make_agent()
        result = await agent.process_task({"action": "report"})
        assert result["status"] == "completed"
        assert "health_score" in result

    @pytest.mark.asyncio
    async def test_reset_action(self):
        agent = self._make_agent()
        await agent.process_task({
            "action": "ingest", "source": "x", "metric": "y", "value": 1.0,
        })
        result = await agent.process_task({"action": "reset"})
        assert result["signals_cleared"] == 1
        # Buffer should be empty now
        report = await agent.process_task({"action": "report"})
        assert report["buffered_signals"] == 0

    @pytest.mark.asyncio
    async def test_unknown_action(self):
        agent = self._make_agent()
        result = await agent.process_task({"action": "unknown_xyz"})
        assert result["status"] == "error"

    @pytest.mark.asyncio
    async def test_health_score_all_clear(self):
        agent = self._make_agent()
        # Signal within threshold
        await agent.ingest_signal(FeedbackSignal(
            source="db", metric="latency_ms", value=50.0, threshold=100.0
        ))
        assert agent._compute_health_score() == 1.0

    @pytest.mark.asyncio
    async def test_health_score_partial_breach(self):
        agent = self._make_agent()
        await agent.ingest_signal(FeedbackSignal(
            source="a", metric="m", value=200.0, threshold=100.0
        ))
        await agent.ingest_signal(FeedbackSignal(
            source="b", metric="m", value=50.0, threshold=100.0
        ))
        # 1 out of 2 signals breach => health = 0.5
        assert agent._compute_health_score() == 0.5
