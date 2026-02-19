# ⬡ TOR Network — AI Correlation Analyst

> An interactive educational visualization showing onion routing, per-relay agent visibility, timing correlation attacks, and AI-powered traffic analysis.  
> **Live demo:** `https://zephyrsai.github.io/relay_ai_agent/`

---

## What Students Learn

| Concept | Visualization |
|---|---|
| Onion routing | Packet rings shed one layer per relay |
| Per-hop knowledge isolation | Agent log panels — each relay sees only adjacent hops |
| Circuit tracking | Color-coded multi-circuit timeline |
| Global passive adversary | Timing correlation arc linking Guard ↔ Exit |
| AI-assisted analysis | Claude analyst generates reports, answers questions live |

---

## Project Structure

```
tor-viz/
├── index.html          ← Self-contained visualization (no build needed)
├── relay_agent.py      ← Run on each classroom machine
├── coordinator.py      ← Run on presenter's machine
└── README.md
```

---

## Mode 1 — Standalone (GitHub Pages / Classroom Browser)

No setup. Open `index.html` or visit the GitHub Pages URL.

- Click **▶ Auto Demo** for a scripted walkthrough
- Click **☠ Correlation Attack** to enable the global adversary overlay
- Use the **AI Analyst panel** to get live commentary (requires API key — see below)

### API Key for AI Features

The AI Analyst is powered by Claude. In two cases:

| Context | What to do |
|---|---|
| Viewing inside **claude.ai** | Nothing — key is injected automatically |
| Viewing on **GitHub Pages** | Paste your `sk-ant-...` key into the API Key field in the panel |

The key is never stored beyond the browser session.

---

## Mode 2 — Multi-Machine Demo (Real Agents)

Run one machine per relay role on the same local network.

### Requirements

```bash
pip install websockets anthropic
```

### Step 1 — Instructor: Start the coordinator

```bash
# On instructor's machine (e.g. 192.168.1.100)
python coordinator.py --port 8765 --ai-key sk-ant-YOUR_KEY
```

### Step 2 — Students: Start relay agents

```bash
# Machine A — plays the Guard node
python relay_agent.py --role guard --coordinator 192.168.1.100:8765

# Machine B — plays the Middle relay
python relay_agent.py --role middle --coordinator 192.168.1.100:8765

# Machine C — plays the Exit node
python relay_agent.py --role exit --coordinator 192.168.1.100:8765
```

### Step 3 — Open visualization

Open `index.html` in any browser. The visualization auto-connects to the coordinator WebSocket and receives live relay logs from the student machines.

### What happens

```
index.html ←──(WS)──→ coordinator.py ←──(WS)──→ relay_agent.py (guard)
                                      ←──(WS)──→ relay_agent.py (middle)
                                      ←──(WS)──→ relay_agent.py (exit)
```

Each agent processes its packet, strips a layer, logs only what its role permits, and sends the sanitized log to the coordinator. The coordinator forwards everything to the browser visualization and periodically runs AI correlation analysis.

---

## Architecture

```
  Client ──► Guard Node ──► Middle Relay ──► Exit Node ──► Destination
   💻         🤖 agent        🤖 agent        🤖 agent        🖥
              Sees:           Sees:           Sees:
              real client IP  guard IP only   destination IP
              + next hop      + exit IP       + prev hop

              ↓ logs to      ↓ logs to       ↓ logs to
              coordinator    coordinator     coordinator
                                ↓
                         AI Analyst (Claude)
                         correlates guard + exit timing
```

---

## Suggested Classroom Script (45 min)

### Phase 1 — Normal TOR (10 min)
1. Open the visualization. Run **▶ Auto Demo**.
2. Point out: each relay's agent log shows only partial info.
3. Ask: *"Why can't the Guard node figure out the destination?"*
4. Ask: *"What would the Middle relay need to deanonymize someone?"*

### Phase 2 — Agent Deep Dive (10 min)
5. Click **⊕ Send Packet** manually a few times.
6. Watch the relay logs in the sidebar — compare Guard vs Exit.
7. Ask the AI: **"📖 Explain TOR"** — walk through its response.
8. Ask students to predict what the Exit sees before clicking.

### Phase 3 — Correlation Attack (15 min)
9. Enable **☠ Correlation Attack** mode.
10. Send several more packets. Watch the yellow arc appear over the network.
11. Point to the timing graph (bottom panel) — Guard events (↑) match Exit events (↓).
12. Click **⚡ Correlation Report** in the AI panel.
13. Discuss: *"What does this tell us about who can defeat TOR?"*
    - Requires a global adversary (ISP-level, national intelligence)
    - TOR adds jitter to resist this — show how delay changes things
    - High-latency mix networks (Nym, Mixnet) provide stronger guarantees

### Phase 4 — Real-World AI Use (10 min)
14. Click **🌐 Real-World Use** in the AI panel.
15. Discuss the AI analyst's answer: law enforcement, security research, ethics.
16. Use the chat box — ask the AI: *"Can TOR be broken by a coffee shop?"*
17. Compare what the AI says with what students expect.

---

## Key Talking Points

**Why TOR still works in practice:**
- Real adversaries don't control all relays
- Circuit paths are random — hard to predict in advance
- TOR adds jitter to timing to frustrate correlation
- Guard node rotation further limits exposure

**Where TOR fails:**
- Global passive adversary (NSA-scale)
- Both endpoints compromised
- Browser fingerprinting / JS exploits (nothing to do with routing)
- Traffic volume correlation even without content

**What AI adds to analysis:**
- Pattern matching across thousands of timing events at scale
- Anomaly detection (unusual circuit build rates)
- Cross-referencing with other signals (DNS, BGP)
- Human analysts can't do this manually — AI makes it tractable

---

## License

MIT — free for coursework, teaching, and research.
