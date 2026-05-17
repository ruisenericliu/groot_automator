# Completed structure & overall goals — groot_automator

**Status:** active. Replaces [`../completed/aws-isaac-automator-migration.md`](../completed/aws-isaac-automator-migration.md).
**Owner:** Eric Liu.
**Opened:** 2026-05-16.
**Supersedes:** `aws-isaac-automator-migration.md` (now under `completed/`).

## Context

The repo currently exists in two layers:

- **Docs scaffolding (done, uncommitted):** `CLAUDE.md`, `ARCHITECTURE.md`, a substantive `README.md`, and `docs/exec-plans/{active,completed}/`. All three top-level docs already describe the AWS + Isaac Automator design. The Runpod build was abandoned before bring-up; its two plans are preserved under `docs/exec-plans/completed/` as historical context.
- **Code, configs, deployment glue (none of it written yet):** no `src/`, `configs/`, `docker/`, `scripts/`, `docker-compose.aws.yml`, `.env.example`, `pyproject.toml`, or `AWS_SETUP.md`.

The previous active plan (`aws-isaac-automator-migration.md`) was written when the working repo name was `runpod_isaac` / `groot_isaac`. This repo is `groot_automator`. The migration plan's phases are still substantively right, but its paths, its assumptions about pre-existing code (`src/shared/zmq_protocol.py`, `docker/groot/`, etc. — none of which actually exist), and its Phase E doc-cleanup (largely already done) need replacing.

This plan is the new north star: the end-state shape of the repo, and a compressed execution checklist to reach it.

## Goal — definition of done

The repo is "done" (Phase 1 done; not GR00T-task done) when, in one sitting on a fresh Mac:

1. `./deploy-aws --isaaclab no --isaaclab-arena no` from the Isaac Automator container stands up an AWS workstation with NoMachine reachable.
2. `git clone https://github.com/<...>/groot_automator ~/workspace/groot_automator` + `docker compose -f docker-compose.aws.yml up -d groot-server` brings GR00T up bound to `127.0.0.1:5555`.
3. `~/IsaacSim/python.sh src/client/run_inference.py --server-host 127.0.0.1` produces `/workspace/outputs/rollout_<timestamp>.mp4` with a Franka moving under GR00T commands.
4. The same script with `headless=False` (or `--live`) is watchable live over NoMachine from the Mac.
5. `./stop` / `./start` cycle works without re-downloading the model or re-compiling shaders (EBS persistence verified).
6. README quickstart walks a new user through 1–4 without surprises.

Phase 1 is **pipeline success, not task success** — GR00T's `LIBERO_PANDA` embodiment was trained on LIBERO data, so visually-random arm motion in a fresh Isaac scene is the expected outcome.

## Target end-state — repository layout

Legend: ✅ exists today (possibly uncommitted), 🟡 needs writing, 📦 archived/historical.

```
groot_automator/
├── CLAUDE.md                              ✅ agent-first ToC; ≤ ~100 lines
├── ARCHITECTURE.md                        ✅ system map, pin table, wire protocol, layering
├── README.md                              ✅ quickstart for humans
├── AWS_SETUP.md                           🟡 fills in after first successful ./deploy-aws
├── LICENSE                                ✅
├── .env.example                           🟡 NGC_API_KEY, HF_TOKEN, ACCEPT_EULA=Y, PRIVACY_CONSENT=Y
├── pyproject.toml                         🟡 ruff config (py310 target, line length 100); no runtime deps
├── docker-compose.aws.yml                 🟡 single service: groot-server, --gpus all, -p 127.0.0.1:5555:5555
├── docker/
│   └── groot/
│       ├── Dockerfile                     🟡 FROM nvcr.io/nvidia/pytorch:25.01-py3 + Isaac-GR00T @ pinned commit
│       └── entrypoint.sh                  🟡 launches gr00t.eval.run_gr00t_server
├── src/
│   ├── __init__.py                        🟡
│   ├── shared/
│   │   ├── __init__.py                    🟡
│   │   └── zmq_protocol.py                🟡 byte-for-byte mirror of gr00t/policy/server_client.py
│   └── client/
│       ├── __init__.py                    🟡
│       ├── run_inference.py               🟡 native ~/IsaacSim/python.sh entry; --server-host 127.0.0.1 default
│       └── scenes/
│           ├── __init__.py                🟡
│           └── tabletop_panda.py          🟡 Franka + tabletop, hits isaacsim.* APIs
├── configs/
│   └── tabletop_panda.yaml                🟡 read at process start by run_inference.py; never imports Python
├── scripts/
│   ├── start_groot.sh                     🟡 thin wrapper: docker compose -f docker-compose.aws.yml up -d
│   ├── pull_assets.sh                     🟡 HF cache primer for nvidia/GR00T-N1.7-3B
│   └── autorun.sh                         🟡 Isaac Automator boot hook (calls start_groot.sh)
└── docs/
    ├── exec-plans/
    │   ├── active/
    │   │   └── completed-structure.md     ✅ this plan (lives here, not in ~/.claude/plans/)
    │   └── completed/
    │       └── aws-isaac-automator-migration.md  ✅ retired in favor of this plan
    └── references/                         (empty placeholder; the Runpod plans + walkthrough were deleted as no longer useful)
```

**Net work remaining:** every 🟡 file. Counting: 5 deployment-glue files (`.env.example`, `pyproject.toml`, `docker-compose.aws.yml`, the two `docker/groot/` files), 4 source files + their `__init__.py`s, 1 config, 3 scripts, 1 doc (`AWS_SETUP.md`). ~18 files total, almost all small.

## Target end-state — runtime architecture

Canonical home: `ARCHITECTURE.md`. Summary only:

- **Single AWS workstation**, Isaac-Automator-provisioned. Default `g6e.2xlarge` (L40S, 48 GB) — matches IA upstream and is the closest EC2 sibling to the RTX 6000 Ada. `g5.2xlarge` (A10G, 24 GB) is the cheaper fallback.
- **Isaac Sim 5.0.0 native** under `~/IsaacSim/` (so NoMachine can see its GUI).
- **GR00T containerized** (NGC PyTorch 25.01-py3 + Isaac-GR00T @ pinned commit), bound to `127.0.0.1:5555`.
- **Wire protocol:** ZMQ REQ/REP over TCP, msgpack with the `__ndarray_class__` extension. `src/shared/zmq_protocol.py` must match the pinned Isaac-GR00T commit byte-for-byte.
- **EBS volume** persists HF model cache, Isaac shader cache, and MP4 outputs across `./stop` / `./start`.
- **Mac is a thin client:** editor, ssh/scp, NoMachine client, and the locally-built `isaac_automator` Docker image. No GPU, no CUDA, no Isaac Sim, no Python runtime.

All pinned versions live in the `ARCHITECTURE.md` pin table. If a pin moves, that table is the one place to update.

## Layering rules (target — not lint-enforced yet)

```
configs/  ─► src/shared/  ─► src/client/  ─► docker/  ─► docker-compose.aws.yml
                                            │
                            scripts/  ◄─────┘   (thin orchestration; no business logic)
docs/                       (knowledge base — orthogonal)
```

- `src/shared/` imports nothing else in the repo.
- `src/client/` imports `src/shared/` and `isaacsim.*` only.
- `docker/groot/` knows about Isaac-GR00T and the NGC base — never about Isaac Sim.
- `scripts/` are thin; anything growing logic moves into `src/`.
- `configs/` are read at process start; they never `import` Python.

## Execution checklist (phases compressed)

The user wants pause-for-confirmation between phases.

### Phase 0 — Land docs scaffolding & this plan

- Plan copied to `docs/exec-plans/active/completed-structure.md`; retired migration plan moved to `docs/exec-plans/completed/`. ✅
- Scrub `CLAUDE.md`, `ARCHITECTURE.md`, and `README.md` of references to the deleted Runpod artifacts (`docs/references/runpod-setup.md`, `docs/exec-plans/completed/groot-isaac-pod.md`, `docs/exec-plans/completed/pod-bringup-and-verify.md`). Rewrite the "why AWS over Runpod" decision-log pointer in `ARCHITECTURE.md` to inline the rationale instead of linking out.
- `git add CLAUDE.md ARCHITECTURE.md docs/ README.md && git commit`. The substantive docs are currently uncommitted; commit them so subsequent work has a known baseline.

### Phase A — Isaac Automator dry-run on AWS

- On Mac: `git clone https://github.com/isaac-sim/IsaacAutomator && cd IsaacAutomator && git checkout 685bc29e677714a7f0f72131e2d30eb9b9db2ce7 && ./build`. (The pinned SHA is the first commit after the NoMachine install fix; recorded in `ARCHITECTURE.md`.)
- `./run ./deploy-aws --isaaclab no --isaaclab-arena no` — IA prompts for AWS creds the first time and stores them in `state/`; no `~/.aws` mount needed. Default instance `g6e.2xlarge`, default region `us-east-1`. Override with `--ec2-instance-type` only if cost forces it.
- Connect via NoMachine from the Mac NoMachine client using the IP + port in `state/<name>/info.txt`. Confirm Isaac Sim editor opens.
- `./run ./stop <name>` then `./run ./start <name>` — confirm pause/resume.
- Write `AWS_SETUP.md` capturing install path, NoMachine port, noVNC URL, and any deltas vs the IA README we hit.

### Phase B — Write the code (Mac-side)

Done before Phase C because Phase C runs it. Mac can lint but not execute it.

- `src/shared/zmq_protocol.py` — verify against the pinned Isaac-GR00T `gr00t/policy/server_client.py`, not from memory.
- `src/client/scenes/tabletop_panda.py` — Franka on a tabletop, isaacsim 5.0.0 APIs.
- `src/client/run_inference.py` — `SimulationApp({...})` config, `--server-host 127.0.0.1` default, MP4 writer via `imageio` to `/workspace/outputs/`.
- `configs/tabletop_panda.yaml` — scene + rollout knobs.
- `docker/groot/Dockerfile` + `entrypoint.sh` — NGC PyTorch base, clone Isaac-GR00T at the pinned commit, `uv sync`, launch `gr00t.eval.run_gr00t_server`.
- `docker-compose.aws.yml` — one service, `--gpus all`, `-p 127.0.0.1:5555:5555`, volumes for HF cache + outputs.
- `scripts/start_groot.sh`, `scripts/pull_assets.sh`, `scripts/autorun.sh` — thin.
- `.env.example`, `pyproject.toml` (ruff only, py310, line length 100).
- Lint on Mac: `ruff check .`. Syntax-check Isaac-importing files via `python -c "import ast; ast.parse(open('<path>').read())"` (can't import isaacsim on Mac).

### Phase C — GR00T container + headless rollout on the workstation

- `./run ./ssh <deployment-name>` from the IA repo on the Mac; on the workstation: `git clone <this-repo> ~/workspace/groot_automator && cd ~/workspace/groot_automator`.
- `cp .env.example .env` and fill `NGC_API_KEY`, `HF_TOKEN`.
- `docker compose -f docker-compose.aws.yml up -d groot-server`. Watch `docker compose logs -f groot-server`; expect model loaded in 30–60 s on subsequent runs.
- Sanity: `python -c "from src.shared.zmq_protocol import PolicyClient; print(PolicyClient('127.0.0.1').ping())"` → `pong`.
- `~/IsaacSim/python.sh src/client/run_inference.py --server-host 127.0.0.1`. Expect MP4 at `/workspace/outputs/rollout_<timestamp>.mp4`. `scp` it to the Mac; play it.

### Phase D — Live viewport via NoMachine

- Open Isaac Sim editor over NoMachine.
- Re-run `run_inference.py` with `headless=False` (or `--live` if we add a CLI flag — decide which during Phase B). Watch the Franka move in real time.
- Confirm MP4 is still produced (same `imageio` writer path).
- Decide on one entry point vs two (recommendation: one with `--live`).

### Phase E — Wrap-up

- Refresh `README.md` quickstart against what actually worked (especially the IA container invocation if commands drifted).
- Update `CLAUDE.md` "Current state" paragraph: it currently says "docs-only" — that won't be true anymore.
- Pin the Isaac Automator commit SHA in `ARCHITECTURE.md` (carry-over from Phase A).
- Move `completed-structure.md` to `docs/exec-plans/completed/`.

## Verification

End-to-end on a fresh Mac, against a fresh AWS deployment:

1. `./deploy-aws --isaaclab no --isaaclab-arena no` completes; `state/<name>/info.txt` lists public IP, NoMachine port, noVNC URL.
2. NoMachine session from the Mac brings up the Ubuntu desktop; Isaac Sim editor opens, no driver errors.
3. `docker compose -f docker-compose.aws.yml up -d groot-server` on the workstation; `PolicyClient('127.0.0.1').ping()` → `pong`.
4. `~/IsaacSim/python.sh src/client/run_inference.py --server-host 127.0.0.1` exits 0; MP4 at `/workspace/outputs/`.
5. `scp` MP4 to Mac; plays; Franka visibly moves under GR00T action commands.
6. With `--live` (`headless=False`), the same run is visible in the NoMachine session.
7. `./stop` → `./start` resumes without re-downloading the HF model or recompiling Isaac shaders.
8. `ruff check .` is clean. No `# TODO: verify` markers left in committed code.

## Critical files / references

- Active design source: `ARCHITECTURE.md` (pin table is canonical), `CLAUDE.md` (operating principles), `README.md` (quickstart).
- Retired plan (for archaeology): `docs/exec-plans/completed/aws-isaac-automator-migration.md`.
- Upstream pin verification: pinned Isaac-GR00T commit `23ace64f17aa5015259b8609d371eb61a357c776`, especially `gr00t/policy/server_client.py`.
- Isaac Automator: https://github.com/isaac-sim/IsaacAutomator.
- NoMachine client (Mac): https://www.nomachine.com/download.

## Out of scope

- Multi-GPU, multi-node, autoscaling.
- Fine-tuning GR00T or training new embodiments.
- A custom Isaac Automator fork or AMI.
- A public web UI or hosted viewer for the MP4.
- CI in the cloud and cost dashboards. Cost discipline is manual: `./stop` when not in use.
- Closing the LIBERO → Isaac distribution shift. Pipeline success ≠ task success in Phase 1.

## Decision log

- **2026-05-16** — New plan replaces `aws-isaac-automator-migration.md` rather than sitting above it. Reason: the migration plan's paths (`runpod_isaac`, `groot_isaac`) and Phase E (docs cleanup) are stale; the new repo name is `groot_automator` and CLAUDE.md/ARCHITECTURE.md/README.md are already written. One plan is clearer than two overlapping ones.
- **2026-05-16** — Plan structured "end-state first, phases compressed." Reason: the canonical end-state lives in `ARCHITECTURE.md` and is stable; the phased work is small enough to summarize as a checklist. Detailed phase prose lives in the retired plan if needed.
- **2026-05-16** — Carry over from the retired plan, unchanged: Isaac Sim native + GR00T containerized; single GPU; localhost ZMQ; AWS over Runpod.
