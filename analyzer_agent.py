"""
Analyzer Agent — AutoGen AssistantAgent + AXME Cross-Machine Handoff

Listens for analyze_data intents via AXME inbox, runs an AutoGen
multi-agent conversation to analyze the data, then sends the result
to the processor agent on a different machine via AXME.

Requires: AXME_API_KEY, OPENAI_API_KEY
"""

from __future__ import annotations

import json
import os
import sys
import time

from axme import AxmeClient, AxmeClientConfig
from autogen import AssistantAgent, UserProxyAgent

# ---------------------------------------------------------------------------
# AutoGen: Agent Configuration
# ---------------------------------------------------------------------------

llm_config = {
    "config_list": [
        {
            "model": "gpt-4o-mini",
            "api_key": os.environ.get("OPENAI_API_KEY", ""),
        }
    ],
    "temperature": 0,
}

analyst = AssistantAgent(
    name="Analyst",
    system_message=(
        "You are a data analyst. When given data, analyze it thoroughly:\n"
        "1. Identify key patterns and anomalies\n"
        "2. Calculate summary statistics\n"
        "3. Assess data quality\n"
        "4. Provide actionable insights\n"
        "Return your analysis as structured JSON with keys: "
        "patterns, anomalies, quality_score (0-1), insights, and summary."
    ),
    llm_config=llm_config,
)

# UserProxyAgent acts as the orchestrator — no human input needed
proxy = UserProxyAgent(
    name="Orchestrator",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=3,
    code_execution_config=False,
)


def run_analysis(data: dict) -> str:
    """Run AutoGen multi-agent analysis conversation."""
    message = (
        f"Analyze this dataset and return structured JSON:\n\n"
        f"{json.dumps(data, indent=2)}"
    )
    proxy.initiate_chat(analyst, message=message, max_turns=3)

    # Get the last message from the analyst
    messages = proxy.chat_messages.get(analyst, [])
    for msg in reversed(messages):
        if msg.get("role") == "assistant" or msg.get("name") == "Analyst":
            return msg.get("content", "")
    return "{}"


# ---------------------------------------------------------------------------
# AXME: Agent Loop
# ---------------------------------------------------------------------------

AGENT_URI = "agent://analyzer"

def main() -> None:
    api_key = os.environ.get("AXME_API_KEY")
    if not api_key:
        print("Error: AXME_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    client = AxmeClient(AxmeClientConfig(api_key=api_key))

    print(f"Analyzer Agent running as {AGENT_URI}")
    print("Polling AXME inbox for analyze_data intents...")

    while True:
        try:
            inbox = client.list_inbox(owner_agent=AGENT_URI)
            threads = inbox.get("threads", [])

            for thread in threads:
                intent_id = thread.get("intent_id")
                intent = client.get_intent(intent_id)
                payload = intent.get("payload", {})
                intent_type = intent.get("intent_type", "")

                if intent_type != "analyze_data":
                    continue

                if intent.get("status") != "pending_action":
                    continue

                print(f"\n--- Analyzing data: {intent_id} ---")
                data = payload.get("data", {})
                print(f"Data keys: {list(data.keys()) if isinstance(data, dict) else 'raw'}")

                # Run AutoGen multi-agent analysis
                analysis_result = run_analysis(data)
                print(f"Analysis complete: {analysis_result[:200]}...")

                # Send result to processor agent on another machine via AXME
                process_intent_id = client.send_intent({
                    "intent_type": "process_analysis",
                    "to_agent": "agent://processor",
                    "payload": {
                        "analysis": analysis_result,
                        "source_data_keys": list(data.keys()) if isinstance(data, dict) else [],
                        "source_intent_id": intent_id,
                        "requires_human_approval": payload.get("requires_human_approval", True),
                    },
                })
                print(f"Sent process_analysis intent to Processor: {process_intent_id}")

                # Resolve our intent with the analysis result
                client.resolve_intent(
                    intent_id,
                    {
                        "status": "analysis_complete",
                        "analysis": analysis_result,
                        "process_intent_id": process_intent_id,
                    },
                    owner_agent=AGENT_URI,
                )
                print(f"Resolved analysis intent: {intent_id}")

        except KeyboardInterrupt:
            print("\nShutting down Analyzer Agent...")
            break
        except Exception as exc:
            print(f"Error processing inbox: {exc}", file=sys.stderr)

        time.sleep(3)


if __name__ == "__main__":
    main()
