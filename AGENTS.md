# Application home and releases

The authoritative repository is https://github.com/Kobii-git/venderintegrationsimmulator.
Keep this application's source, documentation, tests and deployment files there on `main`.
The owner requests that completed updates be committed and pushed to this repository.
Exclude local environments, dependencies, databases, credentials and build caches.

For each future application update, increment the version consistently in
`backend/app/__init__.py`, `backend/app/core/config.py`, `backend/pyproject.toml`,
`frontend/package.json`, `frontend/package-lock.json`, `docker-compose.yml`,
black-box expectations and current-release documentation/build references.
Run applicable checks, commit and push `main`, then tag and push `vX.Y.Z`.
GitHub Actions publishes tested main versions to
`ghcr.io/kobii-git/venderintegrationsimmulator` with version, commit and `latest` tags.
Verify publication and the pulled image before claiming the release is available.
Keep external Sentinel/vendor parser acceptance separate from Docker run verification.
