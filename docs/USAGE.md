# Using Nano-Commons

This guide covers the three ways to work with a Nano-Commons **node console**: a web page, a command line, and an HTTP API (with a Python client). All three talk to the same local process, which holds one testbed mesh.

## What the console is, and what it is not

- **It is your own node's control surface,** the same idea as a daemon's local RPC. You run it on your machine and it controls only what runs there.
- **It is not the Nano-Commons network.** There is no official or central Nano-Commons server, and nobody needs to connect to anyone else's console to take part.
- **Do not run a console as a shared public service.** Whoever operates it would hold the operator token, any hosted mission keys and the canary answer key, which is exactly the central point of control that the [Governance Charter](../GOVERNANCE.md) rules out.
- **Two features are for the testbed only.** *Hosted missions* (the console signs for you) and the *canary* endpoint (the console acts as verifier) exist for testing. Real mission owners sign on their own machines (`keygen` + `submit`), and on a real network canaries come from independent verifiers.
- **Today the console runs a single-process testbed.** When peer-to-peer networking arrives, it becomes the local control panel of each participant's node daemon.

**State is in memory only.** Stopping the server erases every node, mission, checkpoint and key it hosts.

## Install

Python 3.9 or newer.

```bash
pip install .                    # installs the package and the `nano-commons` command
# or, without installing:
pip install -r requirements.txt  # then run `python -m nano_commons ...` from the project folder
```

The only dependency is `cryptography`. Both forms work: `nano-commons <command>` and `python -m nano_commons <command>`.

## Start your node console

```bash
python -m nano_commons serve
```

It prints something like this:

```text
Nano-Commons local node console, network nano-commons-testbed (testbed, state is in memory only)
This console controls your own node only. There is no central Nano-Commons server.
API:        http://127.0.0.1:8700/api/status
Open page:  http://127.0.0.1:8700/?token=Qk3...
```

- The server listens on `127.0.0.1:8700`. Options: `--host`, `--port` (0 to 65535), `--network-id` (default `nano-commons-testbed`).
- The **operator token** guards every write. It means "the person operating this machine", nothing more: it gives no authority over any other node or over the network. Set it with `--token` or the `NANO_TOKEN` environment variable. If you set neither, a random one is made at start and printed in the "Open page" link. If you set it yourself, the console never prints it: the link is shown without `?token=`, so paste your token into the box on the page.
- Open the "Open page" link in a browser. The page keeps the token for that tab only and removes it from the address bar. The link with `?token=` still stays in your browser history, and in the terminal scrollback, so clear it on a shared machine. If the token is wrong or stale, the page drops it and asks for the right one; "change token" is always available. Without a token the page is read-only, and you can paste the token into the box at the top.
- Reading (`GET`) needs no token. Writing (`POST`) always does.

## Walk-through

Do it on the page, or use the CLI as below. Set the connection once per terminal:

```bash
export NANO_URL=http://127.0.0.1:8700
export NANO_TOKEN=<the token from the server output>
```

(PowerShell: `$env:NANO_TOKEN = "..."`.)

1. **Add at least three nodes in different zones.** One zone alone can never reach a quorum, so the zone spread matters.

   ```bash
   nano-commons add-node n1 north --reputation 0.65
   nano-commons add-node n2 central --reputation 0.45
   nano-commons add-node n3 south --reputation 0.40
   nano-commons add-node p1 east --reputation 0.50 --simulate-malicious   # optional: a node that poisons its votes
   ```

2. **Add a mission.** A mission owns a signing key. With no `--public-key` the console makes the key pair and keeps the private key in memory ("hosted"), so it can sign tasks for you. **Hosted missions are for testing only.** For a real mission, see [Sign on your own machine](#sign-on-your-own-machine-real-missions).

   ```bash
   nano-commons add-mission demo
   ```

3. **Run a task.** Nodes classify the value against the threshold and vote. The weighted result becomes a checkpoint if it reaches the quorum (default 65%).

   ```bash
   nano-commons task demo --value 62.5 --threshold 50 --workers n1,n2,n3,p1
   ```

   ```text
   verdict:     ANOMALY (75.0% of the weight)
   accepted:    True  (ok)
   checkpoint:  sha256:...
   faults:      p1
   ```

4. **Run a canary (testbed verifier).** On a real network this is the job of independent verifiers, not of one console: a canary is a task whose right answer you already know. Each worker is scored against that answer, so a node that follows a captured majority is still caught. A canary that most of the weight gets wrong raises an alarm, and ordinary results are held until a canary clears it.

   ```bash
   nano-commons canary demo --value 62.5 --threshold 50 --expect ANOMALY --workers n1,n2,n3,p1
   nano-commons checkpoints      # checkpoint 1 is now "vouched"
   nano-commons status
   ```

   A mesh refusal (for example `insufficient_workers`, or a replayed packet) is a normal answer, not a failure: the command prints `rejected: <reason>` and exits 0. Add `--json` to read the full result in scripts.

5. **Review or roll back.** `nano-commons review 1` marks a checkpoint as accepted by an operator. `nano-commons rollback 1` drops every checkpoint after #1.

## CLI reference

`nano-commons [--url URL] [--token TOKEN] [--json] <command> ...`

`--url` (default env `NANO_URL`, else `http://127.0.0.1:8700`), `--token` (default env `NANO_TOKEN`) and `--json` can go before or after the command. Output is human-readable; `--json` prints the raw JSON. The exit code is 1 for any error (server unreachable, HTTP error, bad key file) and 2 for bad arguments.

| Command | What it does |
| :--- | :--- |
| `serve [--host H] [--port P] [--token T] [--network-id N]` | Start the server (defaults `127.0.0.1`, `8700`). |
| `status` | Network, head checkpoint, alarm, canary accuracy, last trusted / suspect / tainted checkpoints. |
| `nodes` | List nodes with reputation, credits, quarantine state. |
| `add-node ID ZONE [--reputation R] [--simulate-malicious]` | Register a node (reputation default 0.15, range 0 to 1). The flag is for the testbed: the node poisons its votes. |
| `missions` | List missions (hosted or external) and their public keys. |
| `add-mission ID [--public-key B64]` | Without a key: hosted mission. With a public key: external mission. |
| `task MISSION --value V [--threshold T] --workers a,b,c [--no-bind]` | Hosted missions only. The server builds, signs and runs the task. |
| `canary MISSION --value V [--threshold T] --expect ANOMALY\|NORMAL --workers a,b,c [--no-bind]` | Testbed verifier, hosted missions only. Registers the known answer, then runs the task. |
| `checkpoints` | The chain with each checkpoint's status. |
| `rollback ID` | Keep checkpoints up to ID and drop the rest. |
| `review ID` | Mark checkpoint ID as reviewed. |
| `faults` | Faults logged against nodes. |
| `alarms` | The active alarm and the alarm history. |
| `keygen --out PREFIX` | Write `PREFIX.key` (private) and `PREFIX.pub`; print the public key. Refuses to overwrite either file. |
| `submit MISSION --key PREFIX.key --value V [--threshold T] --workers a,b,c [--no-bind]` | Sign a task on your machine and send it to the server. |

By default `task`, `canary` and `submit` bind the worker set into the signed packet (`payload.assigned_workers`), so whoever submits it cannot swap in friendlier workers. `--no-bind` leaves the choice to the submitter.

Workers are the node ids that run the task, separated by commas. At least 3 must be distinct, registered and not quarantined.

## HTTP API

Base URL `http://127.0.0.1:8700`. Bodies and replies are JSON. Every `POST` needs the header `Authorization: Bearer $NANO_TOKEN` (the word `Bearer` is case-insensitive, the token is not). Request bodies are limited to 64 KB.

Errors are `{"error": "..."}` with status 400 (bad input), 401 (missing or wrong token), 404 (unknown path or object), 405 (method not supported) or 413 (body too large). A task the mesh refuses (bad signature, too few workers, replay, alarm hold) is still HTTP 200, with `accepted: false` and a `reason`.

```bash
export NANO_URL=http://127.0.0.1:8700
AUTH="Authorization: Bearer $NANO_TOKEN"
```

### Reads (no token)

| Endpoint | Returns |
| :--- | :--- |
| `GET /` | The web page. |
| `GET /api/status` | `network_id`, `config`, `node_count`, `mission_count`, `checkpoint_count`, `head {checkpoint_id, hash}`, `alarm_active`, `canary_stats`, `last_trusted_checkpoint_id`, `suspect_checkpoint_ids`, `tainted_checkpoint_ids`. |
| `GET /api/nodes` | `{"nodes": [...]}` |
| `GET /api/missions` | `{"missions": [{mission_id, public_key, hosted}]}` |
| `GET /api/checkpoints` | `{"checkpoints": [{checkpoint_id, hash, shard_id, verified_verdict, status, workers}], "last_trusted_checkpoint_id"}`. Status is `unverified`, `vouched`, `tainted` or `reviewed`. |
| `GET /api/faults` | `{"faults": [...]}` |
| `GET /api/alarms` | `{"active": {...} or null, "history": [...]}` |
| `GET /api/held` | `{"held": [...]}`: results held while an alarm was up. |

```bash
curl $NANO_URL/api/status
curl $NANO_URL/api/nodes
curl $NANO_URL/api/missions
curl $NANO_URL/api/checkpoints
curl $NANO_URL/api/faults
curl $NANO_URL/api/alarms
curl $NANO_URL/api/held
```

### Writes (token required)

```bash
# Add a node. reputation defaults to 0.15, simulate_malicious to false.
curl -X POST $NANO_URL/api/nodes -H "$AUTH" \
  -d '{"node_id": "n1", "zone": "north", "reputation": 0.65, "simulate_malicious": false}'

# Add a mission. No public_key: hosted (the reply includes the public key; the private key never leaves the server).
curl -X POST $NANO_URL/api/missions -H "$AUTH" -d '{"mission_id": "demo"}'
# With a public key: external.
curl -X POST $NANO_URL/api/missions -H "$AUTH" -d '{"mission_id": "remote-1", "public_key": "<base64>"}'

# Run a task (hosted missions only). bind_workers defaults to true, hop_energy_cost to 15; shard_id is optional.
curl -X POST $NANO_URL/api/tasks -H "$AUTH" -d '{
  "mission_id": "demo",
  "observation": {"value": 62.5, "threshold": 50},
  "workers": ["n1", "n2", "n3"]
}'

# Run a canary (hosted missions only; expected_verdict is ANOMALY or NORMAL).
curl -X POST $NANO_URL/api/canaries -H "$AUTH" -d '{
  "mission_id": "demo",
  "observation": {"value": 62.5, "threshold": 50},
  "expected_verdict": "ANOMALY",
  "workers": ["n1", "n2", "n3"]
}'

# Submit a packet that was signed elsewhere (external or hosted mission).
# `packet` is a full signed packet, as produced by packet_to_dict; hop_energy_cost is optional.
curl -X POST $NANO_URL/api/packets -H "$AUTH" -d '{
  "packet": {"protocol_version": "0.1", "network_id": "...", "...": "..."},
  "observation": {"value": 62.5, "threshold": 50},
  "workers": ["n1", "n2", "n3"]
}'

# Roll back to a checkpoint (keeps it and everything before it).
curl -X POST $NANO_URL/api/rollback -H "$AUTH" -d '{"checkpoint_id": 1}'

# Mark a checkpoint as reviewed.
curl -X POST $NANO_URL/api/checkpoints/1/review -H "$AUTH"
```

On Windows `cmd`, quote JSON with double quotes and escape the inner ones, or use the CLI or the Python client instead.

## Python client

```python
from nano_commons.client import NanoCommonsClient, NanoCommonsError

client = NanoCommonsClient("http://127.0.0.1:8700", token="...")
try:
    for node_id, zone, rep in [("n1", "north", 0.65), ("n2", "central", 0.45), ("n3", "south", 0.40)]:
        client.add_node(node_id, zone, rep)
    client.add_mission("demo")
    result = client.task("demo", value=62.5, threshold=50.0, workers=["n1", "n2", "n3"])
    print(result["winning_verdict"], result["accepted"], result["checkpoint_hash"])
    client.canary("demo", value=62.5, expected_verdict="ANOMALY", workers=["n1", "n2", "n3"], threshold=50.0)
    print(client.status()["last_trusted_checkpoint_id"])
except NanoCommonsError as err:
    print(err.status, err.message)     # status 0 means the server could not be reached
```

There is one method per endpoint: `status`, `nodes`, `add_node`, `missions`, `add_mission`, `task`, `canary`, `submit_packet`, `checkpoints`, `rollback`, `review`, `faults`, `alarms`, `held`. To embed the mesh with no server at all, use `NanoCommonsMesh` directly (see [the README](../README.md#embed-the-protocol-in-python)).

## Sign on your own machine (real missions)

A hosted mission keeps its private key in the console's memory, which is fine for testing. For a real mission the owner keeps the key on their own computer and only signs there. The console never sees the private key; it only holds the public key.

1. **Make the key on your own computer.**

   ```bash
   nano-commons keygen --out mymission          # writes mymission.key (secret) and mymission.pub
   ```

2. **Register the mission as an external mission on your own console.** Use the console you run yourself, with your own operator token:

   ```bash
   export NANO_URL=http://127.0.0.1:8700
   export NANO_TOKEN=<your operator token>
   nano-commons add-mission my-mission --public-key "$(cat mymission.pub)"
   ```

   If your console runs on another machine that you own (a home server, a VM), do not expose it. Reach it through an SSH tunnel and keep its bind on loopback:

   ```bash
   ssh -L 8700:127.0.0.1:8700 you@your-other-machine     # then use NANO_URL=http://127.0.0.1:8700 as above
   ```

3. **Send signed tasks from the machine that holds the key:**

   ```bash
   nano-commons submit my-mission --key mymission.key --value 62.5 --threshold 50 --workers n1,n2,n3
   ```

`submit` asks `/api/status` for the current head, builds the packet, signs it **locally** and POSTs it to `/api/packets`. The private key is never sent. If the chain advances between the status call and the POST, the mesh answers `stale_parent_checkpoint`; run `submit` again.

From Python, do the same with `build_packet`, `sign_packet`, `packet_to_dict` and `NanoCommonsClient.submit_packet`:

```python
from nano_commons import build_packet, generate_keypair, public_key_to_b64, sign_packet
from nano_commons.client import NanoCommonsClient

private_key, public_key = generate_keypair()
client = NanoCommonsClient("http://127.0.0.1:8700", token="...")
client.add_mission("my-mission", public_key_to_b64(public_key))

status = client.status()
observation = {"value": 62.5, "threshold": 50.0}
packet = sign_packet(build_packet(
    network_id=status["network_id"], mission_id="my-mission",
    parent_checkpoint_hash=status["head"]["hash"], observation=observation,
    assigned_workers=["n1", "n2", "n3"]), private_key)
print(client.submit_packet(packet, observation, ["n1", "n2", "n3"]))
```

`PREFIX.key` holds the private key as plain base64 (raw 32-byte Ed25519). Protect it like a password. On Linux and macOS `keygen` creates it readable by you only (mode 0600). On Windows that mode does nothing and the file inherits the folder's permissions, so choose `--out` inside a folder only you can read.

## Security notes

- **Localhost by default.** The server binds `127.0.0.1`. If you bind another address, the server prints a warning.
- **The token is the only protection for writes.** Anyone who has it can change the mesh, so keep it out of shared logs and chat. The server compares it in constant time. Reads are public by design.
- **Do not expose it directly.** The server speaks plain HTTP, so the token and all traffic can be read on the network. To reach it from another machine, put it behind a TLS reverse proxy, or use an SSH tunnel (`ssh -L 8700:127.0.0.1:8700 host`) and keep the bind on loopback.
- **Slowloris is not handled.** A client that connects and then sends bytes very slowly can hold a handler thread for as long as it keeps trickling bytes (the 15 second timeout applies to each read, not to the whole request), and many such clients can exhaust the process. This is a known limit of the standard-library server; it is another reason to keep the console on loopback.
- **In-memory state.** Nothing is written to disk. A restart resets the mesh and creates new hosted keys.
- **Hosted missions keep private keys in server memory.** No endpoint ever returns them, but anyone who controls the server process, or has the token (and so can have the server sign tasks), can act as that mission. For a mission you care about, use an external mission and sign with `keygen` and `submit`.
- **One console per operator, never one console for everyone.** Offering your console to other people as "the" Nano-Commons service turns you into a central operator who holds their keys, their canary answers and a token over their work. That contradicts the Governance Charter. Each participant should run their own.
- **Testbed limits still apply.** This is a local simulation with a single mesh object, not a network. The token model is an operator convenience, not a replacement for the protocol's own safeguards. See [WHITEPAPER.md §11](../WHITEPAPER.md#11-what-is-still-open) and [the threat model](../spec/SECURITY_AND_THREAT_MODEL.md#4-known-residual-risks).
