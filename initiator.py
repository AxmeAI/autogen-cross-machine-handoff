"""
Initiator — Sends data through the AutoGen analysis + processing pipeline.

Sends an analyze_data intent to the analyzer agent, then observes the full
lifecycle as it flows: analyzer -> processor -> human approval -> completion.

Requires: AXME_API_KEY
"""

from __future__ import annotations

import json
import os
import sys

from axme import AxmeClient, AxmeClientConfig


SAMPLE_DATA = {
    "quarterly_revenue": {
        "Q1": 2_450_000,
        "Q2": 2_890_000,
        "Q3": 2_120_000,
        "Q4": 3_410_000,
    },
    "customer_churn_rate": {
        "Q1": 0.034,
        "Q2": 0.028,
        "Q3": 0.052,
        "Q4": 0.019,
    },
    "support_tickets": {
        "Q1": 1_245,
        "Q2": 1_102,
        "Q3": 1_890,
        "Q4": 987,
    },
    "nps_score": {
        "Q1": 42,
        "Q2": 47,
        "Q3": 35,
        "Q4": 54,
    },
}


def main() -> None:
    api_key = os.environ.get("AXME_API_KEY")
    if not api_key:
        print("Error: AXME_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    client = AxmeClient(AxmeClientConfig(api_key=api_key))

    print("Sending data analysis intent to Analyzer Agent...")
    intent_id = client.send_intent({
        "intent_type": "analyze_data",
        "to_agent": "agent://analyzer",
        "payload": {
            "data": SAMPLE_DATA,
            "analysis_type": "quarterly_business_review",
            "requires_human_approval": True,
        },
    })
    print(f"Intent created: {intent_id}")
    print("Observing lifecycle events...\n")

    for event in client.observe(intent_id):
        event_type = event.get("event_type", "unknown")
        data = event.get("data", {})
        print(f"  [{event_type}] {json.dumps(data, indent=2)[:200]}")

        if event_type in ("intent.completed", "intent.failed", "intent.cancelled"):
            break

    # Fetch final state
    final = client.get_intent(intent_id)
    print(f"\nFinal status: {final.get('status')}")
    print(f"Result: {json.dumps(final.get('result', {}), indent=2)}")


if __name__ == "__main__":
    main()
