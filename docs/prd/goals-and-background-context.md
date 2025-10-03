# Goals and Background Context

## Goals
- Build the central orchestration service that coordinates all collections system components into a working end-to-end system
- Implement AI-powered response generation with confidence scoring for tenant communications
- Create an approval workflow for manager oversight of AI-generated responses
- Extract and process payment plans from tenant conversations automatically
- Handle escalations intelligently based on conversation content and timing
- Provide comprehensive metrics and monitoring for the collections workflow

## Background Context
The collections system currently has individual services (SMS Agent, Collections Monitor, Notification Service) but lacks a central coordinator to make them work together. This orchestrator service will be the "brain" that receives incoming SMS, generates contextual AI responses using tenant data, manages approval workflows, and coordinates outbound communications. Without this component, the existing services cannot function as a complete collections workflow, leaving tenant communications unprocessed and payment plan negotiations unautomated.

## Change Log

| Date | Version | Description | Author |
|------|---------|-------------|--------|
| 2025-10-02 | 1.0 | Initial PRD creation based on Kurt's orchestration specification | John (PM) |
| 2025-10-02 | 1.1 | Updated endpoint alignment and added missing endpoints from Kurt's spec | Sarah (PO) |
