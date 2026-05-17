# AWS Setup

How to go from no AWS account to a deployed Isaac Sim + GR00T workstation. This is the prerequisite walkthrough for Phase A of [`docs/exec-plans/active/completed-structure.md`](docs/exec-plans/active/completed-structure.md). For the larger system, see [`ARCHITECTURE.md`](ARCHITECTURE.md).

## 1. Create an AWS account

- Sign up at https://aws.amazon.com/ → "Create an AWS Account."
- Use an email you control and a strong password; this is the **root account**, treat it like a master key — you will rarely log in as root after setup.
- AWS will ask for a credit card. There is no free tier for GPU instances; expect real charges from the moment the deployment runs (see "Cost discipline" below).
- Pick a support plan: **Basic (free)** is fine.
- Verify your phone number; activation takes a few minutes.
- Sign in to the [AWS Console](https://console.aws.amazon.com/).

## 2. Create an IAM user for Isaac Automator

Do not use root credentials with IA. Create a dedicated IAM user instead.

1. In the console, go to **IAM → Users → Create user**.
2. Name: `isaac-automator` (or anything memorable).
3. Tick **Provide user access to the AWS Management Console** only if you also want to sign in as this user; not required for IA.
4. **Set permissions → Attach policies directly →** check `AmazonEC2FullAccess`. (Upstream IA's documented prerequisite.)
5. Finish creating the user.
6. After creation, open the user → **Security credentials → Create access key →** choose "Command Line Interface (CLI)."
7. Copy the **Access key ID** and **Secret access key** somewhere safe (a password manager). The secret is shown once.

## 3. Request quota for GPU instances in us-west-2

Fresh AWS accounts have a `0` quota for GPU EC2 instances by default. Without a quota increase, `terraform apply` will fail with `VcpuLimitExceeded`. File this before the deploy — approval can take hours to days.

1. In the console, switch the region picker (top-right) to **US West (Oregon) / us-west-2**.
2. Go to **Service Quotas → AWS services → Amazon Elastic Compute Cloud (Amazon EC2)**.
3. Search for "**Running On-Demand G and VT instances**" (the quota code is `L-DB2E81BA`).
4. **Request quota increase.** Ask for at least **8 vCPUs** — that's exactly one `g6e.2xlarge` running. Asking for 16 leaves headroom for two or for short overlaps during `./stop` / `./start`.
5. Wait for approval email. Quick way to check status from the CLI later: `aws service-quotas list-requested-service-quota-change-history --service-code ec2 --region us-west-2 | grep -B2 G-and-VT`.

## 4. Install the AWS CLI (optional, useful for quota checks)

Not required by IA itself (IA prompts for keys interactively and stores them in `state/`), but handy.

```bash
brew install awscli
aws configure          # paste the access key + secret from step 2; default region us-west-2; output json
aws sts get-caller-identity   # sanity check — should print the IAM user ARN
```

## 5. Install the NoMachine client on the Mac

- Download from https://www.nomachine.com/download → "NoMachine for macOS (Apple Silicon)."
- Drag to `/Applications`, launch once, accept first-run prompts.
- No login or account is needed; the client connects directly to the workstation by IP and port.

## 6. Deploy the workstation

Prerequisites done above: AWS account, IAM user + access key, quota in us-west-2, NoMachine client. Docker Desktop is already installed and `~/Repositories/IsaacAutomator` is already cloned at the pinned commit `685bc29e677714a7f0f72131e2d30eb9b9db2ce7` with the image built.

```bash
cd ~/Repositories/IsaacAutomator
./run ./deploy-aws --isaaclab no --isaaclab-arena no --region us-west-2
```

What this does, in order:

1. Launches the `isaac_automator` container with `~/Repositories/IsaacAutomator` mounted at `/app`. AWS credentials are NOT read from `~/.aws/credentials` — IA stores them inside `state/`.
2. Interactive wizard prompts for:
   - **AWS Access Key ID** (from step 2).
   - **AWS Secret Access Key** (from step 2).
   - **AWS session token** — leave blank unless you use STS.
   - **Deployment name** — anything memorable, e.g. `groot-dev`. Used in every later command.
   - **Instance type** — accept the default `g6e.2xlarge` (L40S, 48 GB).
   - **Several yes/no flags** — accept defaults unless you have a reason not to.
3. Runs **Terraform `plan` + `apply`**: provisions VPC, EC2 instance, EBS volume, security group. ~5 min.
4. Runs **Ansible playbooks**: NVIDIA driver, Isaac Sim 5.0.0, NoMachine server. **15–45 min.**
5. Prints a summary with public IP, NoMachine port, noVNC URL. Also written to `state/<deployment-name>/info.txt`.

## 7. Connect to the workstation

After deploy, all subsequent commands run from the same `~/Repositories/IsaacAutomator` directory:

```bash
./run ./ssh <deployment-name>        # shell on the workstation
./run ./novnc <deployment-name>      # opens the noVNC web viewer (browser)
```

**NoMachine (preferred for live Isaac Sim viewport):**

1. Open the NoMachine client on the Mac.
2. New connection → protocol **NX**, host = public IP from `info.txt`, port = NoMachine port from `info.txt` (typically `4000`).
3. Username/password are in `info.txt` too.
4. Once connected, you should see the Ubuntu desktop on the workstation, with Isaac Sim launchable from the application menu.

## 8. Lifecycle commands

```bash
./run ./stop <deployment-name>        # halts the EC2 instance; EBS keeps state. GPU billing stops; storage continues at ~$0.10/GB-month.
./run ./start <deployment-name>       # boots the instance back up; re-runs Ansible (use --quick to skip the Ansible step).
./run ./destroy <deployment-name>     # tears down EVERYTHING — instance, EBS, VPC. Irreversible.
```

**Rule of thumb:** `./stop` between sessions, `./destroy` only when you're truly done.

## 9. Cost discipline

| State | What's billing | Approximate rate |
|---|---|---|
| Running `g6e.2xlarge` | EC2 instance + EBS | ~$2.24/hr on-demand + storage |
| Stopped (`./stop`) | EBS volume only | ~$0.10/GB-month (single-digit $/month at typical sizes) |
| Destroyed (`./destroy`) | Nothing | $0 |

There is **no autoscaler and no budget alarm** built in. The only knob is `./stop` after each session. Consider setting a Billing Alarm in CloudWatch (or AWS Budgets) for safety — Console → Billing → Budgets → Create budget.

## 10. After the first successful deploy — fill in below

This section is the persistent record of the values our code expects. Update as the deploy lands.

- **Deployment name:** _TBD_
- **Region:** `us-west-2`
- **Instance type:** `g6e.2xlarge`
- **AWS AMI ID (Ubuntu version):** _TBD_
- **Isaac Sim install path on the workstation:** _TBD (expected `~/IsaacSim/`)_
- **NoMachine port:** _TBD (expected `4000`)_
- **noVNC URL pattern:** _TBD_
- **Default Ubuntu user:** _TBD (expected `ubuntu`)_
- **EBS volume size:** _TBD_
- **First-deploy wall time:** _TBD_

## 11. Troubleshooting

- **`VcpuLimitExceeded` during `terraform apply`** → quota request from step 3 was not approved or was filed in the wrong region. Re-check Service Quotas in us-west-2.
- **`InsufficientInstanceCapacity`** → AWS is temporarily out of g6e.2xlarge in your chosen AZ. Retry, or switch region (re-run quota request there).
- **NoMachine can't connect** → confirm the security group allows TCP from your IP on the NoMachine port. IA configures `--ingress-cidrs` at deploy time; default may be your detected public IP only.
- **`./ssh` hangs** → first-boot Ansible may still be running. Wait for `info.txt` to update or watch progress in the deploy log.
- **Ansible playbook failures** → `./run ./repair <deployment-name>` retries the playbook against the existing instance.
