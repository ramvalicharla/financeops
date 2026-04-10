# Product Overview

FinanceOps is a backend-governed financial control plane.

The product surface is designed to help finance teams understand:

- which organization and entity they are working in
- which module is active
- which period is in scope
- which governed actions are running
- which evidence objects exist for audit and traceability

The frontend does not grant authority. It visualizes backend truth from:

- onboarding APIs
- control-plane context APIs
- airlock APIs
- intent APIs
- job APIs
- lineage, impact, snapshot, and determinism APIs

Core user journeys:

- onboard a new workspace
- review and progress governed journal actions
- inspect intent and job lifecycle details
- review airlock items before admission
- inspect timeline, snapshots, lineage, and impact before or after changes

Control-plane UX goals:

- make context obvious
- reduce ambiguity around governance status
- show empty, loading, and error states clearly
- keep traceability visible instead of hidden in raw payloads
