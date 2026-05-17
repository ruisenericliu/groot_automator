# groot_automator

Run [NVIDIA GR00T N1.7](https://github.com/NVIDIA/Isaac-GR00T) inference inside [Isaac Sim 5.0.0](https://docs.isaacsim.omniverse.nvidia.com/5.0.0/index.html) on an AWS GPU workstation provisioned by [Isaac Automator](https://github.com/isaac-sim/IsaacAutomator), driven from a MacBook Air. The workstation's Isaac Sim viewport is reachable from the Mac over [NoMachine](https://www.nomachine.com/) (TCP), so you can author scenes and watch policies live; the same scenes also produce MP4 rollouts headlessly.

> **Status — wire protocol + scaffolding landed; container + Isaac driver still to come.** The ZMQ client, env baseline, scripts, and tests ship; the GR00T container (`docker-compose.aws.yml` + `docker/groot/`) and the Isaac client (`src/client/run_inference.py` + scene) are the next two chunks. The Mac-side workflow below describes the full target. Path to "first rollout" lives in [`docs/exec-plans/active/completed-structure.md`](docs/exec-plans/active/completed-structure.md). New contributors (human or agent) should read [`CLAUDE.md`](CLAUDE.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md) first.

## Why this exists

GR00T's reference deployment assumes you have an Isaac Sim host and a GPU sitting on your desk. We don't — we have a laptop. This repo is the small amount of glue that makes "laptop → cloud GR00T + Isaac Sim → live viewport on the laptop" a few commands instead of a project.

Upstream Isaac Automator handles the AWS lifecycle (Terraform + Ansible, NoMachine pre-wired). This repo adds:

- The GR00T container definition and a compose file the workstation can `docker compose up`.
- The Isaac Sim Python driver (`src/client/run_inference.py`) and a tabletop Franka scene.
- The ZMQ wire client that mirrors GR00T's `server_client.py` byte-for-byte.
- The configs and entry points that tie the above together.

## Prerequisites

**On the Mac:**

- Docker Desktop (for building/running the Isaac Automator deployer container locally).
- An [NVIDIA NGC](https://ngc.nvidia.com/) account + API key (`NGC_API_KEY`) — used by `docker login nvcr.io` on the workstation to pull the GR00T base image. Isaac Automator handles its own NGC prompt for the Isaac Sim install.
- A [Hugging Face](https://huggingface.co/) account + token (`HF_TOKEN`) with access accepted for [`nvidia/GR00T-N1.7-3B`](https://huggingface.co/nvidia/GR00T-N1.7-3B).
- An AWS account whose IAM principal has `AmazonEC2FullAccess` (plus quota for a `g6e.2xlarge` (L40S, 48 GB — upstream IA default) in your region of choice; `g5.2xlarge` (A10G) is the cheaper fallback). Isaac Automator prompts for AWS credentials interactively the first time you run `./deploy-aws` and stores them inside its `state/` directory — it does **not** read `~/.aws/credentials` from the host.
- The [NoMachine client for macOS](https://www.nomachine.com/download).
- An SSH keypair you're comfortable handing to AWS instances.

**Not needed on the Mac:** an NVIDIA GPU, CUDA, Isaac Sim, the GR00T weights, or any Python environment beyond what you already use for editing.

## Quickstart (target workflow)

The pieces marked _(not yet wired)_ are still to come — they're in the active plan.

```bash
# 1. Clone Isaac Automator at the pinned commit and build its deployer image (one-time, on the Mac).
git clone https://github.com/isaac-sim/IsaacAutomator
cd IsaacAutomator
git checkout 685bc29e677714a7f0f72131e2d30eb9b9db2ce7   # see ARCHITECTURE.md pin table
./build                                                 # equivalent to `docker build -t isaac_automator .`

# 2. Deploy a minimal Isaac-Sim-only workstation on AWS (g6e.2xlarge / L40S in us-west-2 — see AWS_SETUP.md for the quota dance).
./run ./deploy-aws --isaaclab no --isaaclab-arena no --region us-west-2

#    Capture the deployment name, public IP, NoMachine port from state/<name>/info.txt.

# 3. Connect via NoMachine to confirm Isaac Sim opens on the host display.
#    (NoMachine client on the Mac → enter the IP + port from info.txt.)

# 4. SSH into the workstation and bring up GR00T.
./run ./ssh <deployment-name>
# now on the workstation:
git clone <this-repo> ~/workspace/groot_automator && cd ~/workspace/groot_automator
cp .env.example .env   # paste NGC_API_KEY, HF_TOKEN
docker compose -f docker-compose.aws.yml up -d groot-server   # (B.3 — compose file not yet committed)

# 5. Headless rollout — produces an MP4.
~/IsaacSim/python.sh src/client/run_inference.py --server-host 127.0.0.1   # (B.4 — entry script not yet committed)
# expect /workspace/outputs/rollout_<timestamp>.mp4

# 6. Live rollout — same script with headless=False, watched over NoMachine.
#    (CLI flag TBD; see Phase D of the active plan.)
```

When you're done for the day, pause the GPU to stop the meter:

```bash
docker run --rm -it -v $(pwd)/state:/root/state isaac_automator ./stop <deployment-name>
# ./start to resume — EBS persists model cache + shader cache, so no re-download.
# ./destroy to tear it down completely.
```

## Repository layout

```
.
├── CLAUDE.md                  ← agent-first operating principles + ToC (read first)
├── ARCHITECTURE.md            ← system map, pin table, wire-protocol summary
├── AWS_SETUP.md               ← pre-deploy walkthrough (post-deploy section TBD)
├── README.md                  ← this file
├── LICENSE
├── .env.example               ← NGC_API_KEY, HF_TOKEN, ACCEPT_EULA, PRIVACY_CONSENT
├── pyproject.toml             ← ruff config (py310, line length 100)
├── src/
│   ├── shared/zmq_protocol.py ← ZMQ client mirror of GR00T's server_client.py
│   └── client/                ← Isaac Sim driver (scene + run_inference — coming in B.4)
├── tests/                     ← in-process round-trip tests for the wire protocol
├── scripts/                   ← thin orchestration: start_groot, pull_assets, autorun
└── docs/
    ├── exec-plans/
    │   ├── active/            ← live plans driving current work
    │   └── completed/         ← retired plans (Runpod build plans were deleted; retired AWS migration plan lives here)
    └── references/
        └── upstream-server-client.py   ← frozen snapshot of the pinned GR00T wire protocol
```

Things the active plan calls for that **don't exist yet**: `docker-compose.aws.yml`, `docker/groot/Dockerfile`, `docker/groot/entrypoint.sh`, `src/client/run_inference.py`, `src/client/scenes/tabletop_panda.py`, `configs/tabletop_panda.yaml`. `AWS_SETUP.md` exists but the post-deploy details section is still `TBD` until the first successful deploy lands.

## Cost discipline

There is no autoscaler and no budget alarm. A `g6e.2xlarge` (L40S, the default) running 24/7 is on the order of a few hundred dollars per month on-demand; the cheaper `g5.2xlarge` (A10G) fallback is roughly half that. The only knob is `./stop <deployment-name>` when you're not actively using the workstation. EBS storage keeps billing while stopped (single-digit dollars/month for a working set), which is what lets `./start` come back without re-downloading the model or recompiling shaders.

## A note on what success looks like in Phase 1

GR00T's `LIBERO_PANDA` embodiment was trained on LIBERO/MuJoCo data, not Isaac Sim scenes. Running it against a fresh Isaac tabletop will likely produce visually-random arm motion. That's expected: the Phase 1 goal is **pipeline success** (model loads, wire protocol round-trips, MP4 is produced, arm moves under GR00T commands), not task success.

## Licensing

Code in this repo is under the [Apache 2.0](LICENSE) license. GR00T model weights are governed by the [NVIDIA Open Model License](https://huggingface.co/nvidia/GR00T-N1.7-3B) — read it before using the weights for anything beyond local evaluation.
