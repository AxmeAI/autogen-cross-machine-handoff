# AutoGen Cross-Machine Handoff with AXME

AutoGen is great for multi-agent conversations — AssistantAgent and UserProxy
work seamlessly together. But when agents need to cross machine boundaries —
with durable retries, timeout enforcement, and human approval gates — that's
infrastructure you have to build yourself. Message queues, state persistence,
retry logic, timeout watchers. AXME handles all of it so you can focus on the
agent logic.

> **Alpha** -- AXME is in alpha. APIs may change. Not recommended for production
> workloads without contacting the team first. See [AXME Cloud Alpha](https://cloud.axme.ai/alpha).

---

## Before / After

### Before: DIY Cross-Machine Infrastructure

```python
# You end up building this yourself:
import redis, celery, requests, json, time, threading

# Message broker for cross-machine communication
celery_app = Celery('agents', broker='redis://...')

@celery_app.task(bind=True, max_retries=5)
def send_to_processor(self, analysis_result):
    try:
        resp = requests.post("http://processor-machine:8000/process", json=analysis_result)
        resp.raise_for_status()
    except Exception as exc:
        self.retry(exc=exc, countdown=60)

# Human approval? Build a database + polling + notification system...
# Timeout enforcement? Build a separate watchdog process...
# Observability? Instrument everything manually...
# 300+ lines before any AutoGen logic
```

### After: AXME Handles It

```python
# Analyzer agent sends result to processor on another machine via AXME
intent_id = client.send_intent({
    "intent_type": "process_analysis",
    "to_agent": "agent://processor",
    "payload": {"analysis": result, "requires_human_approval": True}
})
# AXME handles: cross-machine delivery, retries, human approval, timeouts
result = client.wait_for(intent_id, timeout_seconds=86400)
```

---

## Quick Start

### 1. Install dependencies

```bash
pip install -r requirements.txt
```

### 2. Configure environment

```bash
cp .env.example .env
# Edit .env with your AXME API key and OpenAI API key
```

### 3. Run the scenario

```bash
# Terminal 1 (Machine A): Start the analyzer agent
python analyzer_agent.py

# Terminal 2 (Machine B): Start the processor agent — can be a different machine
python processor_agent.py

# Terminal 3: Send data for analysis + processing
python initiator.py
```

The initiator sends data to the analyzer agent. The AutoGen analyzer processes
it with LLM reasoning, then AXME delivers the result to the processor agent on
a different machine. A human approval step gates the final output.

---

## How It Works

```
┌─────────────────────┐         ┌──────────────┐         ┌─────────────────────┐
│  Machine A          │         │  AXME Cloud   │         │  Machine B          │
│                     │         │               │         │                     │
│  ┌───────────────┐  │  send   │  ┌─────────┐  │  deliver│  ┌───────────────┐  │
│  │  Analyzer      │──┼────────▶│  Intent   │──┼────────▶│  Processor     │  │
│  │  (AutoGen      │  │         │  Queue    │  │         │  (AutoGen      │  │
│  │   Assistant)   │  │         │  + Retry  │  │         │   Assistant)   │  │
│  └───────────────┘  │         │  + Timeout│  │         │  └──────┬────────┘  │
│                     │         │  ┌─────────┐  │         │         │          │
│                     │         │  │ Human   │  │         │         │          │
│                     │         │  │ Approval│◀─┼─────────┼─────────┘          │
│                     │         │  │ Gate    │  │         │                     │
│                     │         │  └─────────┘  │         │                     │
└─────────────────────┘         └──────────────┘         └─────────────────────┘
```

1. **Initiator** sends an analysis intent to the analyzer agent via AXME
2. **Analyzer Agent** (AutoGen AssistantAgent) analyzes the data using LLM conversation
3. Analyzer sends a `process_analysis` intent to the processor via AXME (cross-machine, durable)
4. **Processor Agent** (AutoGen AssistantAgent) receives and processes the analysis
5. Processor requests **human approval** via AXME before finalizing
6. Human approves (can be hours or days later) -- AXME holds state durably
7. Processor completes, result flows back through AXME to the initiator

---

## What Each Component Does

| Component | Role | Framework |
|-----------|------|-----------|
| `analyzer_agent.py` | Analyzes data using LLM conversation | AutoGen |
| `processor_agent.py` | Processes analysis results, requests human approval | AutoGen |
| `initiator.py` | Sends data into the pipeline, observes lifecycle | AXME SDK |
| `scenario.json` | Defines agents, workflow, and approval gates | AXP Scenario |

**AutoGen** does the AI thinking (multi-agent conversation, LLM reasoning, tool use).
**AXME** does the infrastructure (cross-machine delivery, human gates, retries, timeouts).

---

## Works With

This pattern works with any AutoGen agent configuration. AXME is framework-agnostic —
it bridges agents across machines regardless of what framework they use internally:

- **AutoGen** agents (AssistantAgent, UserProxy, GroupChat)
- **LangGraph** / **LangChain** agents
- **OpenAI Agents SDK** agents
- **CrewAI** agents
- Plain Python scripts
- Any HTTP-capable service

---

## Related

- [AXME Python SDK](https://github.com/AxmeAI/axme-sdk-python) -- `pip install axme`
- [AXME Documentation](https://github.com/AxmeAI/axme-docs)
- [AXME Examples](https://github.com/AxmeAI/axme-examples) -- more patterns (delivery, durability, human-in-the-loop)
- [AXP Intent Protocol Spec](https://github.com/AxmeAI/axp-spec)
- [AutoGen Documentation](https://microsoft.github.io/autogen/)

---

Built with [AXME](https://github.com/AxmeAI/axme) (AXP Intent Protocol).
