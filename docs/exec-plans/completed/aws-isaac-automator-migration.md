# AWS + Isaac Automator Migration

**Status:** active, not yet started.
**Owner:** Eric Liu.
**Opened:** 2026-05-16.
**Supersedes:** [`completed/pod-bringup-and-verify.md`](../completed/pod-bringup-and-verify.md)
(moved before execution; the Runpod build it covered is being abandoned in
favor of this migration).

## Context

The completed Phase 1 build targets Runpod. While shaking down that plan we
confirmed Runpod cannot give us a live Isaac Sim viewport at all: the WebRTC
livestream requires UDP 47998 + TCP 49100, and **Runpod Pods do not support
UDP on externally-reachable ports** (HTTP-proxy and TCP only). A TURN-relay
workaround doesn't help either, because Runpod can't expose the UDP side of
the relay. See the WebRTC decision-log entry in
[`completed/groot-isaac-pod.md`](../completed/groot-isaac-pod.md#decision-log).

The MP4-only dev loop that constraint forces is acceptable for a pure
pipeline sanity check, but it's hostile to actual scene authoring and policy
debugging — every camera move costs a 3–5 minute cold-load plus a full
episode-length rollout.

NVIDIA ships **[Isaac Automator](https://github.com/isaac-sim/IsaacAutomator)**,
a Terraform + Ansible harness that stands up an Isaac Sim "workstation" on
AWS/GCP/Azure with **NoMachine and noVNC pre-wired**. Both are TCP-only,
which sidesteps the Runpod UDP problem entirely. User has chosen full
migration to AWS as the first target.

Inference code (`src/`), configs (`configs/`), the GR00T wire protocol, and
the version pins are all reusable as-is. The deployment harness changes; the
inference path doesn't.

## Goal

A single end-to-end run on an Isaac-Automator-deployed AWS workstation that:

1. Produces the same `rollout_<timestamp>.mp4` that Phase 1 was supposed to
   produce, headlessly, via the existing `run_inference.py` path; **and**
2. Can be opened interactively in the Isaac Sim editor via NoMachine, so the
   user can author scenes and watch policies live.

## Architecture (delta from current)

**Current (Runpod, deferred):**

```
Mac  --ssh-->  Runpod Pod
                ├── docker compose
                │     ├── groot-server  (NGC PyTorch + Isaac-GR00T)
                │     └── isaac-sim     (NGC Isaac Sim 5.0.0, headless)
                └── /workspace/runpod-volume/  (persistent)
```

**Target (AWS + Isaac Automator):**

```
Mac --NoMachine TCP--> AWS workstation VM
       ssh / scp          ├── Isaac Sim 5.0.0  (NATIVE under ~/IsaacSim/)
                          │     └── /isaac-sim/python.sh run_inference.py
                          ├── docker run groot-server  (containerized; localhost:5555)
                          ├── ~/uploads/autorun.sh     (boot/start hook)
                          └── EBS volume               (model cache, MP4 outputs)
```

Why native Isaac Sim instead of our container:

- Isaac Automator's whole value is the pre-wired NoMachine session pointed
  at the host display. Putting Isaac inside a container would lose that.
- The `docker/isaac/` Dockerfile and entrypoint are retired in this plan.
- GR00T stays containerized — it's an NGC-PyTorch image with one tightly
  pinned dependency tree, and it has no GUI needs, so a container is the
  right unit.
- Ports: Isaac talks to GR00T over `localhost:5555` (the GR00T container
  publishes `-p 5555:5555`). No more compose bridge network.

What stays:

- `src/shared/zmq_protocol.py` — unchanged.
- `src/client/scenes/tabletop_panda.py` — unchanged (still hits the same
  isaacsim Python APIs).
- `src/client/run_inference.py` — runs natively under `~/IsaacSim/python.sh`
  instead of inside a container. Argparse default for `--server-host` flips
  from `groot-server` to `127.0.0.1`. That's it.
- `configs/*.yaml` — unchanged.
- `docker/groot/` (Dockerfile + entrypoint) — unchanged.
- Version pins in `ARCHITECTURE.md` — unchanged.
- `CLAUDE.md` operating principles 1–5 and 7 — unchanged. §6 (live viewport)
  needs rewriting because the constraint that justified it is gone.

What goes:

- `docker/isaac/` (Dockerfile + entrypoint) — delete; Isaac runs natively.
- `docker-compose.yml` — replace with a smaller `docker-compose.yml` that
  defines only the `groot-server` service, plus an `autorun.sh` for Isaac
  Automator that calls `docker compose up -d`.
- `scripts/runpod_bootstrap.sh`, `scripts/start.sh`, `scripts/stop.sh` —
  retired in favor of Isaac Automator's `./deploy-aws`, `./start`, `./stop`,
  `./destroy` from inside the IA container. We keep a thin
  `scripts/start_groot.sh` for the GR00T container only.
- `RUNPOD_SETUP.md` — moved under `docs/references/` as historical, replaced
  by `AWS_SETUP.md` at the repo root.
- `.env.example`'s `NGC_API_KEY` stays (still need it for the GR00T base
  image pull). `HF_TOKEN`, `ACCEPT_EULA=Y`, `PRIVACY_CONSENT=Y` stay. Add
  AWS-specific keys (AWS access-key / region) only if Isaac Automator
  doesn't handle them via its own `~/.aws/credentials` mount.

## Pinned versions (delta)

| Component | Pin | Change vs Phase 1 |
|---|---|---|
| Isaac Automator commit | TBD — verify at first deploy | NEW |
| AWS instance type | `g5.2xlarge` (A10G 24 GB) default; allow `g6e.xlarge` (L40S 48 GB) for headroom | NEW |
| AWS region | TBD by user | NEW |
| Isaac Sim 5.0.0 | unchanged, but now installed natively under `~/IsaacSim/` | install method |
| GR00T container base | `nvcr.io/nvidia/pytorch:25.01-py3` | unchanged |
| Isaac-GR00T commit | `23ace64f17aa5015259b8609d371eb61a357c776` | unchanged |
| HF model repo | `nvidia/GR00T-N1.7-3B` | unchanged |
| pyzmq, msgpack | 27.0.1, 1.1.0 | unchanged |

## Phased deliverables

The user wants pause-for-confirmation between phases.

### Phase A — Isaac Automator dry-run on AWS
- Verify Docker on Mac can build/run the IA container (`docker build -t
  isaac_automator .` per the IA repo's instructions).
- Mount AWS credentials into the IA container (`~/.aws/credentials` or env
  vars). User must already have an AWS account with appropriate IAM.
- `./deploy-aws --isaaclab no --isaaclab-arena no` to stand up a minimal
  Isaac-Sim-only workstation. Default `g5.2xlarge`, region of user's choice.
- Connect via NoMachine (Mac client: `https://www.nomachine.com/download`).
  Confirm Isaac Sim launches and we can see its editor.
- `./stop <deployment-name>` to confirm pause/resume works.
- Capture the install path, the `ubuntu` user's setup, NoMachine port,
  noVNC URL. Record in `AWS_SETUP.md`.

### Phase B — GR00T container on the workstation
- SSH into the running deployment (`./connect <deployment-name>` from IA).
- `git clone` this repo into `~/workspace/runpod_isaac` (rename to
  `~/workspace/groot_isaac` is fine — repo name is overdue for a refactor).
- `cp .env.example .env`, fill NGC and HF tokens.
- `docker compose -f docker-compose.aws.yml up -d groot-server`. Verify it
  binds to `127.0.0.1:5555` and the model loads (watch
  `docker compose logs -f groot-server`).
- Sanity test with `python -c "from src.shared.zmq_protocol import
  PolicyClient; print(PolicyClient('127.0.0.1').ping())"`.

### Phase C — Headless run_inference end-to-end
- From the workstation shell:
  `~/IsaacSim/python.sh /workspace/groot_isaac/src/client/run_inference.py
   --server-host 127.0.0.1`.
- Expect an MP4 at `/workspace/outputs/rollout_<timestamp>.mp4`.
- This is the equivalent of the deferred Runpod Phase-1 success criterion.
- Fix the same crop of in-code `# TODO: verify` markers that the retired
  Runpod plan called out: renderer name, `SimulationApp` import path,
  `Camera()` constructor, `franka.end_effector`, `dof_names`, the EE→joint
  delta hack in `apply_action`. Same TODOs, same files, different host.

### Phase D — Live viewport via NoMachine
- Open Isaac Sim editor via NoMachine.
- From the editor's Script Editor, run the same `run_inference.py` with
  `headless=False` in the `SimulationApp({...})` config. Watch the Franka
  move in real time.
- Confirm the rendered MP4 is also produced. (Both paths share the same
  `imageio` writer.)
- Decide whether to keep two entry points (headless + live) or one with a
  CLI flag — the latter is probably right.

### Phase E — Docs + repo cleanup
- Replace `RUNPOD_SETUP.md` (move to `docs/references/runpod-setup.md` with
  a header explaining it's archived) with `AWS_SETUP.md`.
- Rewrite README quickstart for the new flow: install Docker on Mac, build
  IA container, `./deploy-aws`, `./connect`, run the inference command.
- Update `CLAUDE.md` §6: the WebRTC viewport is back in scope; the new
  host (Isaac Automator + AWS) lets us reach the workstation over NoMachine.
  Note that we don't actually rely on WebRTC — NoMachine NX is the transport.
- Update `ARCHITECTURE.md` system diagram + "Out of scope" section.
- Delete `docker/isaac/` (or move under `docs/references/` for archaeology).
- Retire `scripts/runpod_bootstrap.sh` / `start.sh` / `stop.sh`; keep
  `scripts/pull_assets.sh` (still useful for HF cache priming).
- Move this active plan to `completed/` once Phase D verifies.

## Critical files / references

- Isaac Automator: https://github.com/isaac-sim/IsaacAutomator
- Isaac Automator README (deploy commands, autorun.sh hook):
  https://raw.githubusercontent.com/isaac-sim/IsaacAutomator/main/README.md
- NoMachine client (Mac): https://www.nomachine.com/download
- AWS GPU instance pricing reference (verify at deploy time):
  https://aws.amazon.com/ec2/instance-types/g5/
- Existing `src/shared/zmq_protocol.py`, `src/client/run_inference.py`,
  `src/client/scenes/tabletop_panda.py` — to confirm none of them silently
  depend on a containerized environment.

## Verification

1. `./deploy-aws --isaaclab no --isaaclab-arena no` from the IA container
   completes; `state/<deployment-name>/info.txt` lists a public IP,
   NoMachine port, noVNC URL.
2. NoMachine connection from the Mac brings up the Ubuntu desktop and the
   Isaac Sim editor opens without driver errors.
3. `docker compose up -d groot-server` on the workstation; the GR00T model
   loads in 30–60 s and `PolicyClient('127.0.0.1').ping()` returns `pong`.
4. `~/IsaacSim/python.sh src/client/run_inference.py --server-host
   127.0.0.1` exits 0; MP4 appears at `/workspace/outputs/`.
5. `scp` MP4 to Mac; plays. Franka moves under GR00T action commands.
6. With `headless=False`, the same run is visible live in the NoMachine
   session.
7. `./stop` releases the GPU; `./start` resumes without re-downloading
   models (EBS persistence works).

## Out of scope

- Multi-GPU deployments.
- Fine-tuning GR00T or training new embodiments.
- Building our own Isaac Automator fork or AMI — we use upstream as-is.
- Migrating CI or adding cloud-cost dashboards. Cost discipline is manual:
  `./stop` when done.

## Decision log

- **2026-05-16** — User chose full migration to AWS over Runpod-status-quo,
  hybrid, or third-host options. Cost increase (~2×/hr) accepted in exchange
  for live viewport.
- **2026-05-16** — Run Isaac Sim natively on the IA-provisioned workstation
  rather than in our `docker/isaac/` container; containerizing Isaac would
  defeat the NoMachine GUI access that motivated the migration.
- **2026-05-16** — Keep GR00T containerized; the NGC PyTorch image carries
  Isaac-GR00T's tightly-pinned dependency tree and has no GUI needs.
