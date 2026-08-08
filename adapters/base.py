"""Shared contract every ATS adapter implements (ADR-0018).

A formal base class instead of duck-typed modules means the next adapter
(Lever, then Comeet — PLAN.md Phase 2) has one documented method to
implement, rather than reverse-engineering the shape from
GreenhouseAdapter's source.
"""

from abc import ABC, abstractmethod


class Adapter(ABC):
    """Base class for one ATS platform's Stage 1 fetch (ADR-0016).

    Constructed with a ComplianceAgent (ADR-0002) rather than importing one,
    so every subclass gets robots.txt + rate-limiting for free and can never
    accidentally call `requests` directly — the dependency is injected, not
    hardcoded, which also keeps adapters testable with a fake/mock agent.
    """

    def __init__(self, compliance_agent):
        self.compliance_agent = compliance_agent

    @abstractmethod
    async def fetch_stage1_jobs(self, ats_slug):
        """Fetch the Stage 1 job list for one company's board.

        Async (ADR-0021): so a scan run can fetch many companies
        concurrently via asyncio.gather, with the ComplianceAgent's
        per-domain locks (not this method) deciding what actually waits.

        Must return a list of dicts shaped {title, department, location,
        absolute_url} — plain, JSON-serializable data with no
        platform-specific objects leaking through, since this is the shape
        the PWA will eventually consume directly (ADR-0018).
        """
        raise NotImplementedError
