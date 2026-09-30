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
ACCOUNT DEVELOPMENT
IDENTIFY ← THIS APPLICATION
   ↓
PRIORITIZE
   ↓
ENGAGE

PARTNERSHIP DEVELOPMENT
IDENTIFY / Partner Universe
   ↓
PARTNER
   ↓
ENGAGE

Both tracks can feed EXPAND / Territory Intelligence.
```

---

## Target Market Configuration

Users can define:

- reusable market preset or fully custom configuration
- target industry
- target countries and regions
- customer / business-model types
- localized discovery archetypes
- positive fit signals / keywords
- exclusion signals
- preferred company-size range
- target decision-maker roles
- value proposition / commercial offer

Current reusable profiles include:

- Renewable Energy
- Agribusiness
- Logistics & Trade
- Fintech
- Real Estate
- Government / Public Sector
- Medical Aesthetics
- Custom

Each preset is editable before execution, so the profile layer accelerates setup without restricting the engine to predefined sectors.

The medical-aesthetics preset includes localized Italian discovery language, clinic/practice archetypes, treatment-technology signals and role profiles. It intentionally keeps device/professional eligibility as a validation step rather than assuming every aesthetic professional can use every device.

---

## Territory Intelligence Mode

For Medical Aesthetics, the app includes a dedicated **North Italy Territory Intelligence** workflow covering:

- Lombardia
- Veneto
- Trentino-Alto Adige / Südtirol

The territory layer is independent from the generic market engine. It adds:

- configurable province/city commercial clusters
- Priority / Full Territory / Custom search scopes
- bilingual Italian/German search logic for Bolzano / Bozen and Südtirol
- Account Opportunity Score
- source-observed vs search-scope location confidence
- territory status such as `Find Decision Maker`, `Research & Enrich` and `Eligibility Validation`
- treatment / technology evidence signals
- public LinkedIn decision-maker discovery
- Contact Readiness Score
- `Ready for Outreach` / `Ready for Field Visit` execution statuses
- region and province intelligence
- searched-vs-unsearched coverage gaps

**Research Coverage is not market share.** It measures the completeness of the current discovery dataset and explicitly distinguishes clusters that were not searched in the current run.

### DELEO North Italy Commercial Program

The optional DELEO profile adds commercial discussion themes and technology-fit evidence without automatically recommending a device.

The profile is based on public DELEO information covering technology categories, training, after-sales support, marketing/digital enablement, patient-development support, localized events and KOL/educational activity.

Public reference sources used by the profile:

- https://www.deleo.fr/fr/contactez-nous/
- https://www.deleo.fr/fr/devenir-distributeur/
- https://www.deleo.fr/fr/blog/medecine-esthetique-mutation-2026/

A technology marked **Not observed — validate** means only that it was not present in the evidence currently available. It does not mean the clinic does not offer it.

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

## Account Enrichment

Discovery now includes an optional evidence-aware **Account Enrichment** layer before formal qualification.

For selected or top-ranked target accounts, the app can research public evidence for:

- direct account website
- website-match confidence
- public business phone
- public business email
- public address
- additional fit signals
- Account Data Completeness
- enrichment source URLs and evidence snippets

The workflow is intentionally selective so users can control public-search credit consumption.

Enrichment does **not** infer deal value, buying intent, company size, device eligibility or current decision authority.

Public contact details can change and should be verified before commercial use.

## Qualification Readiness

The discovery workflow now keeps **Account Opportunity** separate from **Qualification Readiness**.

```text
Account Opportunity
How attractive does the account look?

Qualification Readiness
How much decision-useful evidence do we have before formal qualification?
```

Qualification Readiness can use evidence such as:

- account identity confidence
- source-observed territory location
- verified or probable direct website
- public business phone or email
- professional-setting evidence
- technology / treatment evidence
- public decision-maker candidate evidence

Statuses:

```text
Ready for Qualification
Enrich Before Qualification
Research Required
```

This score is **not** a probability of sale and does not change deal value or buying intent.

The app can export either the full target-account handoff or a **Qualification-Ready Only** subset.

---

## ENGAGE Handoff v2

After public-contact validation, IDENTIFY can export an evidence-aware CSV specifically for the Adaptive Outreach Intelligence application.

The v2 handoff carries forward:

- validated contact name and LinkedIn profile
- contact relevance, professional-role and location-match evidence
- Account Opportunity
- Qualification Readiness
- Sales Motion
- Buyer Access status
- commercial hypothesis and commercial angle
- next best action
- qualification questions
- evidence gaps and validation flags
- account website, public contact form and enrichment status
- observed technology axes and territory metadata

This avoids forcing ENGAGE to rediscover account context and keeps uncertain information explicitly marked for validation rather than converting it into prospect-facing claims.

---

## Sales Intelligence

After discovery, enrichment and readiness assessment, the application can convert the current evidence into an explicit **sales motion** without claiming that the account is actively buying.

The deterministic Sales Intelligence layer can provide:

- buyer-access status
- recommended sales motion
- commercial hypothesis grounded in observed evidence
- evidence-based commercial angle
- next best action
- qualification questions
- evidence gaps to close
- commercial validation flags

Typical motions include:

```text
Research Identity
Validate Fit Before Outreach
Research & Enrich
Complete Qualification Research
Find Decision Maker
Prepare Qualification Outreach
Ready for Qualification Outreach
```

This layer is intentionally separate from Account Opportunity and Qualification Readiness. It does **not** calculate win probability, infer purchase intent, or recommend a specific device from public evidence.

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

The application preserves source URLs and evidence snippets, removes exact duplicates and uses controlled per-domain limits. Account discovery excludes common directories, marketplaces and editorial/search pages from the main target-account workflow so research evidence does not automatically become a sales account.

Account discovery intentionally avoids social-network results so company research stays evidence-focused.

### Public LinkedIn Contact Intelligence

For a selected account, the app can run a separate Tavily search restricted to publicly indexed `linkedin.com/in` results and rank likely contacts against the configured target roles.

For practitioner-led markets, a second workflow can discover public LinkedIn profiles across the market even when the professional is effectively the lead rather than an employee of a larger account.

Outputs can include:

- public profile name
- headline
- public LinkedIn URL
- matched target role
- matched market signals
- contact / professional relevance score
- confidence level
- suggested outreach angle
- source snippet

The application does **not** log into LinkedIn, bypass access controls or scrape private profile content. Public search indexes can be stale, so current role and company should be verified before outreach.

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

Unknown deal value is exported with `deal_value_status=unknown`, while engagement remains explicitly unverified until qualification. Upstream account enrichment and public decision-maker evidence are preserved when available.

The export follows the portfolio's shared Commercial Intelligence handoff contract using fields such as `schema_version`, `source_stage` and `market_profile_id`. The app also provides direct navigation to PRIORITIZE and ENGAGE.

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
├── contact_discovery.py
├── account_enrichment.py
├── sales_intelligence.py
├── presets.py
├── territory_profiles.py
├── territory_intelligence.py
├── vendor_profiles.py
├── ai_insights.py
├── requirements.txt
├── README.md
├── .gitignore
│
├── data/
│   └── sample_company_universe.csv
│
└── tests/
    ├── test_discovery_engine.py
    ├── test_market_intelligence.py
    ├── test_territory_intelligence.py
    ├── test_account_enrichment.py
    └── test_sales_intelligence.py
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

## Deployment

The repository includes a `render.yaml` blueprint for deployment as a Streamlit web service on Render.

The service uses:

```text
Build: pip install -r requirements.txt
Start: streamlit run app.py --server.address 0.0.0.0 --server.port $PORT
```

The app works without external credentials in **Sample dataset** and **Upload CSV** modes.

Optional environment variables:

```text
OPENAI_API_KEY
OPENAI_MODEL
```

For a public deployment, configure `TAVILY_API_KEY` in Streamlit Secrets so visitors can use public-web discovery without seeing or entering the key. If no server-side key is configured, the app still allows a temporary session key for development/testing.

---

### Streamlit Community Cloud Secrets

For the deployed portfolio app, configure secrets in the Streamlit Community Cloud app settings rather than committing credentials to GitHub.

```toml
TAVILY_API_KEY = "your-tavily-key"
OPENAI_API_KEY = "your-openai-key"
```

`TAVILY_API_KEY` enables Public Web Discovery for visitors.  
`OPENAI_API_KEY` is optional and enables the AI Evidence Brief.

Never commit `.streamlit/secrets.toml` or API keys to the repository.

The public-web discovery mode uses Tavily **basic** search and limits each run to a small number of generated queries/results to reduce credit consumption in a portfolio environment.

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
- verified company-size enrichment
- industry taxonomy mapping
- richer public professional/contact discovery
- role-specific outreach handoff
- CRM integrations
- account deduplication across sources
- shared account identifiers across the Commercial Intelligence Toolkit
- direct handoff to Lead Qualification
- deeper territory-level discovery analytics
- field-day planning with route-provider integration
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
