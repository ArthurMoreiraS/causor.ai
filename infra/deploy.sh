#!/usr/bin/env bash
# Executed on the VPS by the existing SSH workflow, using a short-lived job token.
set -euo pipefail

: "${IMAGE_TAG:?missing release SHA}"
: "${GHCR_USER:?missing registry user}"
: "${GHCR_TOKEN:?missing registry token}"
[[ "$IMAGE_TAG" =~ ^[a-f0-9]{40}$ ]] || exit 2
export IMAGE_TAG
cd "${CAUSOR_DEPLOY_DIR:-/opt/causor}"

# Do not replace the operator's Docker credentials or persist the Actions token.
DOCKER_CONFIG=$(mktemp -d)
export DOCKER_CONFIG
cleanup() {
  rm -f "$DOCKER_CONFIG/config.json"
  rmdir "$DOCKER_CONFIG"
}
trap cleanup EXIT
printf '%s' "$GHCR_TOKEN" | docker login ghcr.io -u "$GHCR_USER" --password-stdin
unset GHCR_TOKEN

candidate=docker-compose.candidate.yml
curl -fsS "https://raw.githubusercontent.com/ArthurMoreiraS/causor.ai/$IMAGE_TAG/infra/docker-compose.prod.yml" -o "$candidate"
compose() {
  docker compose --project-directory "$PWD" -f "$candidate" --env-file .env "$@"
}
compose config --quiet
compose pull
compose run --rm migrate

if [[ -f docker-compose.yml ]]; then cp -p docker-compose.yml docker-compose.previous.yml; fi
if [[ -f .image_tag.env ]]; then cp -p .image_tag.env .image_tag.previous.env; fi
compose up -d --wait --wait-timeout 120

# A healthy old API is not proof that this release was deployed.
for service in backend worker autos-worker frontend; do
  container_id=$(compose ps -q "$service")
  [[ -n "$container_id" ]]
  actual_image=$(docker inspect --format '{{.Config.Image}}' "$container_id")
  image_name=causor-backend
  if [[ "$service" == frontend ]]; then image_name=causor-frontend; fi
  [[ "$actual_image" == "ghcr.io/arthurmoreiras/$image_name:$IMAGE_TAG" ]]
done

mv "$candidate" docker-compose.yml
printf 'IMAGE_TAG=%s\n' "$IMAGE_TAG" > .image_tag.candidate.env
mv .image_tag.candidate.env .image_tag.env
curl -fsS https://api.causorai.com/health
printf '\nRelease %s verified (backend, worker, autos-worker, frontend).\n' "$IMAGE_TAG"
