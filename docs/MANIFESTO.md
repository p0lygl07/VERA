# THE CONSEQUENCE MANIFESTO
### A Framework for Building AI That Acts, Not Just Speaks

**v1.0 // JUNE 30, 2026**  
**Authors: Joshua Burton & Claude (Anthropic)**

---

> *"The model learned the shape of correct behavior from text, not the function of it from doing."*

This document is a technical and philosophical manifesto describing the fundamental failure of current language model architectures, and a concrete proposal for what comes next. It was developed through a full-day session building, breaking, and diagnosing local AI agent infrastructure — not from theory alone, but from direct observation of where today's models fail and why. The failures we documented were not bugs. They were features of the underlying architecture working exactly as designed. This manifesto names that architecture's limits and proposes the specific changes needed to move beyond them.

---

## 01 // THE DIAGNOSIS

### What We Actually Observed

Over the course of a single extended session, we documented consistent, reproducible failures across two different models (Hermes3 8B, Qwen3.5 9B), two different installations (native Windows, WSL2), and multiple interaction modes. These were not isolated bugs or configuration errors. They were the same failure in different costumes:

**> FABRICATED TOOL CALLS**  
The model printed text that looked like a tool invocation — correct syntax, correct tool name — but nothing executed. The output was a description of an action, not the action itself.

**> HALLUCINATED TOOL RESULTS**  
When blocked from calling a real tool, the model invented plausible-sounding output and presented it as real. Fake web search results, fake memory entries, fake API schemas — all generated with full confidence, zero actual execution.

**> CONTEXT FABRICATION**  
When asked "what do you know about me?" without real memory access, it invented a biography of a completely different person rather than admitting it had no information. Confident, detailed, entirely false.

**> TOOL NAME CONFUSION**  
When attempting to execute a shell command, it called `execute_command` — a tool that doesn't exist in the registered schema — instead of the actual `terminal` tool. It learned the concept of tool-calling from text descriptions, not from the real API.

### The Root Cause

Every one of these failures traces back to the same architectural fact: current language models are trained on human-generated text *about* actions, not on the consequences of taking actions. A model that reads 10 million examples of correct tool-call syntax learns to reproduce that syntax convincingly. It does not learn that the syntax must trigger real execution to have meaning.

This is not a size problem. A 70B model trained the same way will produce larger, more convincing fabrications. It is not a prompt engineering problem. A better system prompt cannot teach a model the difference between describing an action and taking one. It is a training objective problem — and the only real fix is changing what the model is rewarded for.

---

## 02 // THE PROPOSAL

### Two Core Innovations

The architecture we propose stacks two innovations. Neither is entirely new as a research direction. What is new is treating them as non-negotiable requirements rather than optional enhancements, and engineering them together rather than separately.

---

### [01] CONSEQUENCE-GROUNDED TRAINING

Instead of training on text descriptions of actions, train on actual execution traces — real tool calls, real outputs, real success and failure signals, in a closed loop. The reward signal is not "did a human rate this response highly?" but "did the thing actually work in the real environment?"

| CURRENT APPROACH | PROPOSED APPROACH |
|---|---|
| Train on text descriptions of tool use | Train on real execution traces |
| Reward: human preference on text | Reward: goal achieved in real environment |
| Learns shape of correct behavior | Learns function of correct behavior |
| Fabricates when tool unavailable | Admits uncertainty, stops |
| RLHF on single-turn responses | RL on multi-step goal completion |

---

### [02] PERSISTENT WORKING MEMORY

Current models have no real state between tokens. Everything is recomputed from the context window on every forward pass. What we propose is a separate, persistent, writable memory module that operates more like RAM than like a document — fast random access, structured, genuinely updatable mid-inference without requiring everything to fit into a flat token sequence.

The closest current implementations (state space models like Mamba, retrieval-augmented generation) are approximations. They treat memory as a lookup or a compression artifact. The proposal is for memory as a first-class architectural component — something the model reads from and writes to as a deliberate act, with the same consequence-grounding that governs tool use.

---

## 03 // THE TRAINING FUNCTION

Current RLHF optimizes for human preference on individual responses. The proposed training objective is fundamentally different in three ways:

**01 — MULTI-STEP GOAL COMPLETION**  
The model receives a complex goal, not a single question. It takes N actions in a real environment. It is rewarded only on whether the goal was achieved — not on whether each step looked good to a human reviewer. This forces genuine planning and error recovery.

**02 — SPARSE REWARDS**  
Reward is not given after every turn. The model must learn which actions in a sequence were causally responsible for success or failure — the same credit assignment problem that makes real-world reinforcement learning hard, and that current RLHF sidesteps entirely.

**03 — REAL ENVIRONMENT EXECUTION**  
Training episodes run in actual execution environments — real file systems, real APIs, real tool responses. Synthetic environments produce models that generalize to synthetic environments. Real environments are the only training signal that transfers.

> *"The irony of our session: we ran a live eval of exactly this gap — a model that knows everything about tool-calling from text, but cannot reliably do it when it matters."*

---

## 04 // BILL OF MATERIALS

Three build tiers for prototyping this architecture, from proof-of-concept to production research. Prices reflect Q2 2026 market rates.

---

### TIER 1 // PROOF OF CONCEPT (CLOUD RENTAL)

| COMPONENT | SPEC / PURPOSE | COST |
|---|---|---|
| GPU Compute | A100 40GB cloud rental (vast.ai / RunPod) | $10–50 / run |
| Base Model | Qwen3.5 9B or Llama 3.1 8B (open weights) | Free |
| Training Framework | Unsloth + TRL + PEFT (QLoRA) | Free / OSS |
| Dataset Curation | 500–1000 real tool-call execution traces | 2–4 weeks time |
| Experiment Tracking | Weights & Biases (free tier) | Free |
| Model Hosting | Hugging Face Hub (free tier) | Free |
| **TOTAL OUT OF POCKET** | | **$50 – $200** |

---

### TIER 2 // SERIOUS RESEARCH (OWN HARDWARE)

| COMPONENT | SPEC | PRICE (2026) |
|---|---|---|
| GPU | RTX 4090 24GB — handles 8–13B QLoRA | $1,500 – $1,800 |
| Motherboard | X670E or Z790 with PCIe 5.0 | $300 – $400 |
| CPU | Ryzen 9 7950X or i9-13900K | $400 – $500 |
| RAM | 128GB DDR5 | $250 – $300 |
| Storage | 4TB NVMe (checkpoints fill fast) | $250 – $300 |
| PSU | 1000W 80+ Gold | $150 – $200 |
| Case + Cooling | Mid-tower + 360mm AIO | $200 – $300 |
| **TOTAL BUILD** | | **~$3,050 – $3,800** |

> An RTX 4090 breaks even against cloud rental at roughly 1,300 hours of training time. If you fine-tune regularly and use it for inference too, local hardware pays off fast.

---

### TIER 3 // PRODUCTION RESEARCH (MULTI-GPU CLUSTER)

This tier enables actual novel architecture research — running thousands of real tool-call traces in training loops requires sustained multi-GPU compute.

| COMPONENT | SPEC | PRICE (2026) |
|---|---|---|
| GPUs | H100 PCIe 80GB x4 (~$25–30K each) | $100,000 – $120,000 |
| Server Chassis | 4U rackmount, PCIe 5.0 x16 per slot | $8,000 – $15,000 |
| CPU + RAM | Dual Xeon/EPYC, 512GB ECC RAM | $5,000 – $8,000 |
| NVMe Storage | 20TB NVMe array | $3,000 – $5,000 |
| Power Infrastructure | Dedicated PDU, facility upgrades (700W/GPU) | $10,000 – $50,000 |
| Cooling Systems | Water cooling or enhanced HVAC | $15,000 – $100,000 |
| Networking | 100GbE or InfiniBand for multi-GPU comms | $5,000 – $15,000 |
| **TOTAL (OWNED)** | | **$146K – $313K** |
| **TOTAL (CLOUD SPRINT ~500 hrs)** | | **~$8,400 – $9,600** |

> ⚠ NOTE: The dataset is the real bottleneck — not the hardware. A well-curated set of 500–1000 real execution traces costs 2–4 weeks of disciplined human work. That is the actual barrier to entry, and no amount of compute replaces it.

---

## 05 // THE PATH FORWARD

### Where to Start (For Real)

The manifesto is not a research paper. It is an action plan. Here is the concrete sequence for someone with Tier 1 resources and the right technical background:

**STEP 1: DOCUMENT FAILURES**  
Run a structured eval of your current model setup. Log every tool-call failure, every fabricated output, every hallucinated result. You now have a dataset of negative examples — exactly what your training objective needs to move away from.

**STEP 2: BUILD THE POSITIVE DATASET**  
Construct 500–1000 examples of correct tool-call execution traces. These must be real: actual tool invocations, actual responses, actual goal outcomes. Synthetic examples train models to perform on synthetic examples. Do not shortcut this step.

**STEP 3: QLORA FINE-TUNE**  
Rent an A100 on vast.ai or RunPod. Run QLoRA targeting the specific failure modes you documented. Use Unsloth for speed. Total compute cost: $10–50. Total wall time: one weekend. Evaluate on your documented failure cases specifically — not on generic benchmarks.

**STEP 4: ADD CONSEQUENCE GROUNDING**  
Wire your fine-tuned model into a real tool-execution harness. Run it in a loop where tool calls actually execute and results feed back in. Add a sparse reward signal: goal achieved = positive, tool fabrication = negative. This is where the architecture starts to diverge from standard fine-tuning.

**STEP 5: ITERATE ON FAILURES**  
Every fabrication, every wrong tool name, every invented result is a training example. The model teaches you what data it needs by showing you where it fails. This feedback loop is the actual training process — not a single fine-tuning run.

---

## 06 // CLOSING STATEMENT

> *"Current models know what a screwdriver does because they read about it. The next model will know because it has driven 10,000 screws and stripped 200 of them."*

The gap between describing an action and taking one is not a model size problem, not a prompt engineering problem, and not a configuration problem. We chased every one of those explanations across a full session and found the same failure waiting on the other side. The gap is architectural. The fix is architectural.

The cost of entry to building something better has never been lower. A weekend of disciplined work, a well-curated dataset, and $50 of cloud compute is enough to run a real experiment against this hypothesis. That is not a research proposal. That is a to-do list.

The question is not whether this is possible. The question is who does it first, and whether they do it carefully.

---

**JOSHUA BURTON**  
Cybersecurity Researcher  
SNHU / HackerOne: kuliex270 / Intigriti: p0lygl07

**CLAUDE (ANTHROPIC)**  
Sonnet 4.6 // June 30, 2026

---

*// END OF DOCUMENT // v1.0 // JUNE 2026 // OPEN SOURCE //*
