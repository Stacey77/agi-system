"""Unit tests for the tool registry and individual tool implementations."""

from __future__ import annotations

import pytest

from src.tools.base_tool import BaseTool, ToolMetadata
from src.tools.calculator_tool import CalculatorTool
from src.tools.database_tool import DatabaseTool
from src.tools.document_parser_tool import DocumentParserTool
from src.tools.tool_registry import ToolRegistry
from src.tools.web_search_tool import WebSearchTool


# ---------------------------------------------------------------------------
# ToolRegistry
# ---------------------------------------------------------------------------

class TestToolRegistry:
    def test_register_and_get(self):
        registry = ToolRegistry()
        tool = WebSearchTool()
        registry.register_tool(tool)
        retrieved = registry.get_tool("web_search")
        assert retrieved is tool

    def test_get_unknown_raises(self):
        registry = ToolRegistry()
        with pytest.raises(KeyError):
            registry.get_tool("nonexistent_tool")

    def test_get_by_category(self):
        registry = ToolRegistry()
        registry.register_tool(WebSearchTool())
        registry.register_tool(DocumentParserTool())
        registry.register_tool(CalculatorTool())
        info_tools = registry.get_tools_by_category("information_retrieval")
        assert len(info_tools) == 2

    def test_list_tools(self):
        registry = ToolRegistry()
        registry.register_tool(WebSearchTool())
        registry.register_tool(CalculatorTool())
        metadata = registry.list_tools()
        names = [m.name for m in metadata]
        assert "web_search" in names
        assert "calculator" in names

    def test_contains(self):
        registry = ToolRegistry()
        registry.register_tool(CalculatorTool())
        assert "calculator" in registry
        assert "web_search" not in registry


# ---------------------------------------------------------------------------
# WebSearchTool
# ---------------------------------------------------------------------------

class TestWebSearchTool:
    def test_metadata(self):
        tool = WebSearchTool()
        assert tool.metadata.name == "web_search"
        assert tool.metadata.category == "information_retrieval"

    def test_mock_search(self):
        tool = WebSearchTool()
        results = tool.execute(query="test query")
        assert isinstance(results, list)
        assert len(results) > 0
        assert "title" in results[0]
        assert "url" in results[0]

    def test_missing_query_returns_empty(self):
        tool = WebSearchTool()
        results = tool.execute()
        assert results == []

    def test_validate_parameters(self):
        tool = WebSearchTool()
        assert tool.validate_parameters(query="hello") is True
        assert tool.validate_parameters() is False


# ---------------------------------------------------------------------------
# CalculatorTool
# ---------------------------------------------------------------------------

class TestCalculatorTool:
    def test_simple_expression(self):
        tool = CalculatorTool()
        result = tool.execute(expression="2 + 3")
        assert result == 5.0

    def test_complex_expression(self):
        tool = CalculatorTool()
        result = tool.execute(expression="sqrt(16)")
        assert result == 4.0

    def test_statistics(self):
        tool = CalculatorTool()
        result = tool.execute(
            expression="stats",
            operation="statistics",
            data=[1, 2, 3, 4, 5],
        )
        assert result["mean"] == 3.0
        assert result["count"] == 5

    def test_division_expression(self):
        tool = CalculatorTool()
        result = tool.execute(expression="10 / 4")
        assert result == 2.5

    def test_unsafe_expression_returns_error(self):
        tool = CalculatorTool()
        result = tool.execute(expression="__import__('os')")
        assert isinstance(result, dict) and "error" in result

    def test_empty_statistics_data(self):
        tool = CalculatorTool()
        result = tool.execute(expression="", operation="statistics", data=[])
        assert "error" in result


# ---------------------------------------------------------------------------
# DocumentParserTool
# ---------------------------------------------------------------------------

class TestDocumentParserTool:
    def test_metadata(self):
        tool = DocumentParserTool()
        assert tool.metadata.name == "document_parser"
        assert tool.metadata.category == "information_retrieval"

    def test_missing_file_path(self):
        tool = DocumentParserTool()
        result = tool.execute()
        assert result["content"] is None

    def test_nonexistent_file(self):
        tool = DocumentParserTool()
        result = tool.execute(file_path="/tmp/does_not_exist.txt")
        assert result["content"] is None
        assert "error" in result

    def test_text_file_parsing(self, tmp_path):
        text_file = tmp_path / "test.txt"
        text_file.write_text("Hello, AGI!")
        tool = DocumentParserTool()
        result = tool.execute(file_path=str(text_file))
        assert result["content"] == "Hello, AGI!"


# ---------------------------------------------------------------------------
# DatabaseTool
# ---------------------------------------------------------------------------

class TestDatabaseTool:
    def test_metadata(self):
        tool = DatabaseTool()
        assert tool.metadata.name == "database"
        assert tool.metadata.category == "integration"

    def test_execute_query_mock(self):
        tool = DatabaseTool()  # no URL → mock connection
        result = tool.execute(query="SELECT * FROM test")
        assert "rows" in result
        assert isinstance(result["rows"], list)

    def test_missing_query(self):
        tool = DatabaseTool()
        result = tool.execute()
        assert "error" in result
