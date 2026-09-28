from __future__ import annotations

import json
import os

from openai import OpenAI


MODEL = os.getenv("OPENAI_MODEL", "gpt-5.6-luna")


def generate_evidence_aware_brief(candidate: dict, profile: dict, api_key: str | None = None) -> dict | None:
    key = api_key or os.getenv("OPENAI_API_KEY")
    if not key:
        return None

    client = OpenAI(api_key=key)

    evidence = {
        "company_name": candidate.get("company_name", ""),
        "source_title": candidate.get("source_title", ""),
        "source_snippet": candidate.get("source_snippet", ""),
        "source_url": candidate.get("source_url", ""),
        "discovery_score": candidate.get("discovery_score", ""),
        "confidence": candidate.get("confidence", ""),
        "unknowns_to_validate": candidate.get("unknowns_to_validate", ""),
    }

    target = {
        "industry": profile.get("industry", ""),
        "countries": profile.get("countries", []),
        "regions": profile.get("regions", []),
        "business_models": profile.get("business_models", []),
        "required_keywords": profile.get("required_keywords", []),
        "target_roles": profile.get("target_roles", []),
        "value_proposition": profile.get("value_proposition", ""),
    }

    prompt = f"""
You are supporting B2B opportunity discovery.

Use ONLY the evidence provided below. Do not invent company facts, initiatives,
financials, employees, decision makers, expansion plans, technologies or buying signals.

Target profile:
{json.dumps(target, ensure_ascii=False)}

Evidence:
{json.dumps(evidence, ensure_ascii=False)}

Return valid JSON with:
- why_relevant: 2 concise sentences grounded only in evidence
- hypotheses_to_validate: up to 3 hypotheses, explicitly framed as hypotheses
- validation_questions: up to 4 questions for further research/discovery
- suggested_target_functions: roles/functions that are logical for this target profile,
  but do not claim any named person exists at the company
"""

    response = client.responses.create(
        model=MODEL,
        input=prompt,
    )

    text = response.output_text.strip()
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        return {
            "why_relevant": text,
            "hypotheses_to_validate": [],
            "validation_questions": [],
            "suggested_target_functions": [],
        }
