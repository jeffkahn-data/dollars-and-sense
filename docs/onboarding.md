# Recommendations PDS Onboarding

Welcome to the Unified Recommendations team! This guide will help you get started with the data and analysis tools.

## Week 1: Setup & Exploration

### Day 1-2: Access & Environment

1. **BigQuery Access**
   - Request access to `sdp-prd-shop-ml` via [helpdesk](https://shopify.atlassian.net/servicedesk)
   - Follow [Data Platform Access Permissions](https://vault.shopify.io/page/Data-Platform-Access-Permissions~rfTW.md)
   - Run `clouddopermit` to set up local credentials

2. **Join Google Groups**
   - [recommendations-team](https://groups.google.com/a/shopify.com/g/recommendations-team)
   - [disco-flink-control-plane-readers-prd](https://groups.google.com/a/shopify.com/g/disco-flink-control-plane-readers-prd)

3. **Clone Repositories**
   ```bash
   dev clone shop-ml
   dev clone disco-flink
   ```

4. **Join Slack Channels**
   - `#unified-recs-ds` - DS team
   - `#recommendations-team` - Main team
   - `#recommendations-infra-ops` - Operations
   - `#shop-data-dev` - Development discussions

### Day 3-5: Explore the Data

1. **Review the Dashboard**
   - [Unified Recommendations Dashboard](https://lookerstudio.google.com/u/0/reporting/7d5e18c5-2e09-479d-870a-b64f7ad0ff4e)
   - Go through each tab
   - Note the metrics definitions

2. **Run Exploration Queries**
   - Start with `queries/metrics/daily_summary.sql`
   - Try each query in `queries/exploration/`
   - Note questions that arise

3. **Review Key Documents**
   - [Unified Recommenders Overview](https://docs.google.com/document/d/1cscWYe5JCX-bQVnR_2Qam64Y66tx8hKtSajQ-qBlP68)
   - [CGs and Reranker](https://docs.google.com/document/d/1pMzbhZo76QPB7ayxiBsD7ZHP3_O47gxaQJA-BFf7z6w)
   - Entity definitions in `entities/` folder

## Week 2: Deep Dive

### Understand the System

1. **Architecture Review**
   - [Figma: Pipeline Architecture](https://www.figma.com/board/SDwryku0Q2x762goFJA08i/2025-09-disco-flink-pipelines-architecture)
   - Trace data flow from events → CG → Reranker → Storage

2. **Algorithm Deep Dive**
   - Pick one L1 algorithm (e.g., HSTU, NNCF)
   - Understand its inputs, outputs, and training
   - Review its performance metrics

3. **Experiment Review**
   - [Experiments Platform](https://experiments.shopify.com/)
   - Review recent experiments:
     - [UBI homefeed](https://experiments.shopify.com/experiments/e_recommendations_via_ubi/overview)
     - [UBI ads](https://experiments.shopify.com/experiments/e_ads_recommendations_via_ubi/overview)

### Starter Analysis Project

Pick a question and do exploratory analysis:

**Suggested Topics:**
- Which user segments have the lowest recall?
- How does position affect CTR across surfaces?
- What's the incremental value of each CG source?
- How does staleness impact conversion?

**Deliverables:**
- SQL queries (add to `queries/exploration/`)
- Findings document
- Sandbox Looker dashboard
- Share results with team!

## Week 3-4: Contributing

### Build Understanding

1. **Review Experiments**
   - Read hypothesis and results
   - What conclusions can you draw?
   - Any surprising findings?

2. **Identify Opportunities**
   - Review `analysis/opportunities.md`
   - Add your own findings
   - Propose A/B test ideas

3. **Documentation**
   - Improve this repo's docs
   - Add queries you found useful
   - Document tribal knowledge

### Key Questions to Answer

- What are the top 3 underperforming algorithms?
- Which pages have the biggest optimization opportunity?
- What user segments are we serving poorly?
- Where is the biggest gap between recall and conversion?

## Resources

### Dashboards
| Dashboard | Purpose |
|-----------|---------|
| [Unified Recommendations](https://lookerstudio.google.com/u/0/reporting/7d5e18c5-2e09-479d-870a-b64f7ad0ff4e) | Main metrics dashboard |
| [Recs Evaluation Tool](https://lookerstudio.google.com/u/0/reporting/1af052ab-be22-4e03-8908-d5bfa3b03ea4) | Algorithm comparison |
| [Streaming Product Recs](https://observe.shopify.io/d/6bcaec7e-f4ad-4d19-9219-0352c219f553/streaming-product-recs-2-0) | Infra monitoring |

### Docs
| Document | Purpose |
|----------|---------|
| [Onboarding - Recs Infra](https://docs.google.com/document/d/1dYKsrNyWTk4ba4CGk1WhckeaVSrsm5YNObna4DYuK_g) | Engineering onboarding |
| [UR Experiment Checklist](http://docs.google.com/document/d/1hEHmiMG8Cd6ugW31iqQTdGlZ5jSDg6u0aFm2W5YZ7ks) | Running experiments |
| [Event Refinery](https://vault.shopify.io/page/Event-Refinery~3NfJ.md) | Event system |

### People
| Person | Role | Good For |
|--------|------|----------|
| Chen | Manager, Tech Lead | Strategy, architecture |
| Mike | Staff PDS | Shop App context |
| Sireesha | Onboarding buddy | Day-to-day questions |
| Johann | Staff MLE | Content-based models |
| Yang | Staff DE | Data pipelines |

## Success Criteria

By end of Week 4, you should be able to:
- [ ] Run queries against all key tables
- [ ] Explain the L1/L2/L3 architecture
- [ ] Navigate the dashboards confidently
- [ ] Complete a starter analysis project
- [ ] Identify 2-3 optimization opportunities
- [ ] Contribute to team discussions

