"""
Processor Agent — AutoGen AssistantAgent + AXME Human Approval

Listens for process_analysis intents via AXME inbox, processes the analysis
results using an AutoGen agent, then requests human approval before finalizing.

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

processor = AssistantAgent(
    name="Processor",
    system_message=(
        "You are a data processor. Given an analysis result:\n"
        "1. Validate the analysis is complete and well-formed\n"
        "2. Generate actionable recommendations\n"
        "3. Prioritize findings by impact\n"
        "4. Create an executive summary\n"
        "Return structured JSON with keys: "
        "validation_passed, recommendations, priority_findings, executive_summary."
    ),
    llm_config=llm_config,
)

proxy = UserProxyAgent(
    name="Orchestrator",
    human_input_mode="NEVER",
    max_consecutive_auto_reply=3,
    code_execution_config=False,
)


def run_processing(analysis: str) -> str:
    """Run AutoGen processing conversation."""
    message = (
        f"Process this analysis result and generate recommendations:\n\n"
        f"{analysis}"
    )
    proxy.initiate_chat(processor, message=message, max_turns=3)

    messages = proxy.chat_messages.get(processor, [])
    for msg in reversed(messages):
        if msg.get("role") == "assistant" or msg.get("name") == "Processor":
            return msg.get("content", "")
    return "{}"


# ---------------------------------------------------------------------------
# AXME: Agent Loop
# ---------------------------------------------------------------------------

AGENT_URI = "agent://processor"

def main() -> None:
    api_key = os.environ.get("AXME_API_KEY")
    if not api_key:
        print("Error: AXME_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    if not os.environ.get("OPENAI_API_KEY"):
        print("Error: OPENAI_API_KEY environment variable is required", file=sys.stderr)
        sys.exit(1)

    client = AxmeClient(AxmeClientConfig(api_key=api_key))

    print(f"Processor Agent running as {AGENT_URI}")
    print("Polling AXME inbox for process_analysis intents...")

    while True:
        try:
            inbox = client.list_inbox(owner_agent=AGENT_URI)
            threads = inbox.get("threads", [])

            for thread in threads:
                intent_id = thread.get("intent_id")
                intent = client.get_intent(intent_id)
                payload = intent.get("payload", {})
                intent_type = intent.get("intent_type", "")

                if intent_type != "process_analysis":
                    continue

                if intent.get("status") != "pending_action":
                    continue

                print(f"\n--- Processing analysis: {intent_id} ---")
                analysis = payload.get("analysis", "")
                print(f"Analysis length: {len(analysis)} chars")

                # Run AutoGen processing
                processed = run_processing(analysis)
                print(f"Processing complete: {processed[:200]}...")

                if payload.get("requires_human_approval", False):
                    # Request human approval via AXME — durable wait
                    print("Requesting human approval via AXME...")
                    client.resume_intent(
                        intent_id,
                        {
                            "status": "pending_human_approval",
                            "processed_result": processed,
                            "message": "Analysis processed. Awaiting human approval before "
                                       "publishing results.",
                        },
                        owner_agent=AGENT_URI,
                    )
                    print(f"Intent {intent_id} waiting for human approval (can take hours/days)")
                    print("Use AXME CLI or dashboard to approve:")
                    print(f"  axme intent resume {intent_id} --payload '{{\"approved\": true}}'")
                else:
                    # No approval needed — resolve directly
                    client.resolve_intent(
                        intent_id,
                        {
                            "status": "completed",
                            "processed_result": processed,
                        },
                        owner_agent=AGENT_URI,
                    )
                    print(f"Resolved processing intent: {intent_id}")

        except KeyboardInterrupt:
            print("\nShutting down Processor Agent...")
            break
        except Exception as exc:
            print(f"Error processing inbox: {exc}", file=sys.stderr)

        time.sleep(3)


if __name__ == "__main__":
    main()
