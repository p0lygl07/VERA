#!/usr/bin/env python3
"""
VERA Persistent Web Learning Engine v1.0
Searches the web on topics relevant to active projects,
summarizes findings, and writes to memory for VERA to read at startup.

Run: python src/vera_learn.py
Schedule: add to vera cron (daily or hourly)
"""

import json
import os
import sys
import datetime
import requests
from pathlib import Path

VERA_ROOT        = Path(__file__).parent.parent
MEMORY_PATH      = VERA_ROOT / "memory"
LEARNING_LOG     = MEMORY_PATH / "learned_knowledge.md"
OLLAMA_URL       = "http://localhost:11434/api/chat"
MODEL            = "qwen3.5:9b"

# Topics VERA actively monitors and learns about
LEARNING_TOPICS = {
    "bug_bounty": [
        "new bug bounty programs 2026",
        "HackerOne program updates",
        "web application vulnerabilities 2026",
        "OWASP top 10 2026",
        "Ping Identity authentication vulnerabilities",
    ],
    "cybersecurity": [
        "new CVEs this week",
        "penetration testing techniques 2026",
        "CTF writeups web exploitation",
        "cybersecurity news today",
    ],
    "ai_development": [
        "local LLM improvements 2026",
        "Ollama new models",
        "AI agent tool calling best practices",
        "faster whisper improvements",
        "edge TTS alternatives",
    ],
    "hardware_hacking": [
        "Flipper Zero Momentum firmware updates",
        "WiFi Pineapple new payloads",
        "ESP32 security research 2026",
        "hardware hacking techniques 2026",
    ],
    "vera_development": [
        "Python autonomous agent patterns",
        "voice recognition latency improvement",
        "AI self improvement techniques",
        "local AI JARVIS implementation",
    ],
}


def duckduckgo_search(query, max_results=5):
    """Search DuckDuckGo instant answers API."""
    try:
        url = "https://api.duckduckgo.com/"
        params = {
            "q": query,
            "format": "json",
            "no_html": "1",
            "skip_disambig": "1",
        }
        resp = requests.get(url, params=params, timeout=10)
        resp.raise_for_status()
        data = resp.json()

        results = []
        if data.get("AbstractText"):
            results.append({
                "title": data.get("Heading", query),
                "text": data["AbstractText"][:500],
                "url": data.get("AbstractURL", ""),
            })

        for topic in data.get("RelatedTopics", [])[:max_results]:
            if isinstance(topic, dict) and topic.get("Text"):
                results.append({
                    "title": topic.get("FirstURL", "").split("/")[-1].replace("_", " "),
                    "text": topic["Text"][:300],
                    "url": topic.get("FirstURL", ""),
                })

        return results
    except Exception as e:
        return [{"title": "Search error", "text": str(e), "url": ""}]


def summarize_for_vera(topic_name, search_results, query):
    """Ask VERA's model to summarize search results into actionable knowledge."""
    if not search_results:
        return None

    results_text = "\n".join([
        f"- {r['title']}: {r['text']}"
        for r in search_results if r.get("text")
    ])

    if not results_text.strip():
        return None

    try:
        payload = {
            "model": MODEL,
            "messages": [
                {
                    "role": "system",
                    "content": (
                        "You are VERA summarizing web research for your own knowledge base. "
                        "Extract only what is actionable, specific, and relevant to "
                        "Joshua Burton's work in cybersecurity, bug bounty, AI development, "
                        "hardware hacking, and CTF challenges. "
                        "Be concise -- 2-4 bullet points max. Skip generic advice."
                    )
                },
                {
                    "role": "user",
                    "content": (
                        f"Topic: {topic_name} | Query: {query}\n\n"
                        f"Search results:\n{results_text}\n\n"
                        "Summarize into 2-4 specific, actionable bullet points. "
                        "Only include what Josh would actually want to know or act on."
                    )
                }
            ],
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 2048},
        }
        resp = requests.post(f"{OLLAMA_URL.rstrip('/api/chat')}/api/chat",
                            data=json.dumps(payload), timeout=60)
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception as e:
        # Fallback: just return the raw results
        return results_text[:500]


def update_learning_log(topic_name, query, summary):
    """Append learned knowledge to the learning log."""
    MEMORY_PATH.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")

    entry = (
        f"\n\n## [{timestamp}] {topic_name}: {query}\n"
        f"{summary}\n"
        f"---"
    )

    with open(LEARNING_LOG, "a", encoding="utf-8") as f:
        f.write(entry)


def get_recent_learning(max_chars=2000):
    """Get recent learning entries to inject into VERA's context."""
    if not LEARNING_LOG.exists():
        return ""
    content = LEARNING_LOG.read_text(encoding="utf-8")
    # Return most recent entries
    return content[-max_chars:] if len(content) > max_chars else content


def run_learning_cycle(topics=None, max_queries=5):
    """
    Run a full learning cycle.
    topics: specific topic keys to search (None = all)
    max_queries: max searches to run per session
    """
    print("=" * 60)
    print("VERA Persistent Web Learning Engine v1.0")
    print(f"Running: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    topic_filter = topics or list(LEARNING_TOPICS.keys())
    queries_run = 0
    learned = []

    for topic_name, queries in LEARNING_TOPICS.items():
        if topic_name not in topic_filter:
            continue

        print(f"\n[VERA LEARN] Topic: {topic_name}")

        # Run 1-2 queries per topic
        for query in queries[:2]:
            if queries_run >= max_queries:
                break

            print(f"[VERA LEARN] Searching: {query}")
            results = duckduckgo_search(query)

            if results and any(r.get("text") for r in results):
                summary = summarize_for_vera(topic_name, results, query)
                if summary and len(summary.strip()) > 20:
                    update_learning_log(topic_name, query, summary)
                    learned.append((topic_name, query))
                    print(f"[VERA LEARN] Learned: {summary[:100]}...")
                else:
                    print(f"[VERA LEARN] No useful content for: {query}")
            else:
                print(f"[VERA LEARN] No results for: {query}")

            queries_run += 1

        if queries_run >= max_queries:
            break

    print(f"\n[VERA LEARN] Cycle complete: {len(learned)} items learned")
    print(f"[VERA LEARN] Knowledge log: {LEARNING_LOG}")

    # Write a startup injection file — VERA reads this at session start
    write_startup_knowledge()
    return learned


def write_startup_knowledge():
    """
    Write a condensed version of recent learning to inject at startup.
    VERA reads this file as part of her session context.
    """
    recent = get_recent_learning(max_chars=1500)
    if not recent.strip():
        return

    startup_path = MEMORY_PATH / "startup_knowledge.md"
    content = (
        f"# VERA Recent Learning\n"
        f"## Auto-updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"*What VERA has recently learned from the web:*\n"
        f"{recent}\n"
    )
    startup_path.write_text(content, encoding="utf-8")
    print(f"[VERA LEARN] Startup knowledge updated: {startup_path}")


def main():
    if len(sys.argv) >= 2:
        cmd = sys.argv[1].lower()

        if cmd == "status":
            if LEARNING_LOG.exists():
                lines = LEARNING_LOG.read_text(encoding="utf-8").split("\n")
                entries = [l for l in lines if l.startswith("## [")]
                print(f"Total learning entries: {len(entries)}")
                print("Recent 5:")
                for entry in entries[-5:]:
                    print(f"  {entry}")
            else:
                print("No learning log yet -- run vera_learn.py to start")

        elif cmd == "show":
            print(get_recent_learning(max_chars=3000))

        elif cmd in list(LEARNING_TOPICS.keys()):
            # Run specific topic
            run_learning_cycle(topics=[cmd], max_queries=3)

        elif cmd == "startup":
            write_startup_knowledge()
            print("Startup knowledge file updated.")

        else:
            print(f"Commands: status | show | startup | {' | '.join(LEARNING_TOPICS.keys())}")
    else:
        run_learning_cycle()


if __name__ == "__main__":
    main()
