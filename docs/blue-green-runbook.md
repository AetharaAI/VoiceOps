# Blue/Green Runbook (Docker + NGINX)

This runbook keeps live traffic online while deploying a new version.

## Topology
- Blue stack:
  - frontend `127.0.0.1:13000`
  - backend `127.0.0.1:18000`
- Green stack:
  - frontend `127.0.0.1:23000`
  - backend `127.0.0.1:28000`
- NGINX points to exactly one color at a time via an include snippet.

## Files
- `docker-compose.blue.yml`
- `docker-compose.green.yml`
- `infra/nginx/voiceops-upstream-blue.conf`
- `infra/nginx/voiceops-upstream-green.conf`
- `infra/scripts/switch_voiceops_color.sh`

## First-Time Setup
1. Confirm external network exists: `aether_net`
2. Ensure `.env` is correct and does not auto-run migrations.
3. Place one of these in NGINX server block:
   - `include /etc/nginx/snippets/voiceops_active_upstream.conf;`
4. Use `proxy_pass $voiceops_backend;` for API/docs routes.
5. Use `proxy_pass $voiceops_frontend;` for UI route.

## Deploy New Version to Green (while Blue is live)
1. Pull code:
   ```bash
   git pull
   ```
2. Build + start green:
   ```bash
   docker compose -f docker-compose.green.yml up -d --build
   ```
3. Health-check green directly:
   ```bash
   curl -f http://127.0.0.1:28000/api/v1/healthz
   curl -f http://127.0.0.1:23000
   ```
4. Switch traffic to green:
   ```bash
   sudo /path/to/repo/infra/scripts/switch_voiceops_color.sh green
   ```
5. Observe logs for 5-15 minutes.

## Rollback
1. Switch NGINX back to blue:
   ```bash
   sudo /path/to/repo/infra/scripts/switch_voiceops_color.sh blue
   ```
2. Keep green running for forensic debug.

## Promote and Clean Up
- If green is stable, blue can be kept as hot-standby or rebuilt later.
- Do not destroy previous color until confidence window passes.
