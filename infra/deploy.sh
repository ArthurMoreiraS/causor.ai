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
docker run --rm --network none --user "$(id -u):$(id -g)" --mount "type=bind,src=$PWD,dst=/deploy" \
  "ghcr.io/arthurmoreiras/causor-backend:$IMAGE_TAG" python -m app.agent.model_config --env-file /deploy/.env
compose run --rm migrate

if [[ -f docker-compose.yml ]]; then cp -p docker-compose.yml docker-compose.previous.yml; fi
if [[ -f .image_tag.env ]]; then cp -p .image_tag.env .image_tag.previous.env; fi
compose up -d --wait --wait-timeout 120

# A healthy old API is not proof that this release was deployed.
for service in backend worker autos-worker capture-scheduler frontend; do
  container_id=$(compose ps -q "$service")
  [[ -n "$container_id" ]]
  actual_image=$(docker inspect --format '{{.Config.Image}}' "$container_id")
  image_name=causor-backend
  if [[ "$service" == frontend ]]; then image_name=causor-frontend; fi
  [[ "$actual_image" == "ghcr.io/arthurmoreiras/$image_name:$IMAGE_TAG" ]]
done
compose exec -T backend python -m app.agent.model_config --show

mv "$candidate" docker-compose.yml
printf 'IMAGE_TAG=%s\n' "$IMAGE_TAG" > .image_tag.candidate.env
mv .image_tag.candidate.env .image_tag.env
curl -fsS https://api.causorai.com/health

# Every release leaves ~0.7 GB of images behind; 52 of them filled the 48 GB
# disk to 93% on 09/10/2026. Keep this release and the rollback target only.
previous_tag=$(sed -n 's/^IMAGE_TAG=//p' .image_tag.previous.env 2>/dev/null || true)
mapfile -t stale_images < <(docker images --format '{{.Repository}}:{{.Tag}}' \
  | grep -E '^ghcr\.io/arthurmoreiras/causor-(backend|frontend):' \
  | grep -vE ":($IMAGE_TAG|${previous_tag:-$IMAGE_TAG})$" || true)
if (( ${#stale_images[@]} )); then
  docker rmi "${stale_images[@]}" >/dev/null || true
fi
printf '\nRelease %s verified (backend, worker, autos-worker, capture-scheduler, frontend).\n' "$IMAGE_TAG"
