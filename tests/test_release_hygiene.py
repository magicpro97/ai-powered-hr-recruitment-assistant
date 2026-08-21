# Standard library imports
import hashlib
import re
from pathlib import Path

# Third-party imports
import yaml
from pypdf import PdfReader

ROOT = Path(__file__).resolve().parents[1]
SELF = Path(__file__).resolve()
MANIFEST = ROOT / "tests" / "public_candidate_files.txt"
MAX_FILE_SIZE = 5 * 1024 * 1024
GENERATED_CACHE_PATTERNS = (
    re.compile(r"^frontend/(?:\.next|node_modules)/.+$"),
    re.compile(
        r"^(?:.+/)?__pycache__/[A-Za-z0-9_.-]+\.cpython-\d{3}(?:-pytest-\d+\.\d+\.\d+)?\.pyc$"
    ),
    re.compile(
        r"^\.pytest_cache/(?:\.gitignore|CACHEDIR\.TAG|README\.md|v/cache/(?:lastfailed|nodeids|stepwise))$"
    ),
)
FORBIDDEN_MODULES = {
    "backend/admin_routes.py",
    "backend/auth_routes.py",
    "backend/calibration_routes.py",
    "backend/evaluation_routes.py",
    "backend/expert_routes.py",
    "backend/feedback_routes.py",
    "backend/itviec_routes.py",
    "backend/research_routes.py",
    "backend/rubric_routes.py",
    "backend/topcv_routes.py",
    "frontend/src/app/(main)/admin/audit/page.tsx",
    "frontend/src/app/(main)/admin/invitations/page.tsx",
    "frontend/src/app/(main)/admin/users/page.tsx",
    "frontend/src/app/(main)/agent/page.tsx",
    "frontend/src/app/(main)/calibration/page.tsx",
    "frontend/src/app/(main)/evaluation/page.tsx",
    "frontend/src/app/(main)/expert/page.tsx",
    "frontend/src/app/(main)/question-review/page.tsx",
    "frontend/src/app/(main)/research/page.tsx",
    "frontend/src/app/evaluation-guide/page.tsx",
    "frontend/src/app/user-guide/page.tsx",
}
APPROVED_MEDIA = {
    "examples/synthetic-cv.pdf",
    "frontend/public/apple-touch-icon.png",
    "frontend/public/favicon.ico",
    "frontend/public/icon-192.png",
    "frontend/public/icon-512.png",
    "frontend/public/icon.svg",
    "frontend/src/app/favicon.ico",
}
MEDIA_SUFFIXES = {
    ".avi",
    ".gif",
    ".ico",
    ".jpeg",
    ".jpg",
    ".mov",
    ".mp4",
    ".pdf",
    ".png",
    ".svg",
    ".webm",
    ".webp",
}
TEXT_PATTERNS = {
    "private-key header": re.compile(r"-----BEGIN (?:[A-Z ]+ )?PRIVATE KEY-----"),
    "personal email": re.compile(
        r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])"
    ),
    "Vietnamese phone": re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){9,10}(?!\d)"),
    "12-digit identifier": re.compile(r"(?<!\d)\d{12}(?!\d)"),
    "screener" + ".work": re.compile(r"screener" r"\.work", re.IGNORECASE),
    "trycloudflare" + ".com": re.compile(r"trycloudflare" r"\.com", re.IGNORECASE),
    "absolute home path": re.compile(
        r"(?<![\w/])/(?:Users|home)/[^/\s]+(?:/|(?=\s|$))", re.IGNORECASE
    ),
}
REPOSITORY_URL = "https://github.com/magicpro97/ai-powered-hr-recruitment-assistant"
README_SECTIONS = [
    "Purpose",
    "Architecture",
    "Prerequisites",
    "Quick start",
    "Synthetic smoke",
    "Evidence boundaries",
    "Security and privacy",
    "Citation",
    "License",
]


def candidate_files():
    for path in ROOT.rglob("*"):
        if not path.is_file():
            continue
        relative = path.relative_to(ROOT)
        relative_text = relative.as_posix()
        if any(
            pattern.fullmatch(relative_text) for pattern in GENERATED_CACHE_PATTERNS
        ):
            continue
        yield path, relative_text


def manifest_paths():
    return {line for line in MANIFEST.read_text(encoding="utf-8").splitlines() if line}


def test_hygiene_scanner_is_self_scanning_and_uses_no_private_home_literal():
    source = SELF.read_text(encoding="utf-8")
    private_home = "/" + "Users" + "/" + "linhn"
    self_skip = "path.resolve()" + " == SELF"

    assert private_home not in source
    assert self_skip not in source
    assert '"absolute home path"' in source


def test_every_physical_non_manifest_file_is_an_explicit_generated_cache():
    physical = {
        path.relative_to(ROOT).as_posix() for path in ROOT.rglob("*") if path.is_file()
    }
    unexpected = {
        relative
        for relative in physical - manifest_paths()
        if not any(pattern.fullmatch(relative) for pattern in GENERATED_CACHE_PATTERNS)
    }

    assert unexpected == set()


def scan_text_tree():
    findings = []
    for path, relative in candidate_files():
        if relative in FORBIDDEN_MODULES:
            findings.append(f"{relative}: forbidden module")
        if path.stat().st_size > MAX_FILE_SIZE:
            findings.append(f"{relative}: exceeds 5 MiB")
        if path.suffix.lower() in MEDIA_SUFFIXES and relative not in APPROVED_MEDIA:
            findings.append(f"{relative}: unapproved media")
        try:
            content = path.read_text(encoding="utf-8")
        except UnicodeDecodeError:
            continue
        for label, pattern in TEXT_PATTERNS.items():
            if relative == "requirements.lock.txt" and label in {
                "Vietnamese phone",
                "12-digit identifier",
            }:
                continue
            if pattern.search(content):
                findings.append(f"{relative}: {label}")
    return findings


def test_public_candidate_file_manifest_is_exact():
    assert MANIFEST.exists()
    assert {relative for _, relative in candidate_files()} == manifest_paths()


def test_public_tree_has_no_private_or_internal_material():
    forbidden = {"thesis", "results", "logs", "uploads", "docs", "cloudflared"}
    assert not (ROOT / ".git").exists()
    assert forbidden.isdisjoint({path.name for path in ROOT.iterdir()})
    assert scan_text_tree() == []


def test_public_release_documents_have_exact_identity_and_safe_claims():
    documents = {path.name for path in ROOT.iterdir() if path.suffix in {".md", ".cff"}}
    assert documents == {"README.md", "CITATION.cff"}

    license_path = ROOT / "LICENSE"
    assert license_path.exists()
    assert hashlib.sha256(license_path.read_bytes()).hexdigest() == (
        "c131ae0e13601a981e3d13ffd1e4fecd403e4f028ccfccd4f5d02ce6def16ae5"
    )

    citation = yaml.safe_load((ROOT / "CITATION.cff").read_text(encoding="utf-8"))
    assert citation["cff-version"] == "1.2.0"
    assert (
        citation["title"]
        == "AI-Powered HR Recruitment Assistant: Thesis Application Prototype"
    )
    assert citation["version"] == "v1.0.0-thesis"
    assert str(citation["date-released"]) == "2026-08-20"
    assert citation["repository-code"] == REPOSITORY_URL
    assert citation["license"] == "MIT"
    assert citation["authors"] == [{"family-names": "Ngô", "given-names": "Thế Linh"}]

    readme = (ROOT / "README.md").read_text(encoding="utf-8")
    headings = re.findall(r"^## (.+)$", readme, re.MULTILINE)
    assert headings == README_SECTIONS
    assert REPOSITORY_URL in readme
    assert "./setup.sh" in readme
    destinations = re.findall(r"\[[^]]*\]\(([^)]+)\)", readme)
    assert not any(
        re.search(r"(?:thesis|results|logs|uploads|docs|cloudflared)", target, re.I)
        for target in destinations
    )
    forbidden_claims = [
        r"enterprise[- ]ready",
        r"proves? (?:a )?hybrid accuracy gain",
        r"validated by recruiters?",
        r"guarantees? fairness",
        r"independently negotiating peer agents",
        r"reproduces? (?:the )?thesis metrics",
    ]
    assert not any(re.search(pattern, readme, re.I) for pattern in forbidden_claims)


def test_synthetic_examples_are_labelled_and_pdf_text_is_extractable():
    jd = (ROOT / "examples" / "synthetic-job-description.txt").read_text(
        encoding="utf-8"
    )
    assert "SYNTHETIC" in jd
    assert "fictional" in jd.lower()

    pdf = PdfReader(ROOT / "examples" / "synthetic-cv.pdf")
    text = "\n".join(page.extract_text() or "" for page in pdf.pages)
    assert len(text.strip()) > 50
    assert "SYNTHETIC" in text
    assert "fictional" in text.lower()


def test_backend_installs_a_fully_hashed_python_312_lock():
    requirements = (ROOT / "requirements.txt").read_text(encoding="utf-8")
    direct = [
        line
        for line in requirements.splitlines()
        if line and not line.startswith(("#", " "))
    ]
    assert direct
    assert all(
        "==" in line and not any(op in line for op in (">=", "~=", "<="))
        for line in direct
    )

    lock = (ROOT / "requirements.lock.txt").read_text(encoding="utf-8")
    stanzas = re.split(r"\n(?=[A-Za-z0-9])", lock)
    packages = [stanza for stanza in stanzas if "==" in stanza.splitlines()[0]]
    assert packages
    assert all("--hash=sha256:" in stanza for stanza in packages)

    dockerfile = (ROOT / "Dockerfile.backend").read_text(encoding="utf-8")
    assert "COPY requirements.lock.txt ." in dockerfile
    assert (
        "pip install --no-cache-dir --require-hashes --prefix=/install -r requirements.lock.txt"
        in dockerfile
    )
    assert "requirements-prod.txt" not in dockerfile
