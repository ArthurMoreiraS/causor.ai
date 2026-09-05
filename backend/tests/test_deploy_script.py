"""Exercise the production shell with fake Docker/curl; never contact a VPS."""

import os
from pathlib import Path
import shutil
import subprocess

import pytest


SCRIPT = Path(__file__).resolve().parents[2] / "infra" / "deploy.sh"
MOCKS = r'''
docker() {
  printf 'docker %s\n' "$*" >> "$CALL_LOG"
  if [[ "$1" == login ]]; then cat >/dev/null; return 0; fi
  if [[ "$1" == inspect ]]; then
    image=causor-backend
    if [[ "${@: -1}" == frontend ]]; then image=causor-frontend; fi
    tag="$IMAGE_TAG"
    if [[ "$FAIL_AT" == stale ]]; then tag=old; fi
    printf 'ghcr.io/arthurmoreiras/%s:%s\n' "$image" "$tag"
    return 0
  fi
  if [[ " $* " == *" pull "* && "$FAIL_AT" == pull ]]; then return 17; fi
  if [[ " $* " == *" run --rm migrate "* && "$FAIL_AT" == migrate ]]; then return 18; fi
  if [[ " $* " == *" up -d "* && "$FAIL_AT" == up ]]; then return 19; fi
  if [[ " $* " == *" ps -q "* ]]; then printf '%s\n' "${@: -1}"; fi
  return 0
}
curl() {
  printf 'curl %s\n' "$*" >> "$CALL_LOG"
  if [[ "$*" == *docker-compose.prod.yml* ]]; then
    printf 'services: new-release\n' > "${@: -1}"
  fi
}
source "$DEPLOY_SCRIPT"
'''


@pytest.mark.parametrize("failure", ["pull", "migrate", "up", "stale", "none"])
def test_deploy_stops_on_failure_and_verifies_release(tmp_path, failure):
    bash = ("C:/Program Files/Git/bin/bash.exe" if os.name == "nt" else shutil.which("bash"))
    if not bash or not Path(bash).exists():
        pytest.skip("Bash unavailable; exercised in Linux CI")
    (tmp_path / "docker-compose.yml").write_text("previous compose")
    (tmp_path / ".image_tag.env").write_text("IMAGE_TAG=previous\n")
    result = subprocess.run([bash, "-c", MOCKS], capture_output=True, text=True, timeout=20,
        env={**os.environ, "IMAGE_TAG": "a" * 40, "GHCR_USER": "test",
             "GHCR_TOKEN": "test-placeholder", "CAUSOR_DEPLOY_DIR": tmp_path.as_posix(),
             "CALL_LOG": (tmp_path / "calls.log").as_posix(), "FAIL_AT": failure,
             "DEPLOY_SCRIPT": SCRIPT.as_posix()})
    calls = (tmp_path / "calls.log").read_text()
    assert "test-placeholder" not in calls + result.stdout + result.stderr
    if failure != "none":
        assert result.returncode != 0
        assert "https://api.causorai.com/health" not in calls
        assert (tmp_path / ".image_tag.env").read_text() == "IMAGE_TAG=previous\n"
        if failure == "pull":
            assert "run --rm migrate" not in calls
            assert "up -d" not in calls
    else:
        assert result.returncode == 0, result.stderr
        assert "ps -q autos-worker" in calls
        assert "https://api.causorai.com/health" in calls
        assert (tmp_path / ".image_tag.env").read_text() == "IMAGE_TAG=" + "a" * 40 + "\n"
        assert (tmp_path / "docker-compose.previous.yml").read_text() == "previous compose"
