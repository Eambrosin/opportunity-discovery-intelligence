# Opportunity Discovery Intelligence

### Evidence-Aware Target Account Discovery | Lead Generation | Market Adaptation | Commercial Intelligence

[![Python CI](https://github.com/Eambrosin/opportunity-discovery-intelligence/actions/workflows/ci.yml/badge.svg)](https://github.com/Eambrosin/opportunity-discovery-intelligence/actions/workflows/ci.yml)

> **IDENTIFY before you PRIORITIZE.**

Opportunity Discovery Intelligence is a configurable Business Development application for discovering and screening target accounts based on a client-specific market profile.

The application is designed to answer:

> **Which companies should enter the commercial pipeline — and what evidence supports that decision?**

It supports three discovery modes:

1. **Sample dataset** — works immediately with no API key.
2. **Uploaded company universe** — screen a CRM export, directory or purchased dataset.
3. **Public-web discovery** — optional Tavily-powered search that converts public search results into evidence-linked account candidates.

The scoring engine remains deterministic and explainable. AI is optional and is used only after discovery scoring to interpret evidence, generate hypotheses to validate and prepare research questions.

---

## Role in the Commercial Intelligence Ecosystem

This application is the **IDENTIFY** stage of the broader [AI Business Development Toolkit](https://github.com/Eambrosin/AI-Business-Development-Toolkit).

```text
IDENTIFY
Opportunity Discovery Intelligence
← THIS APPLICATION

        ↓

PRIORITIZE
Lead Qualification & Revenue Prioritization

        ↓

ENGAGE
Adaptive Outreach Intelligence

        ↓

PARTNER
Partnership Intelligence

        ↓

EXPAND
Market Entry Intelligence
```

---

## Target Market Configuration

Users can define:

- target industry
- target countries
- target regions
- preferred business models
- required keywords
- exclusion keywords
- preferred company-size range
- target commercial functions
- value proposition / commercial offer

This makes the application adaptable to use cases such as:

- solar distributors in Italy
- food importers in the GCC
- SaaS channel partners in Spain
- logistics companies in Brazil
- industrial distributors in France
- strategic B2B accounts by geography and company profile

---

## Explainable Discovery Model

The default model evaluates:

| Dimension | Default Weight |
|---|---:|
| Industry Fit | 25% |
| Geography Fit | 20% |
| Business Model Fit | 20% |
| Keyword Evidence | 15% |
| Company Size Fit | 10% |
| Evidence Quality | 10% |

When a dimension is genuinely unknown, the engine does not automatically treat the unknown value as a negative signal. Available scoring weights are normalized across the evidence that exists.

A separate **Confidence Score** captures evidence completeness and quality.

This distinction matters:

```text
DISCOVERY SCORE
How well does this account appear to fit?

CONFIDENCE SCORE
How much evidence do we actually have?
```

---

## Evidence-Aware Design

The application distinguishes between:

### Known / Observed

Information contained in the uploaded dataset or public search evidence.

### Commercial Interpretation

A deterministic conclusion derived from the target profile and available evidence.

### Hypothesis

A possible commercial explanation that still requires validation.

### Unknown

Information that should be researched before formal qualification.

The optional AI brief is explicitly instructed not to invent:

- decision makers
- company initiatives
- financials
- expansion plans
- buying signals
- internal priorities
- technologies not present in the evidence

---

## Discovery Sources

### Sample Dataset

A fictional company universe is included for immediate testing.

### CSV Screening

Upload a dataset containing any of the following fields:

```text
company_name
country
region
industry
business_model
company_size
source_title
source_snippet
source_url
```

Common aliases such as `company`, `name`, `employees`, `sector` and `website` are normalized automatically.

### Public Web Discovery

Optional Tavily integration generates market-specific search queries and converts public search results into candidate accounts.

The application deduplicates results by domain and preserves the source URL and evidence snippet.

This is intentionally **not** a LinkedIn scraper and does not depend on private personal data.

---

## Output

Each candidate can include:

- company
- country / region
- industry
- business model
- company size
- Discovery Score
- Confidence Score
- recommended next action
- why the account appears relevant
- matched keywords
- exclusion signals
- unknowns to validate
- evidence URL
- discovery query

Recommended actions include:

```text
Move to Qualification
Research & Validate
Monitor / Enrich
Low Priority
Exclude
```

---

## Qualification Handoff

The application exports a qualification-handoff template aligned with the downstream Lead Qualification platform.

The handoff intentionally marks discovery-stage assumptions for manual enrichment.

Unknown deal value is exported as `0` and initial engagement as `cold`; these fields should be validated before formal opportunity qualification.

Future integration will allow discovery evidence and qualification context to move between applications with less manual work.

---

## Optional AI Evidence Brief

If an OpenAI API key is supplied, the application can generate:

- evidence-grounded relevance summary
- hypotheses to validate
- validation questions
- logical target functions

AI does not modify:

- Discovery Score
- Confidence Score
- exclusion logic
- deterministic prioritization

---

## Public-Web Search

To enable Tavily discovery, provide a Tavily API key in the Streamlit interface or extend the app to use your preferred search provider.

No Tavily key is required for sample or CSV screening modes.

---

## Project Structure

```text
opportunity-discovery-intelligence/
├── app.py
├── discovery_engine.py
├── web_discovery.py
├── ai_insights.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── data/
│   └── sample_company_universe.csv
│
└── tests/
    └── test_discovery_engine.py
```

---

## Run Locally

```bash
git clone https://github.com/Eambrosin/opportunity-discovery-intelligence.git
cd opportunity-discovery-intelligence
python -m venv venv
source venv/bin/activate
pip install -r requirements.txt
streamlit run app.py
```

---

## Testing

```bash
python -m unittest discover -s tests -v
```

GitHub Actions runs syntax validation and the discovery-engine unit tests automatically on pushes and pull requests.

---

## Design Principles

1. **Evidence before claims**
2. **Explainable logic before black-box ranking**
3. **Unknown is not the same as negative**
4. **Discovery is not qualification**
5. **Public-web research should preserve source evidence**
6. **AI should support judgment, not fabricate facts**
7. **Every analysis should end with a commercial next step**

---

## Roadmap

Potential next steps:

- richer provider abstraction for additional search APIs
- website enrichment
- verified company-size enrichment
- industry taxonomy mapping
- contact-function discovery without personal-data scraping
- CRM integrations
- account deduplication across sources
- shared account identifiers across the Commercial Intelligence Toolkit
- direct handoff to Lead Qualification
- market-level discovery analytics
- buying-signal enrichment with explicit provenance
- configurable scoring weights in the UI
- saved ICP / target-market presets
- batch research briefs

---

## Author

**Eduardo Ambrosin**

International Business Development · Strategic Partnerships · GTM · Commercial Intelligence

[GitHub](https://github.com/Eambrosin)  
[LinkedIn](https://www.linkedin.com/in/eduardoambrosin/)  
[Professional Website](https://www.ambrosinlegaltrade.com/)
