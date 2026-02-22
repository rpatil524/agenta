# Hosting

When you need a local instance of Agenta with:

```bash
bash ./hosting/docker-compose/run.sh [flags...]
```

If conflicts, trust script over this.

## Recipes
- Backend work:
  `bash ./hosting/docker-compose/run.sh --ee --dev --no-web --build`
- Frontend work:
  `bash ./hosting/docker-compose/run.sh --ee --dev --web-local --build`
- Full-Stack work:
  `bash ./hosting/docker-compose/run.sh --ee --dev --build`
- OSS test & work:
  `bash ./hosting/docker-compose/run.sh --oss --dev --build`
- OSS test & build:
  `bash ./hosting/docker-compose/run.sh --oss --gh --local --build`
- OSS test as released:
  `bash ./hosting/docker-compose/run.sh --oss --gh`

## Extensions
- clean rebuild: append `--no-cache` (requires `--build`)
- skip pull step: append `--no-pull`
- volume reset: append `--nuke`
- custom env file: append `--env-file <path>`

## Logs
General:  `docker compose logs -f --tail=200`
Specific: `docker compose -p <project> logs -f --tail=200 <service>`
