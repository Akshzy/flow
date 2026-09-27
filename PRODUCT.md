# PRODUCT

## Working name

OrderFlow AI

## Problem

Small online sellers often receive orders through WhatsApp and Instagram conversations and manually copy customer details into notebooks, Excel, shipping panels, or order-management systems.

## Product

A multi-tenant SaaS that connects a seller's supported messaging channels through official APIs, normalizes incoming conversations, extracts structured order information with AI, validates it deterministically, presents uncertain orders for human review, and exports/processes confirmed orders.

## Core value proposition

Turn customer messages into structured, reviewable orders without manually retyping every conversation.

## MVP principle

The product must prioritize reliable inbound order capture over autonomous behavior.

## AI role

AI extracts candidate information.

Deterministic software validates, stores, and controls state.

Human review is required where configured confidence/required-field rules are not satisfied.

## Initial scope

- SaaS authentication
- tenant isolation
- official Meta connection flow
- WhatsApp inbound integration
- webhook ingestion
- normalized messages
- AI order extraction
- order review
- order state management
- CSV/Excel export
- Instagram integration after WhatsApp core stability

## Explicitly deferred

Unless a later phase explicitly adds them:

- unofficial scraping
- password collection
- autonomous browser automation against WhatsApp/Instagram
- shipping aggregation
- payment gateway
- accounting
- inventory synchronization
- mobile application
- vector database/RAG
- multi-agent architecture
- complex analytics
- autonomous customer messaging
