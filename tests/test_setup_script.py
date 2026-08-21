# Standard library imports
import os
import shutil
import stat
import subprocess
from pathlib import Path

# Third-party imports
import pytest

ROOT = Path(__file__).resolve().parents[1]


def test_setup_contract_is_secure_and_compose_v2_only():
    setup = (ROOT / "setup.sh").read_text(encoding="utf-8")

    assert "set -euo pipefail" in setup
    assert "umask 077" in setup
    for command in ("docker", "openssl", "curl"):
        assert f"command -v {command}" in setup
    assert "docker compose version" in setup
    assert "docker-compose" not in setup
    assert "read -r -s" in setup
    assert "docker compose up -d --build" in setup
    assert "300" in setup
    assert "docker compose ps" in setup
    assert "docker compose logs" in setup


def _write_executable(path: Path, content: str) -> None:
    path.write_text(content, encoding="utf-8")
    path.chmod(0o755)


def _run_setup(
    workspace: Path, fake_bin: Path, api_key: str
) -> subprocess.CompletedProcess:
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin"
    env["OPENAI_API_KEY"] = api_key
    return subprocess.run(
        [str(workspace / "setup.sh")],
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )


def test_setup_writes_private_env_and_preserves_generated_secrets(tmp_path):
    workspace = tmp_path / "candidate"
    fake_bin = tmp_path / "bin"
    workspace.mkdir()
    fake_bin.mkdir()
    shutil.copy2(ROOT / "setup.sh", workspace / "setup.sh")
    (workspace / ".env.example").write_text(
        "OPENAI_API_KEY=your_openai_api_key_here\n"
        "OPENAI_MODEL=gpt-4o-mini\n"
        "POSTGRES_USER=hrapp\n"
        "POSTGRES_PASSWORD=REPLACE_WITH_GENERATED_SECRET\n"
        "POSTGRES_DB=hr_assistant\n"
        "JWT_SECRET=REPLACE_WITH_GENERATED_SECRET\n",
        encoding="utf-8",
    )
    _write_executable(
        fake_bin / "docker",
        '#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$FAKE_DOCKER_LOG"\nexit 0\n',
    )
    _write_executable(fake_bin / "curl", "#!/bin/sh\nexit 0\n")
    _write_executable(fake_bin / "open", "#!/bin/sh\nexit 0\n")
    _write_executable(
        fake_bin / "openssl",
        "#!/bin/sh\n"
        'count=$(($(cat "$FAKE_OPENSSL_STATE" 2>/dev/null || printf 0) + 1))\n'
        'printf \'%s\' "$count" > "$FAKE_OPENSSL_STATE"\n'
        "printf '%064d\\n' \"$count\"\n",
    )

    os.environ["FAKE_DOCKER_LOG"] = str(tmp_path / "docker.log")
    os.environ["FAKE_OPENSSL_STATE"] = str(tmp_path / "openssl.state")
    first_key = "sk-test-first-do-not-print"
    first = _run_setup(workspace, fake_bin, first_key)
    assert first.returncode == 0, first.stdout + first.stderr

    env_path = workspace / ".env"
    first_values = dict(
        line.split("=", 1) for line in env_path.read_text(encoding="utf-8").splitlines()
    )
    assert stat.S_IMODE(env_path.stat().st_mode) == 0o600
    assert len(first_values["JWT_SECRET"]) >= 32
    assert len(first_values["POSTGRES_PASSWORD"]) >= 32
    assert "DATABASE_URL" not in first_values
    assert first_key not in first.stdout + first.stderr

    second_key = "sk-test-second-do-not-print"
    second = _run_setup(workspace, fake_bin, second_key)
    assert second.returncode == 0, second.stdout + second.stderr
    second_values = dict(
        line.split("=", 1) for line in env_path.read_text(encoding="utf-8").splitlines()
    )
    assert second_values["JWT_SECRET"] == first_values["JWT_SECRET"]
    assert second_values["POSTGRES_PASSWORD"] == first_values["POSTGRES_PASSWORD"]
    assert second_values["OPENAI_API_KEY"] == second_key
    assert second_key not in second.stdout + second.stderr


def test_setup_never_passes_secrets_in_child_argv(tmp_path):
    workspace = tmp_path / "candidate"
    fake_bin = tmp_path / "bin"
    workspace.mkdir()
    fake_bin.mkdir()
    shutil.copy2(ROOT / "setup.sh", workspace / "setup.sh")
    (workspace / ".env.example").write_text(
        "OPENAI_API_KEY=your_openai_api_key_here\n"
        "OPENAI_MODEL=gpt-4o-mini\n"
        "POSTGRES_USER=hrapp\n"
        "POSTGRES_PASSWORD=REPLACE_WITH_GENERATED_SECRET\n"
        "POSTGRES_DB=hr_assistant\n"
        "JWT_SECRET=REPLACE_WITH_GENERATED_SECRET\n",
        encoding="utf-8",
    )
    _write_executable(fake_bin / "docker", "#!/bin/sh\nexit 0\n")
    _write_executable(fake_bin / "curl", "#!/bin/sh\nexit 0\n")
    _write_executable(
        fake_bin / "openssl",
        "#!/bin/sh\n"
        'count=$(($(cat "$FAKE_OPENSSL_STATE" 2>/dev/null || printf 0) + 1))\n'
        'printf \'%s\' "$count" > "$FAKE_OPENSSL_STATE"\n'
        "printf 'generated-secret-%048d\\n' \"$count\"\n",
    )
    _write_executable(
        fake_bin / "awk",
        '#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$FAKE_ARGV_LOG"\nexec /usr/bin/awk "$@"\n',
    )
    os.environ["FAKE_DOCKER_LOG"] = str(tmp_path / "docker.log")
    os.environ["FAKE_OPENSSL_STATE"] = str(tmp_path / "openssl.state")
    os.environ["FAKE_ARGV_LOG"] = str(tmp_path / "argv.log")

    api_key = "sk-argv-must-stay-private"
    result = _run_setup(workspace, fake_bin, api_key)
    assert result.returncode == 0, result.stdout + result.stderr
    values = dict(
        line.split("=", 1)
        for line in (workspace / ".env").read_text(encoding="utf-8").splitlines()
    )
    argv_log = (tmp_path / "argv.log").read_text(encoding="utf-8")
    for secret in (api_key, values["JWT_SECRET"], values["POSTGRES_PASSWORD"]):
        assert secret not in argv_log


def test_setup_health_checks_honor_host_port_overrides(tmp_path):
    workspace = tmp_path / "candidate"
    fake_bin = tmp_path / "bin"
    workspace.mkdir()
    fake_bin.mkdir()
    shutil.copy2(ROOT / "setup.sh", workspace / "setup.sh")
    (workspace / ".env.example").write_text(
        "OPENAI_API_KEY=your_openai_api_key_here\n"
        "OPENAI_MODEL=gpt-4o-mini\n"
        "POSTGRES_USER=hrapp\n"
        "POSTGRES_PASSWORD=REPLACE_WITH_GENERATED_SECRET\n"
        "POSTGRES_DB=hr_assistant\n"
        "JWT_SECRET=REPLACE_WITH_GENERATED_SECRET\n",
        encoding="utf-8",
    )
    _write_executable(fake_bin / "docker", "#!/bin/sh\nexit 0\n")
    _write_executable(
        fake_bin / "curl",
        '#!/bin/sh\nprintf \'%s\\n\' "$*" >> "$FAKE_CURL_LOG"\nexit 0\n',
    )
    _write_executable(
        fake_bin / "openssl",
        "#!/bin/sh\nprintf '%064d\\n' 1\n",
    )
    env = os.environ.copy()
    env.update(
        {
            "PATH": f"{fake_bin}:/usr/bin:/bin",
            "OPENAI_API_KEY": "sk-test-port-override",
            "BACKEND_PORT": "18000",
            "FRONTEND_PORT": "13000",
            "FAKE_CURL_LOG": str(tmp_path / "curl.log"),
        }
    )

    result = subprocess.run(
        [str(workspace / "setup.sh")],
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    curl_log = (tmp_path / "curl.log").read_text(encoding="utf-8")
    assert "http://localhost:18000/api/health" in curl_log
    assert "http://localhost:13000" in curl_log


def _run_smoke(
    tmp_path: Path, screening_response: str, backend_port: str | None = None
) -> subprocess.CompletedProcess:
    workspace = tmp_path / "candidate"
    fake_bin = tmp_path / "bin"
    (workspace / "scripts").mkdir(parents=True)
    (workspace / "examples").mkdir()
    fake_bin.mkdir()
    shutil.copy2(ROOT / "scripts" / "smoke.sh", workspace / "scripts" / "smoke.sh")
    (workspace / "examples" / "synthetic-job-description.txt").write_text(
        "Synthetic job description long enough for the API contract.", encoding="utf-8"
    )
    (workspace / "examples" / "synthetic-cv.pdf").write_bytes(b"%PDF synthetic")
    _write_executable(
        fake_bin / "docker",
        "#!/bin/sh\n"
        'if [ "${1:-}" = compose ] && [ "${2:-}" = version ]; then exit 0; fi\n'
        'if [ "${1:-}" = compose ] && [ "${2:-}" = exec ]; then\n'
        "  shift 5\n"
        '  exec python3 "$@"\n'
        "fi\n"
        "exit 1\n",
    )
    _write_executable(
        fake_bin / "curl",
        "#!/bin/sh\n"
        'printf \'%s\\n\' "$*" >> "$FAKE_CURL_LOG"\n'
        'case "$*" in\n'
        "  */api/jobs*) printf '%s\\n' '{\"job_id\":\"job-1\"}' ;;\n"
        "  */api/cvs*) printf '%s\\n' '{\"cv_id\":\"cv-1\"}' ;;\n"
        "  */api/screening*) printf '%s\\n' \"$FAKE_SCREENING_RESPONSE\" ;;\n"
        "  *) exit 1 ;;\n"
        "esac\n",
    )
    env = os.environ.copy()
    env["PATH"] = f"{fake_bin}:/usr/bin:/bin"
    env["FAKE_SCREENING_RESPONSE"] = screening_response
    env["FAKE_CURL_LOG"] = str(tmp_path / "curl.log")
    if backend_port:
        env["BACKEND_PORT"] = backend_port
    return subprocess.run(
        [str(workspace / "scripts" / "smoke.sh")],
        cwd=workspace,
        env=env,
        text=True,
        capture_output=True,
        timeout=10,
    )


def test_smoke_accepts_matching_job_with_nonempty_candidate_list(tmp_path):
    result = _run_smoke(
        tmp_path, '{"job_id":"job-1","job_title":"Synthetic","candidates":[{}]}'
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "1 candidate(s)" in result.stdout


def test_smoke_uses_the_backend_port_override(tmp_path):
    result = _run_smoke(
        tmp_path,
        '{"job_id":"job-1","job_title":"Synthetic","candidates":[{}]}',
        backend_port="18000",
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "http://localhost:18000/api/jobs" in (tmp_path / "curl.log").read_text(
        encoding="utf-8"
    )


@pytest.mark.parametrize(
    "response",
    [
        "[]",
        '{"job_id":"job-1","candidates":[]}',
        '{"job_id":"job-1","candidates":"candidate"}',
        '{"job_id":"job-1","candidates":{"cv_id":"cv-1"}}',
        '{"job_id":"other-job","candidates":[{}]}',
    ],
)
def test_smoke_rejects_malformed_or_unbound_screening_response(tmp_path, response):
    result = _run_smoke(tmp_path, response)

    assert result.returncode != 0
    assert "Screening did not complete with at least one candidate" in result.stderr
