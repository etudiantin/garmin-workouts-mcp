# Synology DS224+ Update Guide (Beginner-Friendly)

This guide helps you replace the original `garmin-workouts-mcp` container with this forked version, safely.

## Goal

Deploy this fork on Synology while:

- keeping your current service working
- testing the new version in parallel first
- switching only after validation

---

## Before You Start

You need:

- Synology SSH access (admin account)
- Existing working Garmin MCP container on Synology
- Your fork code available on GitHub (recommended) or copied to NAS

Important for 2FA users:

- Prefer token-based auth with `garth` (`GARTH_HOME` mounted volume)
- Do not rely on `GARMIN_EMAIL` / `GARMIN_PASSWORD` in production with 2FA

---

## Step 1 - Backup Current Container Settings

In **Container Manager**:

1. Open `Container` list
2. Select your current Garmin MCP container
3. Note:
   - container name
   - ports
   - environment variables
   - volume mappings (especially token storage)
   - command/entrypoint

Keep this as rollback reference.

---

## Step 2 - Prepare Project Folder on NAS

SSH into Synology and run:

```bash
mkdir -p /volume1/docker/garmin-workouts-mcp-fork
cd /volume1/docker/garmin-workouts-mcp-fork
```

Option A (recommended): clone your GitHub fork

```bash
git clone https://github.com/<YOUR_GITHUB_USER>/<YOUR_FORK_REPO>.git app
```

Option B: copy local project files into `/volume1/docker/garmin-workouts-mcp-fork/app`.

---

## Step 3 - Build Docker Image on NAS

Build directly on Synology (architecture-safe):

```bash
cd /volume1/docker/garmin-workouts-mcp-fork/app
docker build -f deploy/synology/Dockerfile -t garmin-workouts-mcp:fork-strength .
```

---

## Step 4 - Deploy Test Container In Parallel

In **Container Manager**:

1. Select current container
2. Use **Duplicate settings** (or equivalent clone action)
3. New container name: `garmin-workouts-mcp-fork-test`
4. Change image to: `garmin-workouts-mcp:fork-strength`
5. Keep same env + volumes as current container
6. Change host port to avoid conflict (example old `8000` -> new `18000`)
8. Start test container

Why duplicate settings:

- no accidental command/transport mismatch
- same auth/token mount behavior

---

## Step 5 - Validate New Container

Point your MCP client to the **test container endpoint** (test port) and check:

1. Existing tools still work:
   - `list_workouts`
   - `get_workout`
   - `schedule_workout`

2. New tools are visible:
   - `build_strength_workout`
   - `upload_strength_workout`

3. Strength upload round-trip:
   - upload a small strength workout
   - read back with `get_workout`
   - verify `category`, `exerciseName`, `weightValue`, `reps`, repeat groups

---

## Step 6 - Switch Production

After validation:

1. Stop old container
2. Edit test container:
   - set host port to old production port
   - optionally rename to production name
3. Start/restart container
4. Reconnect MCP client to production endpoint

---

## Step 7 - Rollback (if needed)

If anything is wrong:

1. Stop new container
2. Restart old container
3. Revert MCP endpoint

Because we duplicated settings first, rollback is immediate.

---

## Updating Later

For future updates:

```bash
cd /volume1/docker/garmin-workouts-mcp-fork/app
git pull
docker build -f deploy/synology/Dockerfile -t garmin-workouts-mcp:fork-strength .
```

Then restart/recreate your fork container in Container Manager.

---

## Notes

- Garmin may keep deleted workouts accessible by direct ID lookup for a while, even if not listed.
- Strict exercise validation uses `garmin_exercises_keys_en_fr.csv`, bundled inside the package — no extra file or env var required. Use `GARMIN_STRENGTH_EXERCISES_CSV` only to supply a custom CSV override.
