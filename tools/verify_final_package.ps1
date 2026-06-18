param(
    [string]$ZipPath = "docs\inventarios\projeto_automacao_homologacao_final_segura_20260605.zip"
)

$ErrorActionPreference = "Stop"

$root = Resolve-Path (Join-Path $PSScriptRoot "..")
$zip = Resolve-Path -LiteralPath (Join-Path $root.Path $ZipPath)
$shaPath = "$($zip.Path).sha256"

if (-not (Test-Path -LiteralPath $shaPath)) {
    throw "Arquivo SHA256 nao encontrado: $shaPath"
}

Add-Type -AssemblyName System.IO.Compression.FileSystem
$archive = [System.IO.Compression.ZipFile]::OpenRead($zip.Path)
try {
    $entries = @($archive.Entries | ForEach-Object { $_.FullName -replace "\\", "/" })
    $badEntries = @(
        $entries | Where-Object {
            (($_ -match "(^|/)\.env($|\.)") -and $_ -ne ".env.example") -or
            $_ -match "adintelligence\.db|(^|/)logs/|ffmpeg\.exe|\.zip$|\.sha256$|\.pyc$|\.server\.pid$|\.pytest_tmp"
        }
    )

    $required = @(
        ".env.example",
        "PACKAGE_MANIFEST.json",
        "docs/MISSOES_CONCLUSAO_FINAL.md",
        "docs/TERMO_CONCLUSAO_PROJETO.md",
        "docs/SECURITY_HARDENING_LAYER.md",
        "docs/historico_missoes/RELATORIO_MISSAO35A_SECURITY_SPEC_OFICIAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO35B_RBAC_SERVICE_ACCOUNTS.md",
        "docs/historico_missoes/RELATORIO_MISSAO35C_COMMAND_VALIDATOR.md",
        "docs/historico_missoes/RELATORIO_MISSAO35D_ZERO_TRUST_INTERNAL_CALLS.md",
        "docs/historico_missoes/RELATORIO_MISSAO35E_AUDIT_LOG_IMUTAVEL.md",
        "docs/historico_missoes/RELATORIO_MISSAO35F_HUMAN_APPROVAL_LAYER.md",
        "docs/historico_missoes/RELATORIO_MISSAO35G_SECRETS_VAULT_POLICY.md",
        "docs/historico_missoes/RELATORIO_MISSAO35H_INCIDENT_RESPONSE_MODE.md",
        "docs/historico_missoes/RELATORIO_MISSAO35I_RATE_LIMIT_INTELIGENTE.md",
        "docs/historico_missoes/RELATORIO_SECURITY_HARDENING_LAYER_CONCLUIDA.md",
        "docs/historico_missoes/RELATORIO_MISSAO36A_API_GATEWAY_GUARD.md",
        "docs/historico_missoes/RELATORIO_MISSAO36B_ROUTE_SECURITY_GUARD.md",
        "docs/historico_missoes/RELATORIO_MISSAO36C_EXPANSAO_ROUTE_SECURITY_GUARD.md",
        "docs/historico_missoes/RELATORIO_MISSAO36D_SECURITY_STATUS_DASHBOARD.md",
        "docs/historico_missoes/RELATORIO_MISSAO36E_REAL_MODE_HEALTH_GATE.md",
        "docs/historico_missoes/RELATORIO_MISSAO36F_SECURITY_BRAIN_BRIDGE.md",
        "docs/historico_missoes/RELATORIO_MISSAO36G_SANDBOX_READINESS.md",
        "docs/historico_missoes/RELATORIO_MISSAO36H_SANDBOX_EXECUTION_CONTRACT.md",
        "docs/historico_missoes/RELATORIO_MISSAO36I_TEMPLATE_TESTE_HIPOTESE_01.md",
        "docs/historico_missoes/RELATORIO_MISSAO36J_OPERATIONAL_HANDOFF.md",
        "docs/historico_missoes/RELATORIO_MISSAO36K_META_SANDBOX_SETUP.md",
        "docs/historico_missoes/RELATORIO_MISSAO36L_PRIMEIRO_PAYLOAD_SANDBOX_PAUSADO.md",
        "docs/historico_missoes/RELATORIO_MISSAO37A_GLOBAL_INTELLIGENCE_DATA_CONTRACT.md",
        "docs/historico_missoes/RELATORIO_MISSAO37B_MARKET_RADAR_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37C_WINNING_AD_SCORE_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37D_CREATIVE_INTELLIGENCE_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37E_COUNTRY_INTELLIGENCE_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37F_LANDING_INTELLIGENCE_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37G_OFFER_INTELLIGENCE_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37H_GLOBAL_OPPORTUNITY_BRIEF.md",
        "docs/historico_missoes/RELATORIO_MISSAO37I_GLOBAL_OPERATOR_HUB_DRY_RUN.md",
        "docs/historico_missoes/RELATORIO_MISSAO37J_DASHBOARD_ENTERPRISE_SNAPSHOT.md",
        "docs/historico_missoes/RELATORIO_MISSAO37K_GLOBAL_MINER_HUB_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37L_DATA_MOAT_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37M_API_COMERCIAL_SNAPSHOT.md",
        "docs/historico_missoes/RELATORIO_MISSAO37N_BILLING_READINESS_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37O_MULTI_TENANT_READINESS_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37P_PUBLIC_API_READINESS_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37Q_FRONTEND_ENTERPRISE_SPEC_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37R_REAL_CONNECTORS_READINESS_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37S_VECTOR_DB_READINESS_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37T_AD_LIBRARY_DATA_MODEL_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37U_AD_LIBRARY_SEARCH_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37V_SAAS_COMPLIANCE_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37W_EXECUTIVE_REPORTS_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37X_OPPORTUNITY_ALERTS_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37Y_SATURATION_MONITOR_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO37Z_SCALE_FORECAST_LOCAL.md",
        "docs/historico_missoes/RELATORIO_MISSAO38A_RELEASE_READINESS_LOCAL.md",
        "docs/historico_missoes/RELATORIO_POS_CONCLUSAO_HARDENING_SITEBUILDER.md",
        "docs/historico_missoes/RELATORIO_POS_CONCLUSAO_VERIFICADOR_PACOTE.md",
        "docs/historico_missoes/RELATORIO_POS_CONCLUSAO_GITIGNORE_SEGURO.md",
        "src/app/tests/test_final_safe_e2e.py",
        "src/app/tests/test_command_validator.py",
        "src/app/tests/test_zero_trust_internal_calls.py",
        "src/app/tests/test_immutable_audit_log.py",
        "src/app/tests/test_human_approval_layer.py",
        "src/app/tests/test_secrets_policy.py",
        "src/app/tests/test_incident_response_mode.py",
        "src/app/tests/test_rate_limit.py",
        "src/app/tests/test_api_gateway_guard.py",
        "src/app/tests/test_route_security_guard.py",
        "src/app/tests/test_security_status.py",
        "src/app/tests/test_real_mode_gate.py",
        "src/app/tests/test_security_brain_bridge.py",
        "src/app/tests/test_sandbox_readiness.py",
        "src/app/tests/test_sandbox_execution_contract.py",
        "src/app/tests/test_hypothesis_test_template.py",
        "src/app/tests/test_operational_handoff.py",
        "src/app/tests/test_meta_sandbox_setup.py",
        "src/app/tests/test_first_sandbox_payload.py",
        "src/app/tests/test_global_intelligence_contract.py",
        "src/app/tests/test_market_radar.py",
        "src/app/tests/test_winning_ad_score.py",
        "src/app/tests/test_creative_intelligence.py",
        "src/app/tests/test_country_intelligence.py",
        "src/app/tests/test_landing_intelligence.py",
        "src/app/tests/test_offer_intelligence.py",
        "src/app/tests/test_global_opportunity_brief.py",
        "src/app/tests/test_global_operator_hub.py",
        "src/app/tests/test_enterprise_dashboard_snapshot.py",
        "src/app/tests/test_global_miner_hub.py",
        "src/app/tests/test_data_moat.py",
        "src/app/tests/test_commercial_api_snapshot.py",
        "src/app/tests/test_billing_readiness.py",
        "src/app/tests/test_multi_tenant_readiness.py",
        "src/app/tests/test_public_api_readiness.py",
        "src/app/tests/test_frontend_enterprise_spec.py",
        "src/app/tests/test_real_connectors_readiness.py",
        "src/app/tests/test_vector_db_readiness.py",
        "src/app/tests/test_ad_library_model.py",
        "src/app/tests/test_ad_library_search.py",
        "src/app/tests/test_saas_compliance.py",
        "src/app/tests/test_executive_reports.py",
        "src/app/tests/test_opportunity_alerts.py",
        "src/app/tests/test_saturation_monitor.py",
        "src/app/tests/test_scale_forecast.py",
        "src/app/tests/test_release_readiness.py",
        "src/app/core/api_gateway.py",
        "src/app/core/route_security.py",
        "src/app/core/security_status.py",
        "src/app/core/real_mode_gate.py",
        "src/app/core/security_brain_bridge.py",
        "src/app/core/sandbox_readiness.py",
        "src/app/core/sandbox_execution_contract.py",
        "src/app/core/hypothesis_test_template.py",
        "src/app/core/operational_handoff.py",
        "src/app/core/meta_sandbox_setup.py",
        "src/app/core/first_sandbox_payload.py",
        "src/app/core/global_intelligence_contract.py",
        "src/app/core/market_radar.py",
        "src/app/core/winning_ad_score.py",
        "src/app/core/creative_intelligence.py",
        "src/app/core/country_intelligence.py",
        "src/app/core/landing_intelligence.py",
        "src/app/core/offer_intelligence.py",
        "src/app/core/global_opportunity_brief.py",
        "src/app/core/global_operator_hub.py",
        "src/app/core/enterprise_dashboard_snapshot.py",
        "src/app/core/global_miner_hub.py",
        "src/app/core/data_moat.py",
        "src/app/core/commercial_api_snapshot.py",
        "src/app/core/billing_readiness.py",
        "src/app/core/multi_tenant_readiness.py",
        "src/app/core/public_api_readiness.py",
        "src/app/core/frontend_enterprise_spec.py",
        "src/app/core/real_connectors_readiness.py",
        "src/app/core/vector_db_readiness.py",
        "src/app/core/ad_library_model.py",
        "src/app/core/ad_library_search.py",
        "src/app/core/saas_compliance.py",
        "src/app/core/executive_reports.py",
        "src/app/core/opportunity_alerts.py",
        "src/app/core/saturation_monitor.py",
        "src/app/core/scale_forecast.py",
        "src/app/core/release_readiness.py",
        "src/app/api/routes/campaign_templates.py",
        "src/app/api/routes/global_intelligence.py",
        "src/app/api/routes/security.py",
        "src/app/tests/test_site_builder_legacy_compat.py",
        "src/app/tests/test_security_hardening_rbac.py",
        "tools/verify_final_package.ps1",
        "VERIFICAR_PACOTE_FINAL.bat"
    )
    $missing = @($required | Where-Object { $entries -notcontains $_ })

    $hash = Get-FileHash -LiteralPath $zip.Path -Algorithm SHA256
    $shaText = Get-Content -LiteralPath $shaPath -Raw
    $shaMatches = $shaText -like ($hash.Hash + "*")

    [ordered]@{
        zip = $zip.Path
        total_entries = $entries.Count
        bad_entries_count = $badEntries.Count
        missing_required_count = $missing.Count
        sha256 = $hash.Hash
        sha_file_matches = $shaMatches
    } | ConvertTo-Json

    if ($badEntries.Count -gt 0) {
        throw "Pacote contem arquivos proibidos: $($badEntries -join ', ')"
    }
    if ($missing.Count -gt 0) {
        throw "Pacote sem arquivos obrigatorios: $($missing -join ', ')"
    }
    if (-not $shaMatches) {
        throw "SHA256 externo nao bate com o ZIP."
    }
}
finally {
    $archive.Dispose()
}
