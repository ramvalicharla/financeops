# FOLDERTREE_LEDGER

Purpose: Maintain current code structure snapshot.

Rules:
- Include source code, config files, and infrastructure files.
- Exclude cache/build artifacts (`node_modules`, `.venv`, `__pycache__`, build outputs, docker volumes).
- Snapshot is append-only by date.

## Snapshot Entry

Date: 2026-03-05
Prompt Reference: PROMPT-2026-03-05-GOV-LEDGER-SETUP-001
Scope: repository source/config/infra + platform/governance docs

```text
.env
.gitignore
backend/
    .env
    .env.example
    alembic.ini
    Dockerfile
    financeops/
        __init__.py
        api/
            __init__.py
            deps.py
            v1/
                __init__.py
                auditor.py
                auth.py
                bank_recon.py
                gst.py
                health.py
                mis_manager.py
                monthend.py
                reconciliation.py
                router.py
                tenants.py
                working_capital.py
        config.py
        core/
            __init__.py
            auth.py
            exceptions.py
            middleware.py
            security.py
        db/
            __init__.py
            base.py
            models/
                __init__.py
                audit.py
                auditor.py
                bank_recon.py
                credits.py
                gst.py
                mis_manager.py
                monthend.py
                prompts.py
                reconciliation.py
                tenants.py
                users.py
                working_capital.py
            rls.py
            session.py
        llm/
            __init__.py
            circuit_breaker.py
            fallback.py
            gateway.py
            pipeline.py
            providers/
                __init__.py
                anthropic.py
                base.py
                gemini.py
                ollama.py
                openai.py
        main.py
        services/
            __init__.py
            audit_service.py
            auditor_service.py
            auth_service.py
            bank_recon_service.py
            credit_service.py
            gst_service.py
            mis_service.py
            monthend_service.py
            reconciliation_service.py
            tenant_service.py
            user_service.py
            working_capital_service.py
        storage/
            __init__.py
            airlock.py
            provider.py
            r2.py
        tasks/
            __init__.py
            base_task.py
            celery_app.py
        utils/
            __init__.py
            chain_hash.py
            determinism.py
            findings.py
            formatting.py
            pagination.py
            quality_signals.py
            replay_models.py
    migrations/
        env.py
        script.py.mako
        versions/
            0001_initial_schema.py
            0002_phase1_core_finance.py
    pyproject.toml
    tests/
        __init__.py
        conftest.py
        integration/
            __init__.py
            test_auditor_endpoints.py
            test_auth_endpoints.py
            test_bank_recon_endpoints.py
            test_gst_endpoints.py
            test_health.py
            test_mis_endpoints.py
            test_monthend_endpoints.py
            test_reconciliation_endpoints.py
            test_tenant_endpoints.py
            test_working_capital_endpoints.py
        unit/
            __init__.py
            test_auditor_service.py
            test_auth_service.py
            test_bank_recon_service.py
            test_chain_hash.py
            test_credit_service.py
            test_determinism.py
            test_gst_service.py
            test_mis_service.py
            test_monthend_service.py
            test_reconciliation_service.py
            test_working_capital_service.py
    uv.lock
docs/
    ledgers/
        DECISIONS_LEDGER.md
        DEPENDENCIES_LEDGER.md
        FOLDERTREE_LEDGER.md
        IMPLEMENTATION_LEDGER.md
        KEY_CONSIDERATIONS_LEDGER.md
        PROMPTS_LEDGER.md
        SCHEMA_LEDGER.md
        TODO_LEDGER.md
    platform/
        01_MASTER_BLUEPRINT.md
        02_IMPLEMENTATION_PLAN.md
        03_FRONTEND_BACKEND_INTEGRATION.md
        04_ERROR_LEDGER.md
        05_USER_MANUAL.md
        06_CREDITS_AND_PAYMENTS.md
        07_BUSINESS_MODEL_AND_PRICING.md
        08_TELEMETRY_SCALABILITY_METRICS.md
        09_HR_SALES_ENTERPRISE_OS.md
infra/
    .env
    docker-compose.test.yml
    docker-compose.yml
KNOWN_ISSUES.md
frontend/
```


## Snapshot Entry

Date: 2026-03-05
Prompt Reference: PROMPT-2026-03-05-PROMPT-ENGINE-001
Scope: prompt engine modules + test suite additions

```text
backend/
    financeops/
        prompt_engine/
            __init__.py
            cli.py
            dependency_graph.py
            execution_transaction.py
            executor.py
            ledger_updater.py
            prompt_loader.py
            prompt_runner.py
            rework_engine.py
            validation.py
            guardrails/
                __init__.py
                ai_firewall.py
                file_size_enforcer.py
                prompt_sanitizer.py
                repository_protection.py
                security_policy.py
    tests/
        prompt_engine/
            test_dependency_graph.py
            test_execution_pipeline.py
            test_file_size_enforcer.py
            test_guardrails.py
            test_prompt_loader.py
            test_rework_engine.py
    pyproject.toml
```
