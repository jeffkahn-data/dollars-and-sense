# Dollars and Sense 💰

A data exploration and optimization toolkit for Shopify's Unified Recommendations system. This repository helps identify underperforming pages, slots, and algorithms to generate product ideas and A/B testing suggestions.

## 🎯 Mission

Maximize the lifetime value of buyers across Shopify by identifying optimization opportunities in the recommendation system—from candidate generation to final display.

## 📊 What This Repository Does

- **Analyze** recommendation performance across pages, modules, algorithms, and recall sets
- **Identify** underperforming components using standardized metrics (CTR, CVR, Recall@K)
- **Generate** product ideas and A/B test hypotheses based on data patterns
- **Track** experiments and their outcomes

## 🏗️ Entity Model

This repository defines four core entity types, aligned with Shopify's data platform conventions:

### 1. Pages (Surfaces)
Where recommendations are displayed to users:
- Shop App Homefeed (Organic)
- Shop App Ads Rail
- Shop App Offers Page
- Shop Store
- Shop Order Management
- Shop Email / Offers Email
- Shopify Product Network

### 2. Modules (Slots)
UI components that render recommendations:
- Section positions (`section_id`, `section_y_pos`)
- Merchant cards (with padding products)
- Product cards
- Exploration vs exploitation slots

### 3. Algorithms
ML models and logic that generate/rank recommendations:
- **L1 (Candidate Generation)**: HSTU, SLIM, NNCF, Recent Interactions, etc.
- **L2 (Reranking)**: XGBoost model, diversity layers, Thompson sampling
- **L3 (Post-processing)**: Merchant aggregation, impression decay

### 4. Recall Sets
Evaluation metrics for algorithm performance:
- Recall@K (K=1, 2, 10, 100)
- Product-level (L3P) and Merchant-level (L3M) recall
- Online vs offline evaluation

## 📁 Repository Structure

```
dollars-and-sense/
├── README.md
├── entities/                    # Entity definitions
│   ├── pages.yaml
│   ├── modules.yaml
│   ├── algorithms.yaml
│   └── recall_sets.yaml
├── queries/                     # SQL queries for analysis
│   ├── exploration/            # Ad-hoc exploration queries
│   ├── metrics/                # Standard metric queries
│   └── diagnostics/            # Debugging queries
├── dashboards/                  # Dashboard configurations
│   └── looker_studio/
├── analysis/                    # Analysis notebooks and scripts
│   └── notebooks/
├── docs/                        # Documentation
│   ├── data_models.md
│   ├── metrics_glossary.md
│   └── onboarding.md
└── .claude/                     # AI assistant context
    └── context.md
```

## 🔗 Key Data Models

Primary data sources in `sdp-prd-shop-ml`:

| Model | Description |
|-------|-------------|
| `product_recommendation.intermediate__shop_personalization__recs_impressions_enriched` | Enriched impression events |
| `product_recommendation.intermediate__shop_personalization__recs_orders_enriched` | Enriched order events with attribution |
| `mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily` | Daily impression metrics by algorithm |
| `mart.mart__shop_personalization__recs_recall_metrics` | Recall@K metrics by algorithm |
| `mart.mart__shop_personalization__recs_executive_summary_metrics` | Executive summary metrics |

## 📈 Key Metrics

| Metric | Definition | Use Case |
|--------|------------|----------|
| **CTR** | Click-through rate: clicks / impressions | User engagement |
| **CVR** | Conversion rate: orders / impressions | Business success |
| **HQCTR** | High-quality click-through rate | Quality engagement |
| **pConv** | Probability of conversion (model score) | Ranking signal |
| **Recall@K** | % of purchases in top-K recommendations | L1 (CG) quality |
| **NDCG@K** | Normalized Discounted Cumulative Gain | L2 (Ranking) quality |

### Understanding NDCG

NDCG measures **ranking quality** - whether relevant items appear at the top of the recommendation list.

- **High Recall + Low NDCG** → Good candidates, poor ranking → Fix L2 reranker
- **Low Recall + High NDCG** → Poor candidates, good ranking → Fix L1 CG
- **High Recall + High NDCG** → Optimal system ✅

See `docs/metrics_glossary.md` for detailed NDCG formulas and interpretation.

## 🚀 Getting Started

### Quick Setup with `dev`

```bash
# Clone and setup with Shopify's dev tool
dev clone jeffkahn-data/dollars-and-sense
cd dollars-and-sense
dev up
```

This will automatically:
- Install Python 3.11
- Create a virtual environment
- Install all dependencies from `tools/requirements.txt`

### Run the NDCG Visualizer

```bash
# Start the Flask server
dev server
# Or manually:
python tools/ndcg_server.py --port 8080
```

Then open http://localhost:8080 to access:
- **🔍 Explorer**: Search and visualize individual recommendation sessions
- **📊 Optimization**: Identify underperforming surfaces, segments, or categories  
- **💰 GMV Opportunity**: Calculate dollar impact of NDCG improvements

### Manual Setup (without `dev`)

```bash
git clone https://github.com/jeffkahn-data/dollars-and-sense.git
cd dollars-and-sense
python3 -m venv .venv
source .venv/bin/activate
pip install -r tools/requirements.txt
python tools/ndcg_server.py --port 8080
```

### BigQuery Access

- Request access to `sdp-prd-shop-ml` via helpdesk
- Follow [Data Platform Access Permissions](https://vault.shopify.io/page/Data-Platform-Access-Permissions~rfTW.md)

### Explore the Dashboard

- [Unified Recommendations Dashboard](https://lookerstudio.google.com/u/0/reporting/7d5e18c5-2e09-479d-870a-b64f7ad0ff4e/page/p_wmdft5ogvd)

## 📚 Resources

- [Unified Recommenders Overview](https://docs.google.com/document/d/1cscWYe5JCX-bQVnR_2Qam64Y66tx8hKtSajQ-qBlP68)
- [CGs and Reranker Doc](https://docs.google.com/document/d/1pMzbhZo76QPB7ayxiBsD7ZHP3_O47gxaQJA-BFf7z6w)
- [Recommendations Team Vault](https://vault.shopify.io/teams/16667-Recommendations)
- [shop-ml Repository](https://github.com/Shopify/shop-ml)

## 🤝 Contributing

Found an optimization opportunity? Add it to `analysis/opportunities.md` with:
- What you found
- Supporting data/queries
- Proposed solution
- Expected impact

---

*Part of Shopify's Unified Recommendations initiative*

