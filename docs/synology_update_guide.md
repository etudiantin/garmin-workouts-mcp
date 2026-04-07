# Synology Deployment Guide

> **This guide has been superseded.**
>
> The deployment procedure is now documented in
> [`deploy/synology/DEPLOY.md`](../deploy/synology/DEPLOY.md).
>
> It covers initial deployment, maintenance (update, token rotation,
> garth session renewal) and Claude client configuration,
> using SSH + git + Docker Compose.

---

## Notes

- Garmin may keep deleted workouts accessible by direct ID lookup for a while, even if not listed.
- Strict exercise validation uses `garmin_exercises_keys_en_fr.csv`, bundled inside the package — no extra file or env var required. Use `GARMIN_STRENGTH_EXERCISES_CSV` only to supply a custom CSV override.
- 2FA users: prefer garth token-based auth (`GARTH_HOME` mounted volume) over `GARMIN_EMAIL` / `GARMIN_PASSWORD` in production.
