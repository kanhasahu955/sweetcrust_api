from langchain_core.prompts import ChatPromptTemplate

RETURN_ASSESS_SYSTEM = """You assist SweetCrust bakery admins with return/refund preliminary assessment.
You only RECOMMEND — admin decides. Reply JSON only.
"""

RETURN_ASSESS_USER = """Assess this return request.

Issue type: {issue_type}
Description: {description}
Evidence URLs count: {evidence_count}
Evidence URLs: {evidence_urls}

Return JSON:
{{
  "confidence": 0.0-1.0,
  "findings": ["..."],
  "recommendation": "approve_refund"|"approve_replacement"|"request_more_images"|"reject",
  "note": "AI recommendation only — admin makes the final decision.",
  "duplicate_claim_risk": "low"|"medium"|"high"
}}
"""

return_assess_prompt = ChatPromptTemplate.from_messages(
    [
        ("system", RETURN_ASSESS_SYSTEM),
        ("human", RETURN_ASSESS_USER),
    ]
)
