# VERA ? Verified Execution Reasoning Agent

> "It doesn't say done until it's done."

A personal AI agent built on consequence-grounded execution.
Every tool call is verified before claiming success.
Every failure is logged as a training example.
Every session builds toward a better model.

## Core Principle
Current AI agents describe actions instead of taking them.
VERA verifies execution before claiming completion.

## Stack
- Local inference: Ollama (qwen3.5:9b)
- Execution harness: Python
- Memory: Obsidian-compatible Markdown + SQLite
- Skills: SKILL.md pattern
- Training: QLoRA via Unsloth (when dataset is ready)

## Docs
- [MANIFESTO.md](docs/MANIFESTO.md) ? the founding document
