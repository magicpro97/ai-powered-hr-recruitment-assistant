# Standard library imports
from pathlib import Path

# Third-party imports
import yaml

ROOT = Path(__file__).resolve().parents[1]


def read(path: str) -> str:
    return (ROOT / path).read_text(encoding="utf-8")


def compose() -> dict:
    return yaml.safe_load(read("docker-compose.yml"))


def environment(service: dict) -> dict[str, str]:
    return dict(item.split("=", 1) for item in service.get("environment", []))


def test_compose_contains_only_the_public_stack_with_pinned_images():
    data = compose()
    services = data["services"]

    assert set(services) == {
        "postgres",
        "backend",
        "frontend",
        "clamav",
        "clamav-freshclam",
    }
    assert services["clamav-freshclam"]["image"] == "clamav/clamav:1.4.5_base-debian"
    assert services["clamav"]["image"] == "ghcr.io/rntrp/reefspect:v0.1.0"
    assert all(
        ":latest" not in service.get("image", "") for service in services.values()
    )
    assert all("platform" not in service for service in services.values())


def test_postgres_18_volume_uses_the_version_18_parent_mount():
    postgres = compose()["services"]["postgres"]

    assert postgres["image"].startswith("postgres:18")
    assert postgres["volumes"] == ["postgres_data:/var/lib/postgresql"]


def test_compose_uses_production_environment_and_internal_scanner():
    services = compose()["services"]
    backend = services["backend"]
    backend_environment = environment(backend)

    assert backend_environment["ENV"] == "production"
    assert backend_environment["DEBUG"] == "false"
    assert backend_environment["OPENAI_MODEL"].startswith("${OPENAI_MODEL")
    assert backend_environment["CLAMAV_URL"] == "http://clamav:8000"
    assert "EMBEDDING_MODEL" not in backend_environment
    assert not any(key.startswith("SMTP_") for key in backend_environment)
    assert "ports" not in services["postgres"]
    assert "ports" not in services["clamav"]


def test_compose_readiness_covers_database_scanner_backend_and_frontend():
    services = compose()["services"]
    for name in ("postgres", "backend", "frontend"):
        assert services[name].get("healthcheck", {}).get("test"), name

    backend_health = " ".join(services["backend"]["healthcheck"]["test"])
    assert "http://localhost:8000/api/health" in backend_health
    assert "http://clamav:8000/health" in backend_health
    assert (
        services["backend"]["depends_on"]["postgres"]["condition"] == "service_healthy"
    )
    assert services["backend"]["depends_on"]["clamav"]["condition"] == "service_started"
    assert (
        services["clamav"]["depends_on"]["clamav-freshclam"]["condition"]
        == "service_completed_successfully"
    )
    assert services["clamav-freshclam"]["restart"] == "no"


def test_freshclam_only_releases_a_readable_database_after_a_successful_update():
    services = compose()["services"]
    freshclam = services["clamav-freshclam"]
    scanner = services["clamav"]

    assert freshclam["command"] == [
        "sh",
        "-c",
        "freshclam --stdout && chmod -R a+rX /var/lib/clamav",
    ]
    assert "user" not in scanner


def test_compose_host_ports_keep_defaults_and_accept_overrides():
    services = compose()["services"]

    assert services["backend"]["ports"] == ["${BACKEND_PORT:-8000}:8000"]
    assert services["frontend"]["ports"] == ["${FRONTEND_PORT:-3000}:3000"]


def test_frontend_uses_the_versioned_bun_base():
    bases = [
        line.split()[1]
        for line in read("Dockerfile.frontend").splitlines()
        if line.startswith("FROM ")
    ]
    assert bases and set(bases) == {"oven/bun:1.3.9-alpine"}


def test_environment_template_has_only_reviewed_dummy_values():
    env = read(".env.example")
    assert "OPENAI_API_KEY=your_openai_api_key_here" in env
    assert "OPENAI_MODEL=" in env
    assert "POSTGRES_PASSWORD=REPLACE_WITH_GENERATED_SECRET" in env
    assert "JWT_SECRET=REPLACE_WITH_GENERATED_SECRET" in env
    assert "ENV=production" in env
    assert "DEBUG=false" in env
    assert "EMBEDDING_MODEL=" not in env
    assert "DATABASE_URL=" not in env


def test_smoke_script_uses_one_guest_and_owner_only_synthetic_flow():
    smoke = read("scripts/smoke.sh")
    assert "examples/synthetic-job-description.txt" in smoke
    assert "examples/synthetic-cv.pdf" in smoke
    assert smoke.count("uuid.uuid4()") == 1
    assert "X-Guest-Token: $guest_token" in smoke
    assert '"owner_only":true' in smoke
    assert "/api/jobs" in smoke
    assert "/api/cvs" in smoke
    assert "/api/screening" in smoke
    assert "OPENAI_API_KEY" not in smoke
    assert "candidates" in smoke
