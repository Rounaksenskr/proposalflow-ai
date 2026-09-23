# ProposalFlow AI

An Agentic AI system that automates the freelance lead-to-proposal workflow using LangGraph, RAG, web research, and human-in-the-loop approval.

## Overview

Freelancers often spend significant time researching potential clients, finding relevant previous work, and writing customized proposals.

ProposalFlow AI automates this workflow while keeping the freelancer in control of the final proposal.

The system:

1. Receives a new client lead
2. Extracts and structures the lead information
3. Researches the client/company
4. Retrieves relevant previous projects and proposals
5. Generates a customized proposal
6. Critically evaluates the proposal
7. Regenerates the proposal if quality requirements are not met
8. Pauses for human approval
9. Stores the approved proposal and lead information

---

## Architecture

```text
Client Lead
     │
     ▼
   FastAPI
     │
     ▼
 ┌───────────────┐
 │   LangGraph   │
 │   Workflow    │
 └───────┬───────┘
         │
         ▼
    Ingestion
         │
         ▼
      Research
         │
         ▼
       RAG
    ┌────┴────┐
    │         │
 Vector      BM25
 Search      Search
    │         │
    └────┬────┘
         ▼
    RRF Fusion
         │
         ▼
      Reranker
         │
         ▼
 Relevant Projects
         │
         ▼
 Proposal Generator
         │
         ▼
       Critic
      /     \
   FAIL     PASS
    │         │
    ▼         ▼
  Retry    Human Approval
              │
              ▼
          Database / CRM