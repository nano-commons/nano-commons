# SPDX-License-Identifier: AGPL-3.0-or-later
# Copyright (C) 2026 Krittidet Chanthake and the Nano-Commons contributors
"""Command line interface: ``python -m nano_commons <command>`` or ``nano-commons <command>``."""

from __future__ import annotations

import argparse
import json
import math
import os
import sys
from typing import Any, Callable, Dict, List, Optional, Sequence

from .server import DEFAULT_NETWORK_ID
from .client import DEFAULT_URL, NanoCommonsClient, NanoCommonsError
from .nano_agent import (
    build_packet,
    generate_keypair,
    packet_to_dict,
    private_key_from_b64,
    private_key_to_b64,
    public_key_to_b64,
    sign_packet,
)


class CliError(Exception):
    """A problem to report on stderr with exit code 1."""


# --- argument types ------------------------------------------------------------


def _workers(text: str) -> List[str]:
    workers = [w.strip() for w in text.split(",") if w.strip()]
    if not workers:
        raise argparse.ArgumentTypeError("expected a comma-separated list such as a,b,c")
    return workers


def _finite_float(text: str) -> float:
    try:
        value = float(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a number: {text!r}") from None
    if not math.isfinite(value):
        raise argparse.ArgumentTypeError(f"must be a finite number, not {text!r}")
    return value


def _port(text: str) -> int:
    try:
        port = int(text)
    except ValueError:
        raise argparse.ArgumentTypeError(f"not a port number: {text!r}") from None
    if not 0 <= port <= 65535:
        raise argparse.ArgumentTypeError("port must be between 0 and 65535")
    return port


def _verdict(text: str) -> str:
    verdict = text.upper()
    if verdict not in ("ANOMALY", "NORMAL"):
        raise argparse.ArgumentTypeError("must be ANOMALY or NORMAL")
    return verdict


def build_parser() -> argparse.ArgumentParser:
    # The shared options work before or after the command; the subparser copies only
    # override the top-level value when they are actually given (default SUPPRESS).
    def shared(top: bool) -> argparse.ArgumentParser:
        p = argparse.ArgumentParser(add_help=False, argument_default=None if top else argparse.SUPPRESS)
        p.add_argument("--url", default=os.environ.get("NANO_URL", DEFAULT_URL) if top else argparse.SUPPRESS,
                       help=f"server URL (env NANO_URL, default {DEFAULT_URL})")
        p.add_argument("--token", default=os.environ.get("NANO_TOKEN") if top else argparse.SUPPRESS,
                       help="operator token for write commands, for this console only (env NANO_TOKEN)")
        p.add_argument("--json", action="store_true", default=False if top else argparse.SUPPRESS,
                       help="print raw JSON")
        return p

    parser = argparse.ArgumentParser(
        prog="nano-commons", parents=[shared(True)],
        description="Control your own Nano-Commons node console, or start one with 'serve'. "
                    "There is no central Nano-Commons server: each operator runs their own.")
    sub = parser.add_subparsers(dest="command", required=True, metavar="command")

    def add(name: str, help_: str, func: Callable, **kw: Any) -> argparse.ArgumentParser:
        p = sub.add_parser(name, parents=[shared(False)], help=help_, description=help_, **kw)
        p.set_defaults(func=func)
        return p

    p = add("serve", "start your local node console (HTTP API + web page)", _serve)
    p.add_argument("--host", default="127.0.0.1")
    p.add_argument("--port", type=_port, default=8700)
    p.add_argument("--network-id", default=DEFAULT_NETWORK_ID)

    add("status", "network summary", _status)
    add("nodes", "list nodes", _nodes)
    p = add("add-node", "register a node", _add_node)
    p.add_argument("node_id", metavar="ID")
    p.add_argument("zone")
    p.add_argument("--reputation", type=_finite_float, default=0.15)
    p.add_argument("--simulate-malicious", action="store_true",
                   help="testbed only: the node poisons its votes")

    add("missions", "list missions", _missions)
    p = add("add-mission", "register a mission (hosted = testbed only; real missions use --public-key)", _add_mission)
    p.add_argument("mission_id", metavar="ID")
    p.add_argument("--public-key", metavar="B64", help="external mission: you sign packets yourself")

    def task_args(p: argparse.ArgumentParser) -> None:
        p.add_argument("mission")
        p.add_argument("--value", type=_finite_float, required=True)
        p.add_argument("--threshold", type=_finite_float)
        p.add_argument("--workers", type=_workers, required=True, metavar="a,b,c")

    p = add("task", "run a task on a hosted test mission", _task)
    task_args(p)
    p.add_argument("--no-bind", action="store_true", help="do not bind the worker set in the signature")

    p = add("canary", "testbed verifier: run a canary task with a known answer", _canary)
    task_args(p)
    p.add_argument("--expect", type=_verdict, required=True, metavar="ANOMALY|NORMAL")
    p.add_argument("--no-bind", action="store_true", help="do not bind the worker set in the signature")

    add("checkpoints", "list checkpoints and their audit status", _checkpoints)
    p = add("rollback", "roll the chain back to a checkpoint", _rollback)
    p.add_argument("checkpoint_id", metavar="ID", type=int)
    p = add("review", "mark a checkpoint as reviewed by an operator", _review)
    p.add_argument("checkpoint_id", metavar="ID", type=int)
    add("faults", "list logged faults", _faults)
    add("alarms", "current alarm and alarm history", _alarms)

    p = add("keygen", "create an Ed25519 mission keypair on this machine", _keygen)
    p.add_argument("--out", required=True, metavar="PREFIX", help="writes PREFIX.key and PREFIX.pub")

    p = add("submit", "sign a task on this machine and send it to a node console", _submit)
    task_args(p)
    p.add_argument("--key", required=True, metavar="PREFIX.key", help="private key file from keygen")
    p.add_argument("--no-bind", action="store_true", help="do not bind the worker set in the signature")
    return parser


# --- output --------------------------------------------------------------------


def _table(rows: Sequence[Dict[str, Any]], columns: Sequence[str]) -> None:
    if not rows:
        print("(none)")
        return
    cells = [[str(row.get(c, "")) for c in columns] for row in rows]
    widths = [max(len(c), *(len(r[i]) for r in cells)) for i, c in enumerate(columns)]
    print("  ".join(c.upper().ljust(w) for c, w in zip(columns, widths)).rstrip())
    for r in cells:
        print("  ".join(v.ljust(w) for v, w in zip(r, widths)).rstrip())


def _emit(args: argparse.Namespace, data: Any, human: Callable[[], None]) -> None:
    if args.json:
        print(json.dumps(data, indent=2))
    else:
        human()


def _client(args: argparse.Namespace) -> NanoCommonsClient:
    try:
        return NanoCommonsClient(args.url, args.token)
    except ValueError as exc:
        raise CliError(str(exc)) from None


def _result_lines(r: Dict[str, Any]) -> None:
    if r.get("canary"):
        print(f"canary scored: expected {r['expected_verdict']}, "
              f"{r['wrong_fraction'] * 100:.0f}% of the weight was wrong")
        print(f"alarm active: {r['alarm_active']}" + ("  (raised now)" if r["alarm_raised"] else "")
              + ("  (cleared now)" if r["alarm_cleared"] else ""))
        return
    if "winning_verdict" not in r:
        print(f"rejected: {r.get('reason')}")
        return
    print(f"verdict:     {r['winning_verdict']} ({r['winning_share'] * 100:.1f}% of the weight)")
    print(f"accepted:    {r['accepted']}  ({r['reason']})")
    if r.get("checkpoint_hash"):
        print(f"checkpoint:  {r['checkpoint_hash']}")
    if r.get("fault_hashes"):
        print("faults:      " + ", ".join(sorted(r["fault_hashes"])))


# --- commands ------------------------------------------------------------------


def _serve(args: argparse.Namespace) -> int:
    from . import server
    try:
        server.serve(host=args.host, port=args.port, token=args.token, network_id=args.network_id)
    except OSError as exc:
        raise CliError(f"cannot start server on {args.host}:{args.port}: {exc}") from None
    return 0


def _status(args: argparse.Namespace) -> int:
    s = _client(args).status()

    def human() -> None:
        stats = s["canary_stats"]
        accuracy = "n/a" if stats["consensus_accuracy"] is None else f"{stats['consensus_accuracy'] * 100:.0f}%"
        print(f"network:      {s['network_id']}")
        print(f"nodes:        {s['node_count']}   missions: {s['mission_count']}")
        print(f"head:         #{s['head']['checkpoint_id']}  {s['head']['hash']}")
        print(f"alarm:        {'ACTIVE' if s['alarm_active'] else 'none'}")
        print(f"canaries:     {stats['rounds']} run, consensus accuracy {accuracy}")
        print(f"last trusted: #{s['last_trusted_checkpoint_id']}")
        print(f"suspect:      {s['suspect_checkpoint_ids'] or '-'}   tainted: {s['tainted_checkpoint_ids'] or '-'}")
    _emit(args, s, human)
    return 0


def _nodes(args: argparse.Namespace) -> int:
    nodes = _client(args).nodes()
    _emit(args, nodes, lambda: _table(
        nodes, ["node_id", "zone", "reputation", "compute_credits", "quarantined", "fault_count"]))
    return 0


def _add_node(args: argparse.Namespace) -> int:
    r = _client(args).add_node(args.node_id, args.zone, args.reputation, args.simulate_malicious)
    _emit(args, r, lambda: print(f"added node {r['node_id']} (zone {r['zone']}, reputation {r['reputation']})"))
    return 0


def _missions(args: argparse.Namespace) -> int:
    missions = _client(args).missions()
    rows = [{**m, "kind": "hosted" if m["hosted"] else "external"} for m in missions]
    _emit(args, missions, lambda: _table(rows, ["mission_id", "kind", "public_key"]))
    return 0


def _add_mission(args: argparse.Namespace) -> int:
    m = _client(args).add_mission(args.mission_id, args.public_key)

    def human() -> None:
        print(f"added {'hosted' if m['hosted'] else 'external'} mission {m['mission_id']}")
        print(f"public key: {m['public_key']}")
    _emit(args, m, human)
    return 0


def _task(args: argparse.Namespace) -> int:
    r = _client(args).task(args.mission, args.value, args.workers, args.threshold, not args.no_bind)
    _emit(args, r, lambda: _result_lines(r))
    return 0


def _canary(args: argparse.Namespace) -> int:
    r = _client(args).canary(args.mission, args.value, args.expect, args.workers, args.threshold,
                             not args.no_bind)
    _emit(args, r, lambda: _result_lines(r))
    return 0


def _checkpoints(args: argparse.Namespace) -> int:
    data = _client(args).checkpoints()

    def human() -> None:
        rows = [{**cp, "workers": len(cp["workers"]), "hash": cp["hash"][:23]} for cp in data["checkpoints"]]
        _table(rows, ["checkpoint_id", "status", "verified_verdict", "shard_id", "workers", "hash"])
        print(f"last trusted: #{data['last_trusted_checkpoint_id']}")
    _emit(args, data, human)
    return 0


def _rollback(args: argparse.Namespace) -> int:
    r = _client(args).rollback(args.checkpoint_id)
    _emit(args, r, lambda: print(f"rolled back; head is now #{r['head_checkpoint_id']}"))
    return 0


def _review(args: argparse.Namespace) -> int:
    r = _client(args).review(args.checkpoint_id)
    _emit(args, r, lambda: print(f"checkpoint #{r['checkpoint_id']} is now {r['status']}"))
    return 0


def _faults(args: argparse.Namespace) -> int:
    faults = _client(args).faults()
    _emit(args, faults, lambda: _table(
        faults, ["node_id", "kind", "submitted", "reference", "fault_number", "shard_id"]))
    return 0


def _alarms(args: argparse.Namespace) -> int:
    data = _client(args).alarms()

    def human() -> None:
        active = data["active"]
        print("active alarm: " + ("none" if active is None else
              f"raised at canary round {active['raised_at_canary_round']}, "
              f"workers {', '.join(active['workers'])}"))
        print(f"history: {len(data['history'])} alarm(s)")
        for a in data["history"]:
            state = f"cleared at round {a['cleared_at_canary_round']}" if "cleared_at_canary_round" in a else "open"
            print(f"  round {a['raised_at_canary_round']}: {a['failed_canaries']} failed canar"
                  f"{'y' if a['failed_canaries'] == 1 else 'ies'}, {state}")
    _emit(args, data, human)
    return 0


def _keygen(args: argparse.Namespace) -> int:
    key_path, pub_path = args.out + ".key", args.out + ".pub"
    existing = [p for p in (key_path, pub_path) if os.path.exists(p)]
    if existing:
        raise CliError("refusing to overwrite existing file(s): " + ", ".join(existing))
    private_key, public_key = generate_keypair()
    public_b64 = public_key_to_b64(public_key)
    try:
        # O_EXCL closes the race between the check above and the write. The 0o600 mode
        # restricts the key to its owner on POSIX; on Windows it has no effect and the
        # file inherits the folder's permissions, so choose --out inside a private folder.
        fd = os.open(key_path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
        with os.fdopen(fd, "w", encoding="ascii") as f:
            f.write(private_key_to_b64(private_key) + "\n")
    except OSError as exc:
        raise CliError(f"cannot write key files: {exc}") from None
    try:
        with open(pub_path, "x", encoding="ascii") as f:
            f.write(public_b64 + "\n")
    except OSError as exc:
        try:
            os.remove(key_path)   # do not leave a key whose public half was never written
        except OSError:
            pass
        raise CliError(f"cannot write key files: {exc}") from None

    def human() -> None:
        print(f"private key: {key_path}  (keep it secret)")
        print(f"public key:  {pub_path}")
        print(public_b64)
    _emit(args, {"public_key": public_b64, "key_file": key_path, "pub_file": pub_path}, human)
    return 0


def _submit(args: argparse.Namespace) -> int:
    try:
        with open(args.key, encoding="ascii") as f:
            private_key = private_key_from_b64(f.read())
    except (OSError, ValueError, UnicodeDecodeError) as exc:
        raise CliError(f"cannot read private key {args.key}: {exc}") from None
    client = _client(args)
    status = client.status()
    observation: Dict[str, Any] = {"value": args.value}
    if args.threshold is not None:
        observation["threshold"] = args.threshold
    try:
        packet = sign_packet(build_packet(
            network_id=status["network_id"],
            mission_id=args.mission,
            parent_checkpoint_hash=status["head"]["hash"],
            observation=observation,
            assigned_workers=None if args.no_bind else args.workers,
        ), private_key)   # signed here; the key never leaves this machine
    except ValueError as exc:
        raise CliError(f"cannot build the packet: {exc}") from None
    r = client.submit_packet(packet_to_dict(packet), observation, args.workers)
    _emit(args, r, lambda: _result_lines(r))
    return 0


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args) or 0
    except (CliError, NanoCommonsError) as exc:
        print(f"error: {exc}", file=sys.stderr)
        return 1
    except KeyboardInterrupt:
        return 130
