#!/usr/bin/env python3
"""
VERA Persistent Web Learning Engine v2.0
RSS-based learning -- no bot detection, no API keys, always works.

Monitors curated RSS feeds on your actual topics:
- HackerOne disclosed reports
- NVD CVE feed
- PortSwigger research
- Krebs on Security
- Hacker News security
- And more

Run: python src/vera_learn.py
Schedule: add to Windows Task Scheduler or vera cron
"""

import json
import os
import sys
import time
import datetime
import requests
from pathlib import Path

VERA_ROOT    = Path(__file__).parent.parent
MEMORY_PATH  = VERA_ROOT / "memory"
LEARNING_LOG = MEMORY_PATH / "learned_knowledge.md"
OLLAMA_URL   = "http://localhost:11434/api/chat"
MODEL        = "qwen3.5:9b"

# RSS feeds organized by topic -- all public, no auth needed
RSS_FEEDS = {
    "bug_bounty": [
        {
            "name": "HackerOne Hacktivity",
            "url": "https://hackerone.com/hacktivity.rss",
            "description": "Public bug bounty disclosures",
        },
        {
            "name": "Intigriti Blog",
            "url": "https://blog.intigriti.com/feed/",
            "description": "Bug bounty tips and writeups",
        },
    ],
    "cybersecurity": [
        {
            "name": "NVD CVE Feed",
            "url": "https://nvd.nist.gov/feeds/xml/cve/misc/nvd-rss.xml",
            "description": "Critical CVE vulnerabilities",
        },
        {
            "name": "Krebs on Security",
            "url": "https://krebsonsecurity.com/feed/",
            "description": "Security news and analysis",
        },
        {
            "name": "Threatpost",
            "url": "https://threatpost.com/feed/",
            "description": "Cybersecurity news",
        },
    ],
    "web_security": [
        {
            "name": "PortSwigger Research",
            "url": "https://portswigger.net/research/rss",
            "description": "Web security research from Burp Suite team",
        },
        {
            "name": "OWASP News",
            "url": "https://owasp.org/feed.xml",
            "description": "OWASP project updates",
        },
    ],
    "ai_development": [
        {
            "name": "Hacker News AI",
            "url": "https://hnrss.org/newest?q=AI+agent+LLM&points=50",
            "description": "HN posts on AI with 50+ points",
        },
        {
            "name": "Hacker News Local LLM",
            "url": "https://hnrss.org/newest?q=ollama+local+LLM&points=20",
            "description": "Local LLM discussions",
        },
    ],
    "hardware_hacking": [
        {
            "name": "Hacker News Hardware",
            "url": "https://hnrss.org/newest?q=flipper+zero+ESP32+hardware+hacking&points=20",
            "description": "Hardware hacking discussions",
        },
        {
            "name": "Hackaday",
            "url": "https://hackaday.com/blog/feed/",
            "description": "Hardware hacking projects",
        },
    ],
    "ctf": [
        {
            "name": "CTFtime upcoming",
            "url": "https://ctftime.org/ctf/list/upcoming/rss/",
            "description": "Upcoming CTF competitions",
        },
        {
            "name": "Hacker News CTF",
            "url": "https://hnrss.org/newest?q=CTF+writeup&points=20",
            "description": "CTF writeups on HN",
        },
    ],
}


def fetch_rss(url, max_items=5, timeout=15):
    """Fetch and parse RSS feed using requests + basic XML parsing."""
    try:
        # Try feedparser first
        try:
            import feedparser
            feed = feedparser.parse(url)
            if feed.entries:
                items = []
                for entry in feed.entries[:max_items]:
                    summary = entry.get("summary", "")
                    # Strip HTML tags from summary
                    if "<" in summary:
                        try:
                            from bs4 import BeautifulSoup
                            summary = BeautifulSoup(summary, "html.parser").get_text()
                        except Exception:
                            import re
                            summary = re.sub(r"<[^>]+>", "", summary)
                    items.append({
                        "title": entry.get("title", "")[:100],
                        "summary": summary[:400],
                        "link": entry.get("link", ""),
                        "published": entry.get("published", ""),
                    })
                return items
        except ImportError:
            pass

        # Fallback: basic XML parsing with requests
        resp = requests.get(url, timeout=timeout, headers={
            "User-Agent": "VERA-Agent/1.0 (RSS Reader)"
        })
        resp.raise_for_status()

        import xml.etree.ElementTree as ET
        root = ET.fromstring(resp.content)

        # Handle both RSS and Atom formats
        ns = {"atom": "http://www.w3.org/2005/Atom"}
        items = []

        # RSS format
        for item in root.findall(".//item")[:max_items]:
            title = item.findtext("title", "")
            desc = item.findtext("description", "")
            link = item.findtext("link", "")
            pub = item.findtext("pubDate", "")

            # Strip HTML from description
            if desc and "<" in desc:
                import re
                desc = re.sub(r"<[^>]+>", " ", desc).strip()

            if title:
                items.append({
                    "title": title[:100],
                    "summary": desc[:400],
                    "link": link,
                    "published": pub,
                })

        # Atom format fallback
        if not items:
            for entry in root.findall(".//atom:entry", ns)[:max_items]:
                title = entry.findtext("atom:title", "", ns)
                summary = entry.findtext("atom:summary", "", ns)
                link_el = entry.find("atom:link", ns)
                link = link_el.get("href", "") if link_el is not None else ""
                if title:
                    items.append({
                        "title": title[:100],
                        "summary": summary[:400],
                        "link": link,
                        "published": "",
                    })

        return items

    except requests.exceptions.ConnectionError:
        print(f"[VERA LEARN] Cannot reach: {url}")
        return []
    except Exception as e:
        print(f"[VERA LEARN] RSS error for {url}: {e}")
        return []


def summarize_feed_items(topic_name, feed_name, items):
    """Summarize RSS items into actionable knowledge."""
    if not items:
        return None

    content = "\n".join([
        f"- {item['title']}: {item['summary'][:200]}"
        for item in items if item.get("title")
    ])

    if not content.strip() or len(content) < 50:
        # Just return titles if no summaries
        titles = [f"- {item['title']}" for item in items if item.get("title")]
        return "\n".join(titles[:5]) if titles else None

    try:
        payload = {
            "model": MODEL,
            "messages": [
                {"role": "system", "content": (
                    "You are VERA summarizing RSS feed content for your knowledge base. "
                    "Extract only what is actionable and relevant to Josh's work: "
                    "cybersecurity, bug bounty, AI development, hardware hacking, CTF. "
                    "2-3 bullet points max. Be specific and actionable."
                )},
                {"role": "user", "content": (
                    f"Feed: {feed_name} | Topic: {topic_name}\n\n"
                    f"Recent items:\n{content[:1000]}\n\n"
                    "Give 2-3 specific actionable bullet points Josh would care about."
                )}
            ],
            "stream": False,
            "options": {"temperature": 0.2, "num_ctx": 2048},
        }
        resp = requests.post(OLLAMA_URL, data=json.dumps(payload), timeout=45)
        resp.raise_for_status()
        return resp.json()["message"]["content"]
    except Exception:
        # Return raw titles as fallback
        return "\n".join([f"- {item['title']}" for item in items[:5]])


def update_learning_log(topic_name, feed_name, summary):
    """Append to learning log."""
    MEMORY_PATH.mkdir(parents=True, exist_ok=True)
    timestamp = datetime.datetime.now().strftime("%Y-%m-%d %H:%M")
    entry = (
        f"\n\n## [{timestamp}] {topic_name} | {feed_name}\n"
        f"{summary}\n---"
    )
    with open(LEARNING_LOG, "a", encoding="utf-8") as f:
        f.write(entry)


def get_recent_learning(max_chars=2000):
    if not LEARNING_LOG.exists():
        return ""
    content = LEARNING_LOG.read_text(encoding="utf-8")
    return content[-max_chars:] if len(content) > max_chars else content


def write_startup_knowledge():
    """Write condensed learning to startup file for VERA to read."""
    recent = get_recent_learning(max_chars=2000)
    if not recent.strip():
        return
    startup_path = MEMORY_PATH / "startup_knowledge.md"
    content = (
        f"# VERA Recent Learning from RSS\n"
        f"## Updated: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}\n\n"
        f"*Curated from bug bounty, cybersecurity, AI, hardware, CTF feeds:*\n"
        f"{recent}\n"
    )
    startup_path.write_text(content, encoding="utf-8")
    print(f"[VERA LEARN] Startup knowledge updated: {startup_path}")


def run_learning_cycle(topics=None, max_feeds=8):
    """Run full RSS learning cycle."""
    print("=" * 60)
    print("VERA Persistent Web Learning Engine v2.0 (RSS)")
    print(f"Running: {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}")
    print("=" * 60)

    topic_filter = topics or list(RSS_FEEDS.keys())
    feeds_processed = 0
    learned = []

    for topic_name, feeds in RSS_FEEDS.items():
        if topic_name not in topic_filter:
            continue
        print(f"\n[VERA LEARN] Topic: {topic_name}")

        for feed in feeds[:2]:
            if feeds_processed >= max_feeds:
                break

            print(f"[VERA LEARN] Reading: {feed['name']}")
            items = fetch_rss(feed["url"], max_items=5)

            if items:
                print(f"[VERA LEARN] Got {len(items)} items")
                summary = summarize_feed_items(topic_name, feed["name"], items)
                if summary and len(summary.strip()) > 15:
                    update_learning_log(topic_name, feed["name"], summary)
                    learned.append((topic_name, feed["name"]))
                    print(f"[VERA LEARN] Learned: {summary[:100]}...")
                else:
                    print(f"[VERA LEARN] No useful content")
            else:
                print(f"[VERA LEARN] No items from feed")

            feeds_processed += 1
            time.sleep(1)  # polite delay

        if feeds_processed >= max_feeds:
            break

    print(f"\n[VERA LEARN] Cycle complete: {len(learned)} feeds processed")
    if learned:
        write_startup_knowledge()
    return learned


def list_feeds():
    """List all configured RSS feeds."""
    print("VERA RSS Feed Registry:")
    for topic, feeds in RSS_FEEDS.items():
        print(f"\n  [{topic}]")
        for feed in feeds:
            print(f"    - {feed['name']}: {feed['url'][:60]}")


def main():
    if len(sys.argv) >= 2:
        cmd = sys.argv[1].lower()

        if cmd == "test":
            print("Testing RSS feeds...")
            # Test one feed from each topic
            for topic, feeds in list(RSS_FEEDS.items())[:3]:
                feed = feeds[0]
                print(f"\nTesting [{topic}]: {feed['name']}")
                items = fetch_rss(feed["url"], max_items=3)
                if items:
                    for item in items[:2]:
                        print(f"  - {item['title'][:70]}")
                else:
                    print(f"  No items (feed may be unreachable)")

        elif cmd == "feeds":
            list_feeds()

        elif cmd == "status":
            if LEARNING_LOG.exists():
                lines = LEARNING_LOG.read_text(encoding="utf-8").split("\n")
                entries = [l for l in lines if l.startswith("## [")]
                print(f"Total entries: {len(entries)}")
                for e in entries[-5:]:
                    print(f"  {e}")
            else:
                print("No learning log yet.")

        elif cmd == "show":
            print(get_recent_learning(3000))

        elif cmd == "startup":
            write_startup_knowledge()
            print("Startup knowledge file updated.")

        elif cmd in RSS_FEEDS:
            run_learning_cycle(topics=[cmd], max_feeds=4)

        elif cmd == "add":
            # Add a custom RSS feed
            if len(sys.argv) >= 5:
                topic = sys.argv[2]
                name = sys.argv[3]
                url = sys.argv[4]
                if topic not in RSS_FEEDS:
                    RSS_FEEDS[topic] = []
                RSS_FEEDS[topic].append({"name": name, "url": url,
                                          "description": "Custom feed"})
                print(f"Added feed: {name} to topic: {topic}")
                print("Note: custom feeds are not persistent yet — add to RSS_FEEDS dict manually")
            else:
                print("Usage: vera_learn.py add <topic> <name> <url>")
        else:
            print(f"Commands: test | feeds | status | show | startup | "
                  f"{' | '.join(RSS_FEEDS.keys())}")
            print("Or run with no args for full learning cycle")
    else:
        run_learning_cycle()


if __name__ == "__main__":
    main()
