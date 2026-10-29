- Prefix every shell command with `rtk`: `rtk git status`, `rtk cargo test`, `rtk npm run build`, `rtk ls src/`. Keep the prefix inside chains: `rtk git add . && rtk git commit -m "msg"`. Commands RTK has no filter for run as-is, so the prefix is always safe.
- Never execute application code, dependencies, or database migrations natively on the host OS. All runtime execution must be containerized.
- if $USER is `dev`, you are in LOCAL_MODE. else you are in SERVER_MODE.
- If it is only a non code change (e.g. md file), do not re-run the build.
- for database schema changes, use `alembic`
- for data patching, prepare shell and python patch scripts in `patching/{4 digit running number}` directory so that I can execute these within the running container or via `docker exec` or equivalent. The python script must have a `def patch(params: dict = None):` function that allows the patch to be executed via the maintenance module.
- for implemented html codes, favor css class over inline styles.
- the public repo is https://github.com/SkyStrike/portfolio-manager/ if there are any documentations to be linked, use this as the base.

# SERVER_MODE
- Deploy and test via Kubernetes staging overlays (buildctl + kubectl apply -k kubernetes/overlays/staging).

# LOCAL_MODE
- use `docker compose up -d --build` to build and test containers.

## Mandatory VERSION File Bump:
- If a VERSION file exists in the repository root, bump the version whenever code or configuration changes are made:
    - Minor bump (1.0.0 -> 1.1.0) for feat:.
    - Patch bump (1.0.0 -> 1.0.1) for fix:, chore:, refactor:, or configuration edits.
- SemVer Tag Only: The VERSION file strictly sets the container image tag and is decoupled from git tags.
- Stage and commit the updated VERSION file together with your code changes.