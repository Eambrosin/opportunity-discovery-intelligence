# v2.0.0 — Commercial Mandate & Market Entry Intelligence

## Release Summary

Version 2.0 turns IDENTIFY from a standalone evidence-aware discovery application into the entry layer of a connected Commercial Mandate Workspace.

The release adds persistent mandate context, role-aware buyer / partner branching, stronger public-web account screening and direct continuity into PRIORITIZE, PARTNER and ENGAGE.

## Highlights

- shared private Commercial Mandate Workspace
- Supabase-backed mandate persistence
- protected Private Workspace Access
- automatic cross-app restoration through opaque `mandate_id`
- portable Commercial Mandate JSON fallback
- Trade & Market Entry Feasibility context
- mandate-aware public-web discovery
- product-aware search query generation
- localized Brazil search terms
- stronger holdback of editorial, research and market-report pages
- buyer / route-to-market / execution-partner role classification
- Account Opportunity and Qualification Readiness kept separate
- public decision-maker and contact validation
- vertical-neutral field-sales intelligence
- buyer handoff to PRIORITIZE
- partner handoff to PARTNER
- execution continuity into ENGAGE
- automated tests, CI and secret scanning

## Commercial Workflow

```text
COMMERCIAL MANDATE
        ↓
IDENTIFY
        ↓
        ├─ Buyer / End Customer → PRIORITIZE → ENGAGE
        └─ Partner Candidate → PARTNER → ENGAGE
```

## Design Principles

- observed evidence remains separate from commercial interpretation
- unknown information remains unknown until validated
- content pages are not treated as target accounts
- high opportunity does not imply buying intent
- role classification is a commercial hypothesis until verified

## Compatibility

Existing CSV / JSON handoffs remain supported. The shared workspace becomes the preferred continuity layer while portable files remain available for fallback and interchange.
