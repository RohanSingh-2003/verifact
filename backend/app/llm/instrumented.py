from __future__ import annotations

from typing import Any

from app.llm.base import LLMClient, LLMError


class InstrumentedLLMClient(LLMClient):
    """Counts successful and failed LLM calls without changing MetaQA behavior."""

    def __init__(self, inner: LLMClient) -> None:
        self.inner = inner
        self.success = 0
        self.failed = 0

    @property
    def total(self) -> int:
        return self.success + self.failed

    def stats(self) -> dict[str, int]:
        return {"success": self.success, "failed": self.failed, "total": self.total}

    async def complete_json(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> dict[str, Any]:
        try:
            result = await self.inner.complete_json(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except LLMError:
            self.failed += 1
            raise
        self.success += 1
        return result

    async def complete_text(
        self,
        *,
        model: str,
        system_prompt: str,
        user_prompt: str,
    ) -> str:
        try:
            result = await self.inner.complete_text(
                model=model,
                system_prompt=system_prompt,
                user_prompt=user_prompt,
            )
        except LLMError:
            self.failed += 1
            raise
        self.success += 1
        return result
