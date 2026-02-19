#!/usr/bin/env python3
"""
TOR Coordinator — runs on the presenter/instructor's machine.

Responsibilities:
  1. Accept WebSocket connections from relay agents
  2. Route simulated packets through guard → middle → exit in sequence
  3. Broadcast real-time events to the HTML visualization via a browser WS client
  4. Optionally run an AI correlation analysis using the Anthropic API

Usage:
    pip install websockets anthropic
    python coordinator.py [--ai-key sk-ant-...]

Then open index.html and point its "Live Mode" WebSocket to ws://localhost:8765
(or ws://<presenter-ip>:8765 for students on the same network)
"""

import asyncio, json, time, random, argparse, string
import websockets
from websockets.server import serve

# ── State ─────────────────────────────────────────────────────────────────
agents = {}       # role -> websocket
browsers = set()  # HTML viz clients
circuit_counter = 0
timing_log = {"guard": [], "exit": []}  # for correlation

# ── Helpers ───────────────────────────────────────────────────────────────
def rand_ip(prefix="93.184"):
    return f"{prefix}.{random.randint(1,254)}.{random.randint(1,254)}"

def new_circuit_id():
    global circuit_counter
    circuit_counter += 1
    return f"C{str(circuit_counter).zfill(3)}"

async def broadcast_to_browsers(msg: dict):
    dead = set()
    for ws in browsers:
        try:
            await ws.send(json.dumps(msg))
        except Exception:
            dead.add(ws)
    browsers.difference_update(dead)

# ── Packet simulation ─────────────────────────────────────────────────────
async def send_circuit(src_ip: str = None, dst_ip: str = None):
    """Simulate a full circuit: client → guard → middle → exit → dest"""
    cid = new_circuit_id()
    src = src_ip or f"10.{random.randint(0,9)}.0.{random.randint(2,254)}"
    dst = dst_ip or rand_ip()
    pkt_base = {"circuit_id": cid, "src": src, "dst": dst,
                "size": random.randint(400, 1500), "ts": time.time()}

    # Notify browsers a new circuit is starting
    await broadcast_to_browsers({"type": "circuit_start", "data": {"id": cid, "src": src, "dst": dst}})
    print(f"[coordinator] New circuit {cid}: {src} → {dst}")

    prev_hop_ip = src
    roles = ["guard", "middle", "exit"]

    for i, role in enumerate(roles):
        pkt = {**pkt_base, "id": f"{cid}-{i+1}", "layers": 3 - i,
               "prev_hop": prev_hop_ip}
        if agents.get(role):
            # Send packet to the real relay agent machine
            await agents[role].send(json.dumps({"type": "packet", "data": pkt}))
            # Wait for its log response (with timeout)
            try:
                raw = await asyncio.wait_for(agents[role].recv(), timeout=3.0)
                log_msg = json.loads(raw)
                if log_msg.get("type") == "log":
                    log = log_msg["data"]
                    # Record timing for correlation
                    if role in ("guard", "exit"):
                        timing_log[role].append({"t": time.time(), "cid": cid})
                    # Forward to browsers
                    await broadcast_to_browsers({"type": "relay_log", "data": log})
            except asyncio.TimeoutError:
                print(f"[coordinator] {role} agent timed out — skipping")
        else:
            # No real agent connected — synthesize the log
            synth = synthesize_log(role, pkt)
            if role in ("guard", "exit"):
                timing_log[role].append({"t": time.time(), "cid": cid})
            await broadcast_to_browsers({"type": "relay_log", "data": synth})
            await asyncio.sleep(0.1 + random.uniform(0, 0.1))

        prev_hop_ip = {"guard": "10.0.1.2", "middle": "10.0.2.2", "exit": "10.0.3.2"}.get(role, "?")

    await broadcast_to_browsers({"type": "circuit_done", "data": {"id": cid}})

def synthesize_log(role, pkt):
    """Fallback: generate log entry without a live agent."""
    vis = {
        "guard":  (pkt["src"], "middle-relay", True, True),
        "middle": ("guard-node", "exit-node",   True, True),
        "exit":   ("middle-relay", pkt["dst"],  True, True),
    }[role]
    return {"relay": role, "circuit_id": pkt["circuit_id"],
            "ts": time.strftime("%H:%M:%S"), "from_ip": vis[0], "to_ip": vis[1],
            "from_known": vis[2], "to_known": vis[3],
            "layers_remaining": pkt["layers"] - 1, "synthesized": True}

# ── AI Correlation (optional) ──────────────────────────────────────────────
async def run_ai_correlation(api_key: str):
    """Use Anthropic to analyze timing logs and report correlation findings."""
    if not api_key: return
    try:
        import anthropic
        client = anthropic.Anthropic(api_key=api_key)
        ctx = {"guard_events": timing_log["guard"][-10:],
               "exit_events":  timing_log["exit"][-10:],
               "circuit_count": circuit_counter}
        prompt = (f"You are an AI correlation analyst. Given these TOR relay timing logs: "
                  f"{json.dumps(ctx)}\n"
                  f"Identify which guard events correlate with which exit events by timing proximity (<500ms). "
                  f"Report correlated pairs and confidence. Be brief.")
        msg = client.messages.create(model="claude-sonnet-4-20250514", max_tokens=400,
                                      messages=[{"role":"user","content":prompt}])
        result = msg.content[0].text
        print(f"\n[AI Correlation]\n{result}\n")
        await broadcast_to_browsers({"type": "ai_analysis", "data": {"text": result}})
    except Exception as e:
        print(f"[AI error] {e}")

# ── WebSocket Handler ──────────────────────────────────────────────────────
async def handler(ws):
    # First message determines if this is an agent or a browser
    try:
        raw = await asyncio.wait_for(ws.recv(), timeout=10)
        msg = json.loads(raw)
    except Exception:
        return

    if msg.get("type") == "register":
        role = msg["role"]
        agents[role] = ws
        print(f"[coordinator] Agent registered: {role} ({msg.get('ip','?')})")
        await broadcast_to_browsers({"type": "agent_connected", "data": {"role": role, "ip": msg.get("ip")}})
        # Keep connection alive
        try:
            async for _ in ws:
                pass
        finally:
            if agents.get(role) == ws:
                del agents[role]
                print(f"[coordinator] Agent disconnected: {role}")

    elif msg.get("type") == "browser":
        browsers.add(ws)
        print(f"[coordinator] Browser client connected ({len(browsers)} total)")
        # Send current agent status
        await ws.send(json.dumps({"type": "agent_status",
                                   "data": {"connected": list(agents.keys())}}))
        try:
            async for raw2 in ws:
                m2 = json.loads(raw2)
                if m2.get("type") == "send_packet":
                    asyncio.create_task(send_circuit(m2.get("src"), m2.get("dst")))
        finally:
            browsers.discard(ws)

# ── Packet scheduler ──────────────────────────────────────────────────────
async def auto_scheduler(interval: float, ai_key: str):
    """Automatically send circuits at a set interval."""
    count = 0
    while True:
        await asyncio.sleep(interval)
        if browsers:  # only run if someone is watching
            await send_circuit()
            count += 1
            if count % 5 == 0:  # AI analysis every 5 circuits
                asyncio.create_task(run_ai_correlation(ai_key))

# ── Main ──────────────────────────────────────────────────────────────────
async def main():
    p = argparse.ArgumentParser()
    p.add_argument("--host", default="0.0.0.0")
    p.add_argument("--port", type=int, default=8765)
    p.add_argument("--interval", type=float, default=2.5, help="Auto-send interval (seconds)")
    p.add_argument("--ai-key", default="", help="Anthropic API key for live correlation analysis")
    args = p.parse_args()

    print(f"[coordinator] Starting on {args.host}:{args.port}")
    print(f"[coordinator] Waiting for relay agents to connect…")
    print(f"[coordinator] Open index.html and enter ws://localhost:{args.port} in Live Mode")

    async with serve(handler, args.host, args.port):
        await asyncio.gather(
            asyncio.get_event_loop().create_future(),  # run forever
            auto_scheduler(args.interval, args.ai_key),
        )

if __name__ == "__main__":
    asyncio.run(main())
