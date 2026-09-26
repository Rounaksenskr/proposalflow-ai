from typing import Optional, List, Dict, Any
from pydantic import BaseModel, Field


class LeadSubmitRequest(BaseModel):
    client_name: str = Field(..., min_length=1, description="Client or company name")
    project_description: str = Field(..., min_length=10, description="Detailed project requirements")
    website: Optional[str] = Field(None, description="Client website URL")
    budget: Optional[str] = Field(None, description="Budget range or cap")
    deadline: Optional[str] = Field(None, description="Target timeline")


class HumanReviewRequest(BaseModel):
    approved: bool = Field(..., description="Approval decision")
    feedback: Optional[str] = Field("Approved via API", description="Reviewer notes or feedback")


class LeadSubmitResponse(BaseModel):
    message: str
    thread_id: str
    status: str
    proposal_draft: Optional[Dict[str, Any]] = None
    critic_evaluation: Optional[Dict[str, Any]] = None


class ProposalStatusResponse(BaseModel):
    thread_id: str
    is_paused: bool
    next_node: List[str]
    final_status: Optional[str] = None
    proposal: Optional[Dict[str, Any]] = None
    critic_logs: Optional[List[Dict[str, Any]]] = None
    human_approved: Optional[bool] = None


class ProposalReviewResponse(BaseModel):
    message: str
    thread_id: str
    final_status: Optional[str] = None
    human_approved: bool


class ErrorResponse(BaseModel):
    message: str
    thread_id: Optional[str] = None
    error: Optional[str] = None