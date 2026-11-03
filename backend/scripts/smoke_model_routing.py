"""Standalone live smoke test for multi-model routing in VeriFact.

Tests routing to all registered models (Gemma, GLM, Qwen, Phi-4, OpenRouter/Liquid)
through ModelClientLLMAdapter without consuming unnecessary credits.
Only queries providers that have configured credentials.
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from app.config import get_settings
from app.llm.base import LLMModelNotFoundError, LLMUnavailableError
from app.llm.providers import ModelClientLLMAdapter
from app.llm.registry import MODEL_REGISTRY, is_model_configured, resolve_model_id


async def main() -> int:
    settings = get_settings()
    print("=" * 60)
    print(f"VeriFact Model Routing Smoke Test (LLM_MODE: {settings.llm_mode})")
    print("=" * 60)

    adapter = ModelClientLLMAdapter(settings=settings)

    all_ok = True
    for model_id, mdef in MODEL_REGISTRY.items():
        configured = is_model_configured(model_id, settings)
        status_label = "[CONFIGURED]" if configured else "[NOT CONFIGURED]"
        print(f"\nModel: {mdef.display_name} ({model_id})")
        print(f"  Provider: {mdef.provider_display}")
        print(f"  Identifier: {mdef.default_model_name}")
        print(f"  Status: {status_label}")

        if not configured:
            print("  -> Skipped live call (no credentials configured).")
            continue

        try:
            print(f"  -> Testing complete_text(model='{model_id}') ...")
            resp = await adapter.complete_text(
                model=model_id,
                system_prompt="You are a concise fact-checker. Respond in 5 words or fewer.",
                user_prompt="Is Canberra the capital of Australia?",
                max_tokens=20,
            )
            print(f"  [OK] Response: {resp.strip()[:60]}")
        except LLMUnavailableError as exc:
            print(f"  [UNAVAILABLE] {exc}")
            all_ok = False
        except Exception as exc:
            print(f"  [ERROR] {exc}")
            all_ok = False

    await adapter.aclose()
    print("\n" + "=" * 60)
    print("Smoke test finished.")
    return 0 if all_ok else 1


if __name__ == "__main__":
    raise SystemExit(asyncio.run(main()))

