"""Domínio: Production Security Audit (Missão 86)."""

from pydantic import BaseModel


class ProductionSecurityAuditConfig(BaseModel):
    security_audit_fail_closed: bool = True
    security_audit_scan_routes: bool = True
