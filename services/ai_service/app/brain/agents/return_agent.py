from __future__ import annotations

from package.logger import get_logger
from typing import Any

from app.config import get_settings

logger = get_logger(__name__)


class ReturnAgent:
    def assess(self, issue_type: str, evidence_urls: list[str], description: str | None) -> dict[str, Any]:
        heuristic = self._heuristic(issue_type, evidence_urls, description)
        settings = get_settings()
        if not settings.llm_configured or not settings.llm_api_key:
            return heuristic
        try:
            from app.brain.llm import get_chat_model
            from app.brain.parser.returns import parse_return_assess
            from app.brain.prompts.return_assessment import return_assess_prompt

            messages = return_assess_prompt.format_messages(
                issue_type=issue_type,
                description=description or "",
                evidence_count=len(evidence_urls or []),
                evidence_urls=", ".join(evidence_urls or [])[:500],
            )
            model = get_chat_model(temperature=0.1)
            if settings.llm_provider.lower() in ("openai", "groq"):
                try:
                    model = model.bind(response_format={"type": "json_object"})
                except Exception:
                    pass
            raw = model.invoke(messages).content
            parsed = parse_return_assess(raw if isinstance(raw, str) else str(raw))
            if not parsed.get("findings"):
                parsed["findings"] = heuristic["findings"]
            parsed["provider"] = f"langchain:{settings.llm_provider}"
            return parsed
        except Exception:
            logger.exception("LLM return assess failed — heuristic")
            return heuristic

    @staticmethod
    def _heuristic(issue_type: str, evidence_urls: list[str], description: str | None) -> dict[str, Any]:
        confidence = 0.55
        findings = []
        if evidence_urls:
            confidence += min(0.25, 0.08 * len(evidence_urls))
            findings.append("Evidence images attached")
        else:
            findings.append("Insufficient image quality / missing photos")
        if issue_type in ("damaged", "melted", "packaging"):
            findings.append("Visible product/packaging damage likely")
            confidence += 0.1
        if issue_type == "wrong_product":
            findings.append("Possible wrong item — compare with order photo")
        if description and len(description) > 20:
            confidence += 0.05
        recommendation = (
            "approve_replacement" if issue_type in ("damaged", "melted", "wrong_product") else "request_more_images"
        )
        if confidence < 0.6:
            recommendation = "request_more_images"
        return {
            "confidence": round(min(confidence, 0.95), 2),
            "findings": findings,
            "recommendation": recommendation,
            "note": "AI recommendation only — admin makes the final decision.",
            "duplicate_claim_risk": "low",
            "provider": "heuristic",
        }


_agent = ReturnAgent()
assess_return = _agent.assess
