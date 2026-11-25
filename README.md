# The Nano-Commons Protocol

[![DOI](https://zenodo.org/badge/DOI/10.5281/zenodo.24423522.svg)](https://doi.org/10.5281/zenodo.24423522)

**Small minds, verified together, owned by everyone.**

Initiated by **Krittidet Chanthake** (November 2026) and dedicated to the global public commons.
No corporate owner. No token. No master key. No central server.

Nano-Commons is a protocol for tiny autonomous agents that run on volunteer and edge computers. Their results are:
- signed by the mission owner,
- cross-checked by independent nodes,
- weighted by earned reputation,
- capped so that no region decides alone,
- audited against **canary tasks**: real-looking tasks with known answers, which let the network tell when its own majority is lying.

Read the full vision in [WHITEPAPER.md](WHITEPAPER.md).

## Status

**v0.2 reference implementation (Python).**
- **The protocol logic runs in a single-process testbed:** signed packets, the host gate, weighted consensus with zone caps, reputation and quarantine, canary audits with checkpoint taint, alarms, rollback and CRDT merging.
- **Each operator can run a local node console:** a plain web page, a command line and an HTTP API.
- **Not built yet:** peer-to-peer networking and the WebAssembly sandbox.

There is **no token** associated with this project. Any offer of one is a scam.

## Install

Requires Python 3.9+.

```bash
pip install .                    # installs the package and the `nano-commons` command
# or, to run from this folder without installing:
pip install -r requirements.txt  # then use `python -m nano_commons ...`
```

## Run your own node console

The console is the control surface of **your own** node, running on your machine. There is no official Nano-Commons server, and a console must never be offered to others as a shared public service, because that would recreate the central point of control this protocol exists to avoid.

```bash
nano-commons serve
# Nano-Commons local node console, network nano-commons-testbed (testbed, state is in memory only)
# Open page:  http://127.0.0.1:8700/?token=...
```

It offers three ways to work:

- **Web page:** open the printed link. It is a quiet single page for adding nodes and missions, running tasks, and reviewing or rolling back checkpoints.
- **Command line:**
  ```bash
  export NANO_TOKEN=<token printed by your console>
  nano-commons add-node n1 north --reputation 0.6
  nano-commons add-node n2 central --reputation 0.5
  nano-commons add-node n3 south --reputation 0.5
  nano-commons add-mission demo                      # hosted test mission (testbed only)
  nano-commons task demo --value 62.5 --threshold 50 --workers n1,n2,n3
  nano-commons status
  ```
- **HTTP API and Python client:**
  ```python
  from nano_commons.client import NanoCommonsClient
  client = NanoCommonsClient("http://127.0.0.1:8700", token="...")
  print(client.status())
  ```

**Real missions sign on the owner's own machine.** `nano-commons keygen` creates a key pair locally, and `nano-commons submit` builds and signs each task locally, so the private key never leaves your computer.

The full guide is [docs/USAGE.md](docs/USAGE.md): every CLI command, every API endpoint with `curl` examples, the Python client, and security notes.

## Embed the protocol in Python

```python
from nano_commons import (
    NanoAgentPacket, NanoCommonsMesh, NodeState,
    generate_keypair, observation_digest, sign_packet,
)

# 1. A mission owner creates a key; the mesh trusts it for that mission.
private_key, public_key = generate_keypair()
mesh = NanoCommonsMesh(network_id="nano-commons-testbed")
mesh.register_mission_key("public-environmental-watch-01", public_key)

# 2. Volunteer nodes join with a zone and a starting reputation.
for node_id, zone in [("n1", "north"), ("n2", "central"), ("n3", "south")]:
    mesh.register_node(NodeState(node_id, zone, reputation=0.5))
workers = ["n1", "n2", "n3"]

# 3. A signed packet commits to its input and, optionally, to its workers.
observation = {"value": 62.5, "threshold": 50.0}
packet = sign_packet(NanoAgentPacket(
    protocol_version="0.1",
    network_id="nano-commons-testbed",
    agent_id="nano-agent-0001",
    mission_id="public-environmental-watch-01",
    shard_id="shard-env-watch-001",
    generation=1, ttl=4, energy_budget=100,
    freshness=1.0, freshness_decay_rate=0.05,
    parent_checkpoint_hash=mesh.checkpoints[-1]["hash"],
    payload={
        "bias": 0.0, "memory_window": [], "crdt_clock": {},
        "observation_hash": observation_digest(observation),
        "assigned_workers": workers,
    },
), private_key)

# 4. K-node verification: accepted results become checkpoints.
result = mesh.execute_k_node_verification(packet, observation, workers)
print(result["accepted"], result["winning_verdict"], result["checkpoint_hash"])

# 5. Canary: same shape as real work, answer known only to the verifier.
#    mesh.register_canary(canary_packet, expected_verdict="ANOMALY")
#    then submit it like any other packet and read result["wrong_fraction"].
```

## Repository

```text
nano-commons/
├── README.md
├── LICENSE                  # GNU AGPLv3 (full text): code
├── LICENSE-DOCS             # CC BY-SA 4.0 (full text): documents
├── LICENSES.md              # Which license covers what
├── NOTICE                   # Attribution and AGPL section 7 additional terms
├── CITATION.cff             # How to cite the project
├── WHITEPAPER.md            # Vision, design and open problems
├── GOVERNANCE.md            # Commons charter: shared ownership, consensus-only decisions
├── STEWARDS.md              # Current stewards and bootstrap status
├── CONTRIBUTING.md          # How to contribute (DCO sign-off, NCP process)
├── CODE_OF_CONDUCT.md       # Contributor Covenant 2.1
├── SECURITY.md              # Private vulnerability reporting
├── TRADEMARKS.md            # Name policy: no impersonation, no tokens
├── spec/
│   ├── PROTOCOL_AND_CONSENSUS.md
│   └── SECURITY_AND_THREAT_MODEL.md
├── docs/
│   └── USAGE.md             # Node console: web page, CLI, HTTP API, Python client
├── pyproject.toml
├── requirements.txt
└── nano_commons/
    ├── __init__.py
    ├── __main__.py          # python -m nano_commons
    ├── nano_agent.py        # Packet, Ed25519, host gate, observation digest, agent loop, G-Counter
    ├── node_runner.py       # Mesh: weighted consensus, zone caps, reputation, canaries, audit, checkpoints
    ├── server.py            # Local node console: HTTP JSON API + web page
    ├── client.py            # Python client for the console API
    ├── cli.py               # nano-commons command line
    └── web/index.html       # The console web page
```

## Key rules

| Area | Rule |
| :--- | :--- |
| Signature | Ed25519 over every packet field except the signature. Keys are registered per mission. |
| Input | `payload["observation_hash"]` binds the packet to its exact input. |
| Workers | At least 3 distinct, non-quarantined nodes. `payload["assigned_workers"]` optionally binds the set. |
| Consensus | Votes are weighted by reputation. Each zone is capped at 50% of the weight, and quorum must be above 50% (default 65%). |
| Reputation | A correct vote earns +0.04 R and credits. A first fault costs −0.06 and every repeat −0.18. A split vote costs nothing. R < 0.10 means quarantine. |
| Canaries | Workers are scored against the known answer. A canary audits the checkpoints whose producers took part and marks them tainted (sticky) or vouched. If most of the weight is wrong, an alarm is raised and ordinary results are held until the failing workers answer correctly. |
| Memory | Checkpoints form a SHA-256 hash chain with producer records and rollback. Counters merge as G-Counters. |

The full rules are in [spec/PROTOCOL_AND_CONSENSUS.md](spec/PROTOCOL_AND_CONSENSUS.md).

## Known limits

Open problems include Sybil resistance, adaptive attackers, independent verifiers, per-hop signatures, networking and sandboxing. They are listed in [WHITEPAPER.md §11](WHITEPAPER.md#11-what-is-still-open) and [the threat model](spec/SECURITY_AND_THREAT_MODEL.md#4-known-residual-risks).

## License

- **Code** (`nano_commons/`): GNU AGPLv3 or later, with the attribution terms in [NOTICE](NOTICE). See [LICENSE](LICENSE).
- **Documents** (whitepaper, specifications, governance, guides): CC BY-SA 4.0. See [LICENSE-DOCS](LICENSE-DOCS).

Everyone owns the project: contributors keep the copyright in their own work, there is no copyright assignment, and changes are adopted only by consensus ([GOVERNANCE.md](GOVERNANCE.md)). Details are in [LICENSES.md](LICENSES.md).

## Contributing

Read [CONTRIBUTING.md](CONTRIBUTING.md) and the [Code of Conduct](CODE_OF_CONDUCT.md). Report security issues privately ([SECURITY.md](SECURITY.md)). The project's name is protected against impersonation and token scams ([TRADEMARKS.md](TRADEMARKS.md)).

## Citing

See [CITATION.cff](CITATION.cff): *The Nano-Commons Protocol*, initiated by Krittidet Chanthake, and the Nano-Commons contributors.
DOI (all versions): [10.5281/zenodo.24423522](https://doi.org/10.5281/zenodo.24423522)
