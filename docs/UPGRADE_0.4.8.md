# Release 0.4.8 — simpler installation and updates

20 October 2026. This release updates installation documentation and release
version references. Runtime behavior and dependencies are unchanged.

- First installation uses the public `latest` image with one Docker command.
- Registry login, environment variables, `.env` setup and source builds are not
  required for the normal installation.
- Docker updates pull the image before replacing the container and reuse the
  existing data volume.
- The standalone Compose option uses the same command for installation and updates:
  `docker compose -f docker-compose.image.yml up -d --pull always`.
- Version pinning, source builds and advanced deployment details remain optional.

Follow [installation and update instructions](INSTALLATION.md). Keep a backup of
the complete existing data volume, including `.secret_key`, and retain the same
installation method, ports and volume when updating. There is no database schema
migration or encryption-key change in this release. Running simulations stop
as interrupted on restart under the existing default policy.

To return to 0.4.7, follow the same container replacement instructions with image
tag `0.4.7` instead of `latest`, reusing the same volume. For Compose, pin the image
tag in the saved file to `0.4.7` before running the update command.

Publication and pulled-image verification evidence is recorded in
[implementation status](IMPLEMENTATION_STATUS.md). Docker verification remains
separate from external vendor/parser or Sentinel acceptance.
