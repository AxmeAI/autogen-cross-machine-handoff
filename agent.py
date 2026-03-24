"""AutoGen analyzer agent - AXME integration handler.

Listens for intents via SSE, analyzes data, resumes with result.
Full AutoGen integration requires OPENAI_API_KEY.
This simplified agent tests the AXME delivery and resume flow.

Usage:
    export AXME_API_KEY="<agent-key>"
    python agent.py
"""

import os, sys, time
sys.stdout.reconfigure(line_buffering=True)
from axme import AxmeClient, AxmeClientConfig

AGENT_ADDRESS = "autogen-analyzer-demo"

def handle_intent(client, intent_id):
    intent_data = client.get_intent(intent_id)
    intent = intent_data.get("intent", intent_data)
    payload = intent.get("payload", {})
    if "parent_payload" in payload:
        payload = payload["parent_payload"]

    dataset = payload.get("dataset", "unknown")
    analysis = payload.get("analysis_type", "unknown")

    print(f"  [AutoGen] Analyzing dataset: {dataset}...")
    time.sleep(1)
    print(f"  [AutoGen] Running {analysis}...")
    time.sleep(1)

    result = {
        "action": "complete",
        "dataset": dataset,
        "analysis_type": analysis,
        "findings": ["Upward trend detected in Q1", "Anomaly on Feb 15"],
        "analyzed_at": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
    }
    client.resume_intent(intent_id, result)
    print(f"  [AutoGen] Analysis complete: {len(result['findings'])} findings")

def main():
    api_key = os.environ.get("AXME_API_KEY", "")
    if not api_key:
        print("Error: AXME_API_KEY not set."); sys.exit(1)
    client = AxmeClient(AxmeClientConfig(api_key=api_key))
    print(f"Agent listening on {AGENT_ADDRESS}...")
    print("Waiting for intents (Ctrl+C to stop)\n")
    for delivery in client.listen(AGENT_ADDRESS):
        intent_id = delivery.get("intent_id", "")
        status = delivery.get("status", "")
        if intent_id and status in ("DELIVERED", "CREATED", "IN_PROGRESS"):
            print(f"[{status}] Intent received: {intent_id}")
            try:
                handle_intent(client, intent_id)
            except Exception as e:
                print(f"  Error: {e}")

if __name__ == "__main__":
    main()
