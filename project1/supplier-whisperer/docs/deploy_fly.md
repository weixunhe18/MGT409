# Deploying the always-on mailbox to Fly.io (for Wei, later)

Nothing here has been run against Fly yet: there's no account, and the hike session didn't talk to Fly. The files
are ready (`Dockerfile`, `.dockerignore`, `fly.toml`, `scripts/docker-entrypoint.sh`). Why polling on an always-on
host: see `decisions.md` D7.

## What gets deployed

| | |
|---|---|
| Machine | 1 × `shared-cpu-1x`, 256 MB, region `ewr` (New Jersey) |
| Command | `python app.py --live --mailbox --no-browser --fly-private` |
| Data | Fly volume `whisperer_data` mounted at `/data`; database `/data/sample-mailbox.db` |
| Internet exposure | **None.** `fly.toml` has no `[http_service]` or `[[services]]`, so Fly allocates no public port. The app listens only on the machine's private Fly address (`fdaa::/16`), and only accepts requests whose `Host` is `localhost`/`127.0.0.1`. |
| How you see the dashboard | `fly proxy 8000` on your laptop (a WireGuard tunnel only your Fly account can open), then http://127.0.0.1:8000 |
| Image | `python:3.12-slim` + `certifi`; runs as non-root user `whisperer`. `.env`, `.venv`, `.git`, `data/raw_private/` and `data/runtime/` are excluded by `.dockerignore`. |

`--fly-private` is a new, explicit flag: it resolves `fly-local-6pn` (an `/etc/hosts` entry Fly writes in every
machine) and refuses to start unless that is a private `fdaa::/16` address. On your laptop it just exits with an
error, so it can never bind a public interface by accident. The old rule is unchanged: any other non-loopback host is
refused unless `WEBHOOK_SECRET` and `ALLOW_REMOTE=1` are both set. Tests: `tests/test_server.py`.

## ⚠️ Before you start

* **Run only ONE mailbox poller.** If the laptop (`python app.py --mailbox`) and Fly both run, both answer the same
  email (they keep separate databases). Stop the laptop one before deploying, and vice versa.
* **Start in dry-run on Fly** (`MAILBOX_SEND=dry-run`), check a few drafts through `fly proxy`, then switch to `on`.
* The course rule on extra keys still applies: ask the professor before telling TAs they can email it.

## Commands (run in `project1/supplier-whisperer`)

```bash
brew install flyctl
```

```bash
fly auth signup
```

(or `fly auth login` if the account exists). Fly asks for a card; that's your call, not Claude's.

```bash
fly launch --no-deploy --copy-config --name supplier-whisperer-wei
```

Accept the existing `fly.toml`. Say **no** to Postgres, Redis and Tigris. If the name is taken, pick another and it
updates `app =` in `fly.toml`. (Alternative without the scanner: `fly apps create supplier-whisperer-wei`, then edit
`app =` yourself.)

```bash
fly volumes create whisperer_data --region ewr --size 1
```

Set the secrets (they're stored encrypted on Fly and never written to the repo; type the values in your own
terminal):

```bash
fly secrets set PORTKEY_API_KEY=... GMAIL_APP_PASSWORD=... MAILBOX_SEND=dry-run MY_PERSONAL_EMAIL=you@yale.edu --stage
```

`--stage` stores them without restarting anything (there's nothing running yet).

```bash
fly deploy
```

```bash
fly logs
```

You should see `Supplier Whisperer is running`, `Mailbox: … DRY-RUN`, and
`Private network only (fdaa:…). From your laptop: fly proxy 8000`.

Open the dashboard from your laptop (keep this terminal open):

```bash
fly proxy 8000
```

Then browse to http://127.0.0.1:8000. Email the agent from your Yale address and watch the draft appear.

When the drafts look right, turn on real sending (this restarts the machine):

```bash
fly secrets set MAILBOX_SEND=on
```

Other useful commands:

```bash
fly status
```

```bash
fly ssh console
```

## Stop, roll back, delete

| Goal | Command |
|---|---|
| Stop sending right now | `fly secrets set MAILBOX_SEND=dry-run` (restarts in dry-run), or the dashboard's kill switch via `fly proxy` |
| Stop the machine (no compute cost; volume kept) | `fly scale count 0` (start again: `fly scale count 1`) |
| Roll back to the previous release | `fly releases --image` → copy the previous image ref → `fly deploy --image <ref>` |
| Delete everything (app, machine, volume, secrets) | `fly apps destroy supplier-whisperer-wei` |

The conversation database lives on the volume, so restarts and redeploys keep it. `fly apps destroy` deletes it.

## Expected monthly cost

| Item | Est. / month |
|---|---:|
| `shared-cpu-1x` 256 MB machine, always on | ≈ $2 |
| 1 GB volume | ≈ $0.15 |
| Outbound traffic (a few hundred emails) | ≈ $0 |
| gpt-6-luna (course key; see `docs/tokenomics.md` for the measured per-email cost) | cents |
| **Total** | **≈ $2–3** |

Fly prices change; check https://fly.io/docs/about/pricing/ before you sign up. Fly bills by the second, so
`fly scale count 0` after the grading window stops the machine charge.

## Not verified (hike session)

* Docker isn't installed on this Mac, so `docker build` was **not** run. First check: `fly deploy` builds remotely
  on Fly's builder, so a Dockerfile error would show up there.
* `setpriv` (used by the entrypoint to drop root) ships with Debian's util-linux in `python:3.12-slim`; if the build
  log says otherwise, replace that line with `runuser -u whisperer -- "$@"`.
* `fly proxy` reaching a machine with no services is the documented private-network path, but untested here.
