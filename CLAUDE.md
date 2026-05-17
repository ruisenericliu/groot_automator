# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this repo is

A harness for running **NVIDIA GR00T N1.7 inference inside Isaac Sim 5.0.0** on a remote AWS GPU workstation provisioned by [Isaac Automator](https://github.com/isaac-sim/IsaacAutomator), driven from a MacBook Air dev machine. The Mac connects to the AWS workstation over NoMachine (TCP) for a live Isaac Sim viewport; rollouts also produce MP4 artifacts. GR00T runs in a container on the workstation; Isaac Sim runs natively on the workstation (Isaac Automator pre-wires its GUI to NoMachine).

## Current state — read before doing anything

**The repo is currently docs-only.** `LICENSE`, `README.md`, `CLAUDE.md`, `ARCHITECTURE.md`, and `docs/` are all that exist. There is no `src/`, no `docker/`, no `scripts/`, no `docker-compose.aws.yml`, no `.env.example`, no `pyproject.toml`. An earlier Runpod build was scoped but never executed; it was superseded by the AWS + Isaac Automator design before bring-up, and its plans have since been deleted. Do not assume any file mentioned in the retired AWS-migration plan exists; verify with `ls` first.

The current source of truth for what we're building is **[`docs/exec-plans/active/completed-structure.md`](docs/exec-plans/active/completed-structure.md)** — read it before proposing changes. The retired AWS-migration plan under `docs/exec-plans/completed/` is historical context that explains the same delta from a Runpod-build vantage; the new plan is the live one.

## Operating principles (agent-first harness)

We are intentionally following the OpenAI Codex "harness engineering" model: humans steer, agents execute, and the repo itself is the system of record. Concretely:

1. **Keep this CLAUDE.md as a table of contents, not an encyclopedia.** Push details into `docs/`, link out from here. Target ≤ ~100 lines.
2. **Anything an agent can't see in-repo effectively doesn't exist.** If a decision was made in chat, encode it into a plan, a reference doc, or a code-level invariant.
3. **Plans are first-class artifacts.** Non-trivial work goes through `docs/exec-plans/active/<slug>.md`; completed plans move to `docs/exec-plans/completed/`. Update the plan as decisions land; don't let it drift from the code.
4. **Verify before recommending.** GR00T's wire protocol, Isaac Sim 5.0.0 APIs, and Isaac Automator's flags all change between releases — read the pinned source, don't pattern-match from memory.
5. **The MacBook is a thin client.** Builds, GPU work, and Isaac Sim all run on the AWS workstation. The Mac runs editors, `ssh`, `scp`, the NoMachine client, and the Isaac Automator deployer container.

## Repo layout (current)

```
.
├── CLAUDE.md                              (this file — ToC for agents)
├── ARCHITECTURE.md                        (system map, pin table, wire-protocol summary)
├── README.md                              (human-facing quickstart)
├── LICENSE
└── docs/
    ├── exec-plans/
    │   ├── active/
    │   │   └── completed-structure.md     ← READ THIS FIRST
    │   └── completed/
    │       └── aws-isaac-automator-migration.md  (retired; superseded by completed-structure.md)
    └── references/                         (empty placeholder)
```

Files the active plan calls for but **do not exist yet**: `ARCHITECTURE.md`, `AWS_SETUP.md`, `src/`, `configs/`, `docker/groot/`, `docker-compose.aws.yml`, `scripts/start_groot.sh`, `.env.example`, `pyproject.toml`.

## Target architecture (delta only — full picture in the active plan)

```
Mac (dev machine)  --NoMachine TCP-->  AWS workstation VM (Isaac Automator-provisioned)
   ssh / scp                                ├── Isaac Sim 5.0.0   (native, under ~/IsaacSim/)
   IA container locally                     │     └── /isaac-sim/python.sh run_inference.py
                                            ├── docker run groot-server  (GR00T on localhost:5555)
                                            └── EBS volume               (model cache, MP4 outputs)
```

- **Isaac Sim native, GR00T containerized** — Isaac stays native so NoMachine sees its GUI; GR00T stays in its NGC PyTorch image because its dep tree is tightly pinned and it needs no GUI.
- **Single GPU host.** Default `g5.2xlarge` (A10G 24 GB); `g6e.xlarge` (L40S 48 GB) for headroom. Multi-GPU is out of scope.
- **Localhost ZMQ.** Isaac talks to GR00T at `127.0.0.1:5555`. No compose bridge network in the new design.

## Pinned versions (canonical; mirror in `ARCHITECTURE.md` once it exists)

| Component | Pin |
|---|---|
| Isaac Sim | `5.0.0` (native install via Isaac Automator) |
| Isaac Automator commit | TBD — record on first successful `./deploy-aws` |
| AWS instance | `g5.2xlarge` default |
| GR00T base image | `nvcr.io/nvidia/pytorch:25.01-py3` |
| Isaac-GR00T commit | `23ace64f17aa5015259b8609d371eb61a357c776` (`n1.7-release`) |
| HF model repo | `nvidia/GR00T-N1.7-3B` |
| pyzmq / msgpack | 27.0.1 / 1.1.0 (driven by GR00T's `uv sync`) |

## Commands

There are no project-specific build, lint, or test commands yet — the code hasn't been written. Once `pyproject.toml` lands, expect:

- `ruff check .` — Mac-side lint (target py310, line length 100 per the original plan).
- `python -c "import ast; ast.parse(open('<path>').read())"` — Mac-side syntax check for files we can't run locally.

End-to-end runs happen **on the AWS workstation**, not on the Mac:

- `./deploy-aws --isaaclab no --isaaclab-arena no` (from inside the locally-built `isaac_automator` Docker image) — provision the workstation.
- `./connect <deployment-name>` / `./start` / `./stop` / `./destroy` — Isaac Automator lifecycle.
- `docker compose -f docker-compose.aws.yml up -d groot-server` — on the workstation, after `git clone`ing this repo there.
- `~/IsaacSim/python.sh src/client/run_inference.py --server-host 127.0.0.1` — the headless rollout entry point (writes MP4 to `/workspace/outputs/`).

Cost discipline is manual: `./stop` when not actively using the workstation.

## When to add to this file vs. elsewhere

- New cross-cutting invariant or convention → here (briefly), with a link to a detail doc.
- New design decision with non-obvious rationale → a plan in `docs/exec-plans/active/`, or its decision log.
- External setup walkthrough → `docs/references/<thing>.md`.
- Code-level rule that can be mechanically enforced → encode as a lint or a test, not prose.
