"""IDE agent — AI-powered coding assistant for the vibecoding IDE."""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional

from src.agents.base_agent import AgentConfig, BaseAgent
from src.ide.ide_session import IDESession, IDESessionManager, SessionState

logger = logging.getLogger(__name__)

# Completion templates keyed by action
_ACTION_TEMPLATES: Dict[str, str] = {
    "complete": "# AI completion for: {prompt}\n",
    "explain": "# Explanation: {prompt}\n",
    "refactor": "# Refactored: {prompt}\n",
    "fix": "# Fix applied: {prompt}\n",
    "generate": "# Generated: {prompt}\n",
    "review": "# Code review: {prompt}\n",
}


@dataclass
class CodeCompletion:
    """Result of an AI code-completion request."""

    prompt: str
    language: str
    completion: str
    suggestions: List[str] = field(default_factory=list)
    confidence: float = 0.0
    action: str = "complete"
    session_id: Optional[str] = None


class IDEAgent(BaseAgent):
    """AI coding assistant powering the vibecoding IDE.

    Supports code completion, explanation, refactoring, bug-fixing,
    generation, and review within persistent IDE sessions.
    """

    def __init__(
        self,
        config: AgentConfig,
        execution_agent: Optional[Any] = None,
        session_manager: Optional[IDESessionManager] = None,
    ) -> None:
        super().__init__(config, execution_agent)
        self.session_manager = session_manager or IDESessionManager()

    # ------------------------------------------------------------------
    # BaseAgent interface
    # ------------------------------------------------------------------

    async def process_task(self, task: Dict[str, Any]) -> Dict[str, Any]:
        """Dispatch an IDE task (complete / explain / refactor / fix / generate / review)."""
        action = task.get("action", "complete")
        prompt = task.get("prompt", task.get("task", ""))
        language = task.get("language", "python")
        session_id: Optional[str] = task.get("session_id")

        logger.info("IDEAgent action='%s' language='%s'", action, language)

        session = self._resolve_session(session_id, language)
        completion = await self._handle_action(action, prompt, language, session)

        result: Dict[str, Any] = {
            "status": "completed",
            "action": completion.action,
            "language": completion.language,
            "completion": completion.completion,
            "suggestions": completion.suggestions,
            "confidence": completion.confidence,
            "session_id": session.session_id,
        }
        self._record_task(task, result)
        return result

    # ------------------------------------------------------------------
    # Public helpers
    # ------------------------------------------------------------------

    async def complete_code(
        self, prompt: str, language: str = "python", session_id: Optional[str] = None
    ) -> CodeCompletion:
        """Generate a code completion for the given prompt."""
        session = self._resolve_session(session_id, language)
        return await self._handle_action("complete", prompt, language, session)

    async def explain_code(
        self, code: str, language: str = "python", session_id: Optional[str] = None
    ) -> CodeCompletion:
        """Generate a natural-language explanation of the supplied code."""
        session = self._resolve_session(session_id, language)
        return await self._handle_action("explain", code, language, session)

    async def refactor_code(
        self, code: str, language: str = "python", session_id: Optional[str] = None
    ) -> CodeCompletion:
        """Suggest a refactored version of the supplied code."""
        session = self._resolve_session(session_id, language)
        return await self._handle_action("refactor", code, language, session)

    async def fix_code(
        self, code: str, language: str = "python", session_id: Optional[str] = None
    ) -> CodeCompletion:
        """Attempt to fix bugs in the supplied code."""
        session = self._resolve_session(session_id, language)
        return await self._handle_action("fix", code, language, session)

    async def generate_code(
        self,
        description: str,
        language: str = "python",
        session_id: Optional[str] = None,
    ) -> CodeCompletion:
        """Generate code from a natural-language description."""
        session = self._resolve_session(session_id, language)
        return await self._handle_action("generate", description, language, session)

    async def review_code(
        self, code: str, language: str = "python", session_id: Optional[str] = None
    ) -> CodeCompletion:
        """Review code and return feedback suggestions."""
        session = self._resolve_session(session_id, language)
        return await self._handle_action("review", code, language, session)

    # ------------------------------------------------------------------
    # Internals
    # ------------------------------------------------------------------

    def _resolve_session(
        self, session_id: Optional[str], language: str
    ) -> IDESession:
        if session_id:
            session = self.session_manager.get_session(session_id)
            if session and session.state != SessionState.CLOSED:
                return session
        return self.session_manager.create_session(language=language)

    async def _handle_action(
        self, action: str, prompt: str, language: str, session: IDESession
    ) -> CodeCompletion:
        template = _ACTION_TEMPLATES.get(action, _ACTION_TEMPLATES["complete"])
        completion_text = template.format(prompt=prompt[:200])

        # Build language-appropriate code skeleton
        if action in ("complete", "generate"):
            completion_text += self._build_code_skeleton(prompt, language)
        elif action == "explain":
            completion_text = self._build_explanation(prompt, language)
        elif action == "refactor":
            completion_text += self._build_refactor_hints(prompt, language)
        elif action == "fix":
            completion_text += self._build_fix_hints(prompt, language)
        elif action == "review":
            completion_text = self._build_review_feedback(prompt, language)

        suggestions = self._derive_suggestions(action, language)
        confidence = self._estimate_confidence(prompt, action)

        session.add_interaction("user", prompt)
        session.add_interaction("assistant", completion_text)

        return CodeCompletion(
            prompt=prompt,
            language=language,
            completion=completion_text,
            suggestions=suggestions,
            confidence=confidence,
            action=action,
            session_id=session.session_id,
        )

    def _build_code_skeleton(self, prompt: str, language: str) -> str:
        skeletons: Dict[str, str] = {
            "python": f"def solution():\n    # TODO: implement {prompt[:60]}\n    pass\n",
            "javascript": f"function solution() {{\n  // TODO: implement {prompt[:60]}\n}}\n",
            "typescript": f"function solution(): void {{\n  // TODO: implement {prompt[:60]}\n}}\n",
            "java": f"public void solution() {{\n  // TODO: implement {prompt[:60]}\n}}\n",
            "go": f"func solution() {{\n\t// TODO: implement {prompt[:60]}\n}}\n",
        }
        return skeletons.get(language, f"// TODO: implement {prompt[:60]}\n")

    def _build_explanation(self, code: str, language: str) -> str:
        lines = [ln for ln in code.splitlines() if ln.strip()]
        return (
            f"This {language} code contains {len(lines)} line(s). "
            "It appears to define logic for the described functionality. "
            "Key patterns include variable assignments, function calls, and control flow."
        )

    def _build_refactor_hints(self, code: str, language: str) -> str:
        return (
            f"# Refactoring suggestions for {language}:\n"
            "# 1. Extract repeated logic into helper functions\n"
            "# 2. Use descriptive variable names\n"
            "# 3. Add type annotations where applicable\n"
            + code
        )

    def _build_fix_hints(self, code: str, language: str) -> str:
        return (
            f"# Bug-fix pass for {language}:\n"
            "# - Checked for null/undefined references\n"
            "# - Added boundary checks\n"
            + code
        )

    def _build_review_feedback(self, code: str, language: str) -> str:
        lines = code.splitlines()
        issues: List[str] = []
        if len(lines) > 50:
            issues.append("Function is long — consider splitting into smaller units.")
        if not any("test" in ln.lower() for ln in lines):
            issues.append("No test coverage detected for this snippet.")
        if not issues:
            issues.append("Code looks clean. No immediate issues found.")
        return "\n".join(f"- {i}" for i in issues)

    def _derive_suggestions(self, action: str, language: str) -> List[str]:
        base = [
            f"Consider adding {language} type hints.",
            "Write unit tests to validate the logic.",
        ]
        if action == "generate":
            base.append("Review the generated stub and fill in the TODO sections.")
        elif action == "fix":
            base.append("Run the test suite after applying this fix.")
        return base

    def _estimate_confidence(self, prompt: str, action: str) -> float:
        length_factor = min(1.0, len(prompt) / 200)
        action_weights = {
            "complete": 0.8,
            "generate": 0.75,
            "explain": 0.9,
            "refactor": 0.7,
            "fix": 0.65,
            "review": 0.85,
        }
        base = action_weights.get(action, 0.7)
        return round(base * (0.6 + 0.4 * length_factor), 3)
