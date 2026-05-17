# Architecture

Top-level map of the system. This file is the canonical home for the version-pin table, the wire-protocol summary, and the layering rules. Update it whenever a pin moves or a boundary changes.

For the current in-flight plan, see [`docs/exec-plans/active/completed-structure.md`](docs/exec-plans/active/completed-structure.md). For agent-facing operating principles, see [`CLAUDE.md`](CLAUDE.md).

## System map

```
┌──────────────────────────┐         NoMachine NX (TCP)        ┌───────────────────────────────────────────┐
│  MacBook Air (dev)       │  ───────────────────────────────► │  AWS workstation VM (Isaac Automator)     │
│                          │         ssh / scp                  │                                           │
│  - editor + git          │  ───────────────────────────────► │  ┌─────────────────────────────────────┐  │
│  - NoMachine client      │                                    │  │ Isaac Sim 5.0.0 (NATIVE)            │  │
│  - isaac_automator       │                                    │  │   ~/IsaacSim/python.sh              │  │
│    Docker image (local)  │                                    │  │   run_inference.py ──┐              │  │
│      ./deploy-aws        │                                    │  └──────────────────────┼──────────────┘  │
│      ./start  ./stop     │                                    │                         │  localhost:5555  │
│      ./connect           │                                    │                         ▼  (ZMQ REQ/REP)   │
│      ./destroy           │                                    │  ┌─────────────────────────────────────┐  │
│                          │                                    │  │ groot-server (docker)               │  │
│                          │                                    │  │   nvcr.io/nvidia/pytorch:25.01-py3  │  │
│                          │                                    │  │   gr00t.eval.run_gr00t_server       │  │
│                          │                                    │  └─────────────────────────────────────┘  │
│                          │                                    │                                           │
│                          │                                    │  EBS volume: HF cache, MP4 outputs,       │
│                          │                                    │  Isaac shader cache (persists across     │
│                          │                                    │  ./stop / ./start)                        │
└──────────────────────────┘                                    └───────────────────────────────────────────┘
```

Key invariants:

- **Isaac Sim runs natively** on the workstation so Isaac Automator's pre-wired NoMachine session can drive its GUI. Containerizing Isaac would defeat the point of migrating off Runpod.
- **GR00T runs in a container** on the same host, bound to `127.0.0.1:5555`. No cross-host networking, no Docker bridge network — Isaac talks to it over localhost loopback.
- **Single GPU.** All work assumes one CUDA device. Multi-GPU is explicitly out of scope.
- **The Mac is a thin client.** It never builds or runs the GPU stack. Its only Docker workload is the locally-built `isaac_automator` image that drives the AWS deployment.

## Pinned versions (canonical)

This table is the source of truth. Anywhere else (plans, READMEs, comments) that names a version must agree with it — update both, or update the link.

| Component | Pin | Source / notes |
|---|---|---|
| Isaac Sim | `5.0.0` | Installed natively by Isaac Automator under `~/IsaacSim/`. |
| Isaac Automator commit | TBD — record on first successful `./deploy-aws` | Pin once a deploy lands; capture in this row and in the active plan. |
| AWS instance (default) | `g5.2xlarge` (A10G, 24 GB) | `g6e.xlarge` (L40S, 48 GB) is the headroom option. |
| AWS region | User's choice | No region-locked assumptions in code. |
| GR00T base image | `nvcr.io/nvidia/pytorch:25.01-py3` | Provides CUDA 12.8 / Python 3.10. Confirm tag at build time. |
| Isaac-GR00T | `23ace64f17aa5015259b8609d371eb61a357c776` (tag `n1.7-release`) | https://github.com/NVIDIA/Isaac-GR00T |
| Hugging Face model | `nvidia/GR00T-N1.7-3B` | Pulled into the EBS cache by `pull_assets.sh` (TBD). |
| Embodiment tag | `LIBERO_PANDA` | GR00T was trained on LIBERO data; behavior on a fresh Isaac scene will be distribution-shifted. Pipeline success ≠ task success. |
| pyzmq / msgpack | 27.0.1 / 1.1.0 | Driven by GR00T's own `uv sync`. Match in the Isaac-side client so framing is byte-identical. |
| Python (GR00T container) | 3.10 | From the NGC PyTorch base. |
| Python (Mac lint env) | 3.10 target | `ruff` config, line length 100. |

## Wire protocol

GR00T's `gr00t/policy/server_client.py` is the canonical implementation. Our client (`src/shared/zmq_protocol.py`, TBD) must mirror it byte-for-byte:

- **Transport:** ZMQ REQ/REP over TCP. Server binds; client connects.
- **Framing:** msgpack with a custom `np.ndarray` extension type (`__ndarray_class__` / `as_npy`). Not pickle. Not raw numpy.
- **Dispatch:** Each request is a dict with an `endpoint` key (e.g. `get_action`, `ping`, `get_modality_config`); payload sits alongside it.
- **`get_action` returns** `(action_dict, info_dict)` — both unpacked through the same ext type.
- **Special types:** `__ModalityConfig_class__` round-trips as a plain dict on our side; we do not need to reconstruct the GR00T class.
- **Default port:** `5555` (`DEFAULT_MODEL_SERVER_PORT`).

If you change anything here, verify against the pinned Isaac-GR00T commit, not against memory or against `main`.

## Repository layering (target — most does not exist yet)

The repo will divide into a small number of layers with one-way dependencies. None of this is enforced by lints today; it's the model we're building toward.

```
configs/   ──► src/shared/    ──► src/client/   ──► docker/   ──► docker-compose.aws.yml
(YAML)         (wire protocol)   (Isaac driver)    (GR00T)       (workstation orchestration)
                                                  │
                                  scripts/  ◄─────┘  (thin entry points; no business logic)
docs/      (knowledge base — orthogonal to the code layers)
```

Rules of thumb:

- **`src/shared/` depends on nothing in the repo.** It's the GR00T wire protocol and constants — the one place that must match the pinned Isaac-GR00T commit exactly.
- **`src/client/` depends on `src/shared/` and on `isaacsim.*`.** It does not import anything GR00T-specific other than the wire types.
- **`docker/groot/` knows about Isaac-GR00T and the NGC base image, nothing about Isaac Sim.** Symmetrically, the Isaac side does not pull in GR00T's Python deps.
- **`scripts/` are thin** — orchestration only. Anything that grows business logic moves into `src/`.
- **`configs/` are read at process start** by `src/client/run_inference.py`. They never `import` Python.

## Decision-log pointers

Architectural decisions live with the plan that made them. When a decision is broad enough to affect future work, link it from here:

- **Why AWS over Runpod** — Runpod can't expose UDP on externally-reachable ports, which blocks Isaac Sim's WebRTC livestream and rules out a TURN workaround (Runpod also can't expose the relay's UDP side). Isaac Automator's NoMachine session is TCP-only and sidesteps the constraint entirely. The original Runpod plans have been deleted; the retired AWS-migration plan under `docs/exec-plans/completed/` carries the most detail.
- **Why Isaac Sim native, GR00T containerized** — Isaac Automator's NoMachine session targets the host display, so containerizing Isaac would defeat the GUI access that motivated the move. GR00T has no GUI needs and its dep tree benefits from container pinning. See [`docs/exec-plans/active/completed-structure.md`](docs/exec-plans/active/completed-structure.md).

## Out of scope (until a plan says otherwise)

- Multi-GPU, multi-node, autoscaling.
- Fine-tuning GR00T or training new embodiments.
- A custom Isaac Automator fork or AMI — we use upstream as-is.
- A public web UI or hosted viewer for the MP4.
- CI in the cloud and cost dashboards. Cost discipline is manual via `./stop`.
