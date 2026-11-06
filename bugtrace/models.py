from typing import Literal

from pydantic import BaseModel, Field


class BugReport(BaseModel):
    title: str = ""
    environment: dict = Field(default_factory=dict)
    endpoint: str = ""
    method: str = "POST"
    headers: dict[str, str] = Field(default_factory=dict)
    body: dict = Field(default_factory=dict)
    request_id: str = ""
    expected: dict = Field(default_factory=dict)
    actual: dict = Field(default_factory=dict)
    reported_at: str = ""
    needs_info: list[str] = Field(default_factory=list)


class EvidenceItem(BaseModel):
    id: str
    source: str
    timestamp: str = ""
    confidence: Literal["high", "low"]
    content: dict


class InvariantResult(BaseModel):
    invariant_id: str
    passed: bool
    summary: str
    evidence_ids: list[str] = Field(default_factory=list)


class Hypothesis(BaseModel):
    title: str
    explanation: str
    status: Literal["supported", "weak", "inconclusive"]
    supporting_evidence_ids: list[str] = Field(default_factory=list)
    contradicting_evidence_ids: list[str] = Field(default_factory=list)


class Reproduction(BaseModel):
    attempted: bool = False
    expected: dict = Field(default_factory=dict)
    actual: dict = Field(default_factory=dict)
    matched: bool = False
    reason: str = "not run"


class RegressionResult(BaseModel):
    status: str = "not_run"
    test_source: str = ""
    buggy_result: str = "not_run"
    fixed_result: str = "not_run"
    reason: str = ""


class Investigation(BaseModel):
    case_id: str
    verdict: str
    summary: str
    needs_info: list[str] = Field(default_factory=list)
    evidence: list[EvidenceItem] = Field(default_factory=list)
    invariants: list[InvariantResult] = Field(default_factory=list)
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    reproduction: Reproduction = Field(default_factory=Reproduction)
    regression: RegressionResult = Field(default_factory=RegressionResult)
    limitations: list[str] = Field(default_factory=list)
