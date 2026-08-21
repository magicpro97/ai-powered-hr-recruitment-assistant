# Standard library imports
import ast
import importlib
import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
MAIN = ROOT / "backend" / "main.py"
EXCLUDED_ROUTERS = {
    "admin_routes",
    "auth_routes",
    "calibration_routes",
    "evaluation_routes",
    "expert_routes",
    "feedback_routes",
    "itviec_routes",
    "research_routes",
    "rubric_routes",
    "topcv_routes",
}
EXCLUDED_MODULES = {
    *(f"backend/{name}.py" for name in EXCLUDED_ROUTERS),
    "backend/cv_routes.py",
    "backend/evaluation_utils.py",
    "backend/expert_task_targets.py",
    "backend/actions/base.py",
    "backend/actions/factory.py",
    "backend/actions/list_jobs.py",
    "backend/authorization.py",
    "backend/messages.py",
    "backend/models.py",
    "src/agents/tracing.py",
    "src/database/feedback_db.py",
    "src/processors/template_question_generator.py",
    "src/utils/ai_security.py",
    "src/utils/llm_helper.py",
    "src/utils/vietnamese_utils.py",
}
PUBLIC_ROUTERS = {
    "auth_routes_v2",
    "chat_routes",
    "interview_routes",
}


def main_tree():
    return ast.parse(MAIN.read_text(encoding="utf-8"))


def test_excluded_modules_are_absent():
    assert not {path for path in EXCLUDED_MODULES if (ROOT / path).exists()}
    assert not (ROOT / "uv.lock").exists()


def test_postgres_schema_is_exactly_the_public_runtime_closure():
    source = (ROOT / "src" / "database" / "postgres_db.py").read_text(encoding="utf-8")
    tables = set(
        re.findall(r'CREATE TABLE IF NOT EXISTS\s+"?([a-z_]+)"?', source, re.IGNORECASE)
    )
    indexes = set(
        re.findall(r"CREATE INDEX IF NOT EXISTS\s+([a-z_]+)", source, re.IGNORECASE)
    )

    assert tables == {
        "account_lockout",
        "audit_log",
        "cv_ownership",
        "guest_usage",
        "interview_question_set",
        "job_ownership",
        "login_attempt",
        "password_reset_token",
        "screening_cache",
        "user",
        "user_session",
    }
    assert indexes == {
        "idx_audit_action",
        "idx_audit_created",
        "idx_audit_user",
        "idx_cv_ownership_job",
        "idx_cv_ownership_user",
        "idx_guest_usage_ip",
        "idx_guest_usage_window",
        "idx_iq_set_job",
        "idx_iq_set_user",
        "idx_job_ownership_user",
        "idx_login_attempt_email_created",
        "idx_reset_token_hash",
        "idx_reset_token_user",
        "idx_screening_cache_job",
        "idx_session_jti",
        "idx_session_refresh_jti",
        "idx_session_user",
        "idx_user_email",
        "idx_user_role",
    }


def test_runtime_has_no_research_tracing_or_experiment_plumbing():
    paths = [
        ROOT / "backend" / "chat_routes.py",
        ROOT / "src" / "agents" / "recruitment_agent.py",
        ROOT / "src" / "database" / "postgres_db.py",
        ROOT / "src" / "processors" / "cv_processor.py",
        ROOT / "src" / "processors" / "job_processor.py",
        ROOT / "src" / "processors" / "question_generator.py",
    ]
    forbidden = re.compile(
        r"\b(?:DecisionTracer|experiment_run_id|feedback_type|show_feedback_widget|researcher|tracer)\b"
    )
    findings = [
        path.relative_to(ROOT).as_posix()
        for path in paths
        if forbidden.search(path.read_text(encoding="utf-8"))
    ]

    assert findings == []


def test_matching_engine_has_only_the_hybrid_screening_pipeline():
    path = ROOT / "src" / "processors" / "matching_engine.py"
    source = path.read_text(encoding="utf-8")
    tree = ast.parse(source)
    matching_engine = next(
        node
        for node in tree.body
        if isinstance(node, ast.ClassDef) and node.name == "MatchingEngine"
    )
    methods = {
        node.name: node
        for node in matching_engine.body
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef))
    }

    assert {
        "run_all_baselines",
        "_extract_keywords",
        "_compute_keyword_score",
    }.isdisjoint(methods)
    for method_name in ("match_candidates", "match_candidates_async"):
        assert "pipeline_type" not in {
            argument.arg for argument in methods[method_name].args.args
        }
    assert not any(
        token in source
        for token in ("ats_keyword", "vector_only", "llm_only", "research accuracy")
    )


def test_auth_source_has_no_reference_to_an_absent_internal_plan():
    source = (ROOT / "backend" / "auth.py").read_text(encoding="utf-8")
    assert "feedback_system_plan.md" not in source


def test_pytest_ini_is_the_only_pytest_configuration():
    assert (ROOT / "pytest.ini").exists()
    pyproject = (ROOT / "pyproject.toml").read_text(encoding="utf-8")
    assert "[tool.pytest.ini_options]" not in pyproject


def test_main_registers_only_public_routers():
    registered = {
        call.args[0].value.id
        for call in ast.walk(main_tree())
        if isinstance(call, ast.Call)
        and isinstance(call.func, ast.Attribute)
        and call.func.attr == "include_router"
        and call.args
        and isinstance(call.args[0], ast.Attribute)
        and isinstance(call.args[0].value, ast.Name)
        and call.args[0].attr == "router"
    }
    assert registered == PUBLIC_ROUTERS


def test_main_has_no_admin_endpoint_or_development_deletion():
    tree = main_tree()
    direct_paths = {
        decorator.args[0].value
        for node in ast.walk(tree)
        if isinstance(node, (ast.AsyncFunctionDef, ast.FunctionDef))
        for decorator in node.decorator_list
        if isinstance(decorator, ast.Call)
        and isinstance(decorator.func, ast.Attribute)
        and isinstance(decorator.func.value, ast.Name)
        and decorator.func.value.id == "app"
        and decorator.args
        and isinstance(decorator.args[0], ast.Constant)
        and isinstance(decorator.args[0].value, str)
    }
    called_methods = {
        call.func.attr
        for call in ast.walk(tree)
        if isinstance(call, ast.Call) and isinstance(call.func, ast.Attribute)
    }
    assert not {path for path in direct_paths if path.startswith("/api/admin")}
    assert "delete_test_data" not in called_methods


def test_retained_python_source_has_no_private_deployment_literals():
    patterns = (
        re.compile(r"(?<![\w.+-])[\w.+-]+@[\w.-]+\.[A-Za-z]{2,}(?![\w.-])"),
        re.compile(r"(?<!\d)(?:\+?84|0)(?:[ .-]?\d){9,10}(?!\d)"),
        re.compile(r"screener" + r"\.work", re.IGNORECASE),
        re.compile(r"trycloudflare" + r"\.com", re.IGNORECASE),
    )
    findings = []
    for root in (ROOT / "backend", ROOT / "src"):
        for path in root.rglob("*.py"):
            content = path.read_text(encoding="utf-8").lower()
            if any(pattern.search(content) for pattern in patterns):
                findings.append(path.relative_to(ROOT).as_posix())
    assert findings == []


def test_kept_backend_module_graph_imports_with_dummy_settings(
    tmp_path, monkeypatch, stub_psycopg
):
    modules = (
        "backend.audit_logger",
        "backend.auth_routes_v2",
        "backend.chat_routes",
        "backend.cookie_policy",
        "backend.email_service",
        "backend.interview_routes",
        "backend.pii_masking",
        "backend.security",
        "src.database.postgres_db",
    )
    settings = {
        "CHROMA_PERSIST_DIR": str(tmp_path / "chroma"),
        "DATABASE_URL": "postgresql://public:public@127.0.0.1:5432/public",
        "JWT_SECRET": "public-test-secret-with-at-least-32-characters",
        "OPENAI_API_KEY": "public-test-key",
        "UPLOAD_DIR": str(tmp_path / "uploads"),
    }
    for name, value in settings.items():
        monkeypatch.setenv(name, value)

    for module in modules:
        importlib.import_module(module)
