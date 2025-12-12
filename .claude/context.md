# Dollars and Sense - AI Assistant Context

## Project Overview

This repository analyzes Shopify's Unified Recommendations system to identify optimization opportunities. The goal is to find underperforming pages, slots, and algorithms to generate product ideas and A/B testing suggestions.

## Key Concepts

### Unified Recommendations (UR)
- Created Dec 2024 to power all recommendation experiences across Shopify
- Mission: Maximize lifetime value of buyers by recommending optimal path to purchase
- Powers: Shop App (organic + ads), Product Network (2P ads), Email

### Three-Layer Architecture

1. **L1 - Candidate Generation (Recall)**
   - Generates ~200 candidates per source per user
   - Sources: HSTU, SLIM (product/merchant), NNCF, Recently Viewed, LLM CG
   - Key metric: Recall@K (especially @100)

2. **L2 - Reranking**
   - XGBoost model with ~250 features
   - Optimizes for pConv (organic) or harmonic mean of pConv + fees (ads)
   - Applies decay (probabilistic rank, dislike)

3. **L3 - Post-processing**
   - Merchant-level aggregation
   - Diversity enforcement
   - Impression decay
   - Thompson sampling exploration

### Entity Types

1. **Pages** - Surfaces where recs appear (Homefeed, Ads Rail, Offers, etc.)
2. **Modules** - UI components (merchant cards, product cards, exploration slots)
3. **Algorithms** - ML models and logic at each layer
4. **Recall Sets** - Evaluation configurations (Recall@1, @2, @10, @100)

## Data Access

- **Project**: `sdp-prd-shop-ml`
- **Key tables**:
  - `product_recommendation.intermediate__shop_personalization__recs_impressions_enriched`
  - `product_recommendation.intermediate__shop_personalization__recs_orders_enriched`
  - `mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`
  - `mart.mart__shop_personalization__recs_recall_metrics`

## Current Performance Benchmarks (Dec 2024)

| Algorithm | CTR | CVR | Recall@100 |
|-----------|-----|-----|------------|
| Recently Viewed | 2.0% | 0.17% | - |
| HSTU | 0.9% | 0.06% | - |
| Product SLIM | 0.8% | 0.054% | 22% |
| NNCF | 0.8% | 0.046% | 5.7% |
| NEUT | 0.5% | 0.001% | 0.04% |
| Recent Interactions | - | - | 33% |
| Merchant SLIM | 0.8% | - | 19% |

## Key Resources

- [Unified Recommendations Dashboard](https://lookerstudio.google.com/u/0/reporting/7d5e18c5-2e09-479d-870a-b64f7ad0ff4e)
- [Recs Evaluation Tool](https://lookerstudio.google.com/u/0/reporting/1af052ab-be22-4e03-8908-d5bfa3b03ea4)
- [shop-ml Repository](https://github.com/Shopify/shop-ml)
- [disco-flink Repository](https://github.com/Shopify/disco-flink)
- [Recommendations Team Vault](https://vault.shopify.io/teams/16667-Recommendations)

## Common Analysis Patterns

### Identify Underperforming Algorithms
```sql
-- See queries/exploration/algorithm_performance.sql
-- Look for algorithms with CTR/CVR below 1 std dev from mean
```

### Find Position Decay Issues
```sql
-- See queries/exploration/module_performance.sql
-- Compare CTR at position 1 vs position 10+
```

### Evaluate Recall Gaps
```sql
-- See queries/exploration/recall_analysis.sql
-- Look for algorithms with low Recall@100
```

## Slack Channels

- `#unified-recs-ds` - DS team channel
- `#recommendations-team` - Main team channel
- `#recommendations-infra-ops` - Operations/alerts

## Team Context

- **Manager**: Chen (Montreal, Senior Staff PDS)
- **Team Lead**: Mike (Toronto, Staff PDS)
- **Onboarding Buddy**: Sireesha (Bay Area, Staff DE)

