"""
llm_agent.py
------------
AI Agent for enriching bank statement transactions using LLM (OpenAI).
"""

import os
import json
import logging
from typing import List, Dict, Any

try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from dotenv import load_dotenv

load_dotenv()

logger = logging.getLogger(__name__)

# Constants
BATCH_SIZE = 40

# Schema definition for structured output
RESPONSE_SCHEMA = {
    "type": "json_schema",
    "json_schema": {
        "name": "transaction_enrichment_list",
        "strict": True,
        "schema": {
            "type": "object",
            "properties": {
                "results": {
                    "type": "array",
                    "description": "A list of structured transaction enrichments corresponding to the input list.",
                    "items": {
                        "type": "object",
                        "properties": {
                            "transaction_id": {
                                "type": "string",
                                "description": "Must exactly match the input transaction_id"
                            },
                            "transaction_type": {
                                "type": "string",
                                "description": "One of: IN_TRANSFER, OUT_TRANSFER, DEPOSIT, WITHDRAW, FEE, SALARY, IN_UNKNOWN, OUT_UNKNOWN"
                            },
                            "counterparty_name": {
                                "type": "string",
                                "description": "Extracted name of the person or entity (e.g. นายสมชาย, บริษัทเอบีซี). If none, leave empty string."
                            },
                            "confidence": {
                                "type": "number",
                                "description": "Confidence score from 0.0 to 1.0"
                            },
                            "nlp_promptpay": {
                                "type": "boolean",
                                "description": "True if the transaction description contains a PromptPay marker or phone/ID."
                            },
                            "nlp_accounts": {
                                "type": "string",
                                "description": "Comma-separated list of any account numbers found in the description."
                            }
                        },
                        "required": ["transaction_id", "transaction_type", "counterparty_name", "confidence", "nlp_promptpay", "nlp_accounts"],
                        "additionalProperties": False
                    }
                }
            },
            "required": ["results"],
            "additionalProperties": False
        }
    }
}

SYSTEM_PROMPT = """
You are a highly capable Thai financial analyst AI.
Your task is to analyze a batch of bank transactions and return structured JSON.
For each transaction, determine:

1. transaction_type:
- "IN_TRANSFER": Incoming money transfer
- "OUT_TRANSFER": Outgoing money transfer
- "DEPOSIT": Cash deposit (e.g. at CDM/Branch)
- "WITHDRAW": Cash withdrawal (e.g. at ATM/Branch)
- "FEE": Bank fees, card fees, SMS fees
- "SALARY": Payroll, salary, bonus
- "IN_UNKNOWN" / "OUT_UNKNOWN": Use if unsure based on description

2. counterparty_name:
- Extract the clear human or company name.
- Remove unwanted prefixes if they clutter, but keep them if they help identify an entity type.
- Do NOT use ATM or CDM or transaction codes as a name. Leave empty if no name is present.

Return ONLY valid JSON matching the schema.
"""

def enrich_transactions_batch(transactions: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """Send a batch to the LLM and return the parsed JSON dictionaries."""
    if not OpenAI:
        logger.warning("openai not installed. Skipping LLM enrichment.")
        return []

    api_key = os.getenv("LLM_API_KEY")
    if not api_key:
        logger.warning("LLM_API_KEY not set in .env. Falling back to rule-based.")
        return []

    client = OpenAI(api_key=api_key)
    model_name = os.getenv("LLM_MODEL_NAME", "gpt-4o-mini")

    prompt_data = json.dumps(transactions, ensure_ascii=False, indent=2)

    try:
        response = client.chat.completions.create(
            model=model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": f"Analyze these transactions:\n{prompt_data}"}
            ],
            response_format=RESPONSE_SCHEMA,
            temperature=0.1,
        )
        content = response.choices[0].message.content
        result = json.loads(content)
        
        if isinstance(result, dict) and "results" in result:
            return result["results"]
            
        logger.error("LLM returned unexpected JSON structure")
        return []
    except Exception as e:
        logger.error(f"Error calling LLM: {e}")
        return []

def run_llm_pipeline(df) -> dict:
    """Takes a normalised DataFrame, extracts minimal info, invokes LLM, and returns a dict mapping id->enrichment."""
    results_map = {}
    batch = []
    
    for idx, row in df.iterrows():
        txn_id = row.get("transaction_id", f"temp_{idx}")
        # Only send relevant columns to save tokens
        item = {
            "transaction_id": txn_id,
            "direction": str(row.get("direction", "")),
            "amount": float(row.get("amount", 0.0) or 0.0),
            "description": str(row.get("description", "")),
            "channel": str(row.get("channel", ""))
        }
        batch.append(item)
        
        if len(batch) >= BATCH_SIZE:
            logger.info(f"Sending batch of {len(batch)} transactions to LLM...")
            batch_res = enrich_transactions_batch(batch)
            for r in batch_res:
                results_map[r["transaction_id"]] = r
            batch = []
            
    if batch:
        logger.info(f"Sending final batch of {len(batch)} transactions to LLM...")
        batch_res = enrich_transactions_batch(batch)
        for r in batch_res:
            results_map[r["transaction_id"]] = r

    return results_map
