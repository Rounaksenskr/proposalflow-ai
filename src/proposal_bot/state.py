import operator
from typing import Annotated, Any, Dict, List, Optional
from pydantic import BaseModel, Field
from typing_extensions import TypedDict


# --- Pydantic Schemas for Structured Ingestion and Outputs ---

class LeadInput(BaseModel):
    client_name: str
    website: Optional[str] = None
    project_description: str
    budget: Optional[str] = None
    deadline: Optional[str] = None


class ResearchArtifact(BaseModel):
    company_summary: str
    industry: str
    pain_points: List[str] = Field(default_factory=list)
    identified_tech: List[str] = Field(default_factory=list)
    source_urls: List[str] = Field(default_factory=list)


class RetrievedCase(BaseModel):
    id: str
    title: str
    industry: str
    similarity_score: float
    technologies: List[str] = Field(default_factory=list)
    summary: str


class ProposalDraft(BaseModel):
    executive_summary: str
    scope_of_work: List[str]
    recommended_tech_stack: List[str]
    timeline_and_phases: str
    estimated_pricing: str
    relevant_experience: str


class CriticFeedback(BaseModel):
    passed: bool
    score: int = Field(ge=1, le=10)
    missing_requirements: List[str] = Field(default_factory=list)
    hallucinated_claims: List[str] = Field(default_factory=list)
    actionable_revisions: List[str] = Field(default_factory=list)


# --- Central LangGraph State ---

class ProposalState(TypedDict):
    lead: Dict[str, Any]
    research: Optional[Dict[str, Any]]
    retrieved_cases: List[Dict[str, Any]]
    proposal: Optional[Dict[str, Any]]

    # Preserves append-only reflection history across retries
    critic_logs: Annotated[List[Dict[str, Any]], operator.add]

    # Explicit decoupled counters
    critic_attempts: int   # Number of evaluations run by critic
    revision_count: int    # Number of actual regenerations run by generator
    retry_count: int       # Backward compatibility alias

    # Human-in-the-loop fields
    human_approved: Optional[bool]
    human_feedback: Optional[str]
    final_status: str