#!/usr/bin/env python3
"""
TOR Relay Agent — runs on each classroom machine.
Role is passed as CLI arg: guard | middle | exit

Usage:
    python relay_agent.py --role guard   --coordinator 192.168.1.100:8765
    python relay_agent.py --role middle  --coordinator 192.168.1.100:8765
    python relay_agent.py --role exit    --coordinator 192.168.1.100:8765

Each agent:
  - Simulates receiving a packet from the previous hop
  - Strips one encryption layer (simulated)
  - Logs only what IT can see (source/dest visibility depends on role)
  - Forwards metadata to the central coordinator via WebSocket
  - Coordinator feeds the HTML visualization in real time
"""

import asyncio, json, time, random, argparse, socket
import websockets

# ── Role visibility rules (mirrors the HTML visualization) ────────────────
ROLE_VISIBILITY = {
    "guard":  {"sees_src": True,  "sees_dst": False, "sees_prev": False, "sees_next": True},
    "middle": {"sees_src": False, "sees_dst": False,  "sees_prev": True,  "sees_next": True},
    "exit":   {"sees_src": False, "sees_dst": True,   "sees_prev": True,  "sees_next": False},
}

NEXT_HOP = {"guard": "middle", "middle": "exit", "exit": "destination"}

# Simulated IPs (in a real setup these would be actual NIC addresses)
ROLE_IPS = {
    "guard":  "10.0.1.2",
    "middle": "10.0.2.2",
    "exit":   "10.0.3.2",
}

class RelayAgent:
    def __init__(self, role: str, coordinator: str, my_ip: str):
        self.role = role
        self.coordinator = f"ws://{coordinator}"
        self.my_ip = my_ip
        self.vis = ROLE_VISIBILITY[role]
        self.packet_count = 0
        self.ws = None

    def build_log_entry(self, pkt: dict) -> dict:
        """Build log entry based on what this role CAN see."""
        v = self.vis
        entry = {
            "relay":      self.role,
            "relay_ip":   self.my_ip,
            "circuit_id": pkt.get("circuit_id"),
            "ts":         time.strftime("%H:%M:%S"),
            "from_ip":    pkt["src"] if v["sees_src"] else (pkt.get("prev_hop", "???") if v["sees_prev"] else "???"),
            "to_ip":      pkt["dst"] if v["sees_dst"] else (NEXT_HOP[self.role] if v["sees_next"] else "???"),
            "from_known": v["sees_src"] or v["sees_prev"],
            "to_known":   v["sees_dst"] or v["sees_next"],
            "layers_remaining": pkt.get("layers", 3) - 1,
            "packet_size_bytes": pkt.get("size", 512),
        }
        print(f"[{self.role.upper()}] pkt#{pkt.get('id','?')} | "
              f"from={entry['from_ip']} -> to={entry['to_ip']} | "
              f"layers_left={entry['layers_remaining']}")
        return entry

    async def connect(self):
        print(f"[{self.role}] Connecting to coordinator at {self.coordinator}…")
        self.ws = await websockets.connect(self.coordinator)
        # Register with coordinator
        await self.ws.send(json.dumps({"type": "register", "role": self.role, "ip": self.my_ip}))
        print(f"[{self.role}] Connected. Waiting for packets…")

    async def run(self):
        await self.connect()
        async for raw in self.ws:
            msg = json.loads(raw)
            if msg.get("type") == "packet":
                self.packet_count += 1
                log = self.build_log_entry(msg["data"])
                # Send processed log back to coordinator
                await self.ws.send(json.dumps({"type": "log", "data": log}))
                # Simulate processing delay (real TOR adds jitter here)
                await asyncio.sleep(random.uniform(0.05, 0.15))
            elif msg.get("type") == "ping":
                await self.ws.send(json.dumps({"type": "pong", "role": self.role}))

async def main():
    p = argparse.ArgumentParser(description="TOR Relay Agent (Educational)")
    p.add_argument("--role", choices=["guard","middle","exit"], required=True)
    p.add_argument("--coordinator", default="localhost:8765", help="host:port of coordinator")
    p.add_argument("--ip", default=None, help="Override this machine's IP (auto-detect if omitted)")
    args = p.parse_args()

    my_ip = args.ip or socket.gethostbyname(socket.gethostname())
    print(f"[startup] Role={args.role} | IP={my_ip} | Coordinator={args.coordinator}")
    agent = RelayAgent(args.role, args.coordinator, my_ip)
    await agent.run()

if __name__ == "__main__":
    asyncio.run(main())
