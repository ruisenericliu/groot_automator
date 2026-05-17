# groot_automator

Run [NVIDIA GR00T N1.7](https://github.com/NVIDIA/Isaac-GR00T) inference inside [Isaac Sim 5.0.0](https://docs.isaacsim.omniverse.nvidia.com/5.0.0/index.html) on an AWS GPU workstation provisioned by [Isaac Automator](https://github.com/isaac-sim/IsaacAutomator), driven from a MacBook Air. The workstation's Isaac Sim viewport is reachable from the Mac over [NoMachine](https://www.nomachine.com/) (TCP), so you can author scenes and watch policies live; the same scenes also produce MP4 rollouts headlessly.

> **Status — early scaffolding.** Only documentation exists today. The Mac-side workflow below describes the target. The repo's current shape and the path to "first rollout" is tracked in [`docs/exec-plans/active/completed-structure.md`](docs/exec-plans/active/completed-structure.md). New contributors (human or agent) should read [`CLAUDE.md`](CLAUDE.md) and [`ARCHITECTURE.md`](ARCHITECTURE.md) first.

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
- An [NVIDIA NGC](https://ngc.nvidia.com/) account + API key (`NGC_API_KEY`) — needed for the GR00T base image and Isaac Sim assets.
- A [Hugging Face](https://huggingface.co/) account + token (`HF_TOKEN`) with access accepted for [`nvidia/GR00T-N1.7-3B`](https://huggingface.co/nvidia/GR00T-N1.7-3B).
- An AWS account with IAM credentials and quota for a `g5.2xlarge` (or `g6e.xlarge`) in your region of choice. Isaac Automator reads `~/.aws/credentials`.
- The [NoMachine client for macOS](https://www.nomachine.com/download).
- An SSH keypair you're comfortable handing to AWS instances.

**Not needed on the Mac:** an NVIDIA GPU, CUDA, Isaac Sim, the GR00T weights, or any Python environment beyond what you already use for editing.

## Quickstart (target workflow)

The pieces marked _(not yet wired)_ are still to come — they're in the active plan.

```bash
# 1. Clone Isaac Automator and build its deployer image (one-time, on the Mac).
git clone https://github.com/isaac-sim/IsaacAutomator
cd IsaacAutomator
docker build -t isaac_automator .

# 2. Deploy a minimal Isaac-Sim-only workstation on AWS.
docker run --rm -it \
  -v ~/.aws:/root/.aws \
  -v $(pwd)/state:/root/state \
  isaac_automator ./deploy-aws --isaaclab no --isaaclab-arena no

#    Capture the deployment name, public IP, NoMachine port from state/<name>/info.txt.

# 3. Connect via NoMachine to confirm Isaac Sim opens on the host display.
#    (NoMachine client on the Mac → enter the IP + port from info.txt.)

# 4. SSH into the workstation and bring up GR00T.
docker run --rm -it -v $(pwd)/state:/root/state isaac_automator ./connect <deployment-name>
# now on the workstation:
git clone <this-repo> ~/workspace/groot_automator && cd ~/workspace/groot_automator
cp .env.example .env   # paste NGC_API_KEY, HF_TOKEN          # (not yet wired)
docker compose -f docker-compose.aws.yml up -d groot-server   # (not yet wired)

# 5. Headless rollout — produces an MP4.
~/IsaacSim/python.sh src/client/run_inference.py --server-host 127.0.0.1   # (not yet wired)
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
├── README.md                  ← this file
├── LICENSE
└── docs/
    ├── exec-plans/
    │   ├── active/            ← live plans driving current work
    │   └── completed/         ← retired plans (Runpod build plans were deleted; retired AWS migration plan lives here)
    └── references/            ← archived setup guides and external pointers
```

Things the active plan calls for that **don't exist yet**: `src/`, `configs/`, `docker/groot/`, `docker-compose.aws.yml`, `scripts/`, `.env.example`, `pyproject.toml`, `AWS_SETUP.md`. Don't be surprised when they're missing.

## Cost discipline

There is no autoscaler and no budget alarm. A `g5.2xlarge` running 24/7 is in the low hundreds of dollars per month; an L40S box is more. The only knob is `./stop <deployment-name>` when you're not actively using the workstation. EBS storage keeps billing while stopped (single-digit dollars/month for a working set), which is what lets `./start` come back without re-downloading the model or recompiling shaders.

## A note on what success looks like in Phase 1

GR00T's `LIBERO_PANDA` embodiment was trained on LIBERO/MuJoCo data, not Isaac Sim scenes. Running it against a fresh Isaac tabletop will likely produce visually-random arm motion. That's expected: the Phase 1 goal is **pipeline success** (model loads, wire protocol round-trips, MP4 is produced, arm moves under GR00T commands), not task success.

## Licensing

Code in this repo is under the [Apache 2.0](LICENSE) license. GR00T model weights are governed by the [NVIDIA Open Model License](https://huggingface.co/nvidia/GR00T-N1.7-3B) — read it before using the weights for anything beyond local evaluation.
