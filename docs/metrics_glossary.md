# Metrics Glossary

A comprehensive reference for metrics used in recommendations analysis.

## Performance Metrics

### Click-Through Rate (CTR)
- **Formula**: `clicks / impressions`
- **Description**: Percentage of impressions that result in a click
- **Use Case**: Measures user engagement with recommendations
- **Typical Values**: 0.5% - 2.0% depending on surface and algorithm
- **Benchmark**: Recently Viewed (2%) > HSTU (0.9%) > NNCF (0.8%) > NEUT (0.5%)

### High-Quality Click-Through Rate (HQCTR)
- **Formula**: `hq_clicks / impressions`
- **Description**: CTR filtered for meaningful clicks (excludes bounces)
- **Use Case**: More reliable engagement signal than raw CTR
- **Notes**: Achieved +57.9% improvement on Homefeed, +30.6% on Ads

### Conversion Rate (CVR)
- **Formula**: `orders / impressions`
- **Description**: Percentage of impressions that result in a purchase
- **Use Case**: Ultimate success metric for recommendations
- **Typical Values**: 0.01% - 0.2% depending on surface
- **Benchmark**: Recently Viewed (0.17%) > HSTU (0.06%) > Product SLIM (0.054%)

### Probability of Conversion (pConv)
- **Formula**: XGBoost model output
- **Description**: Predicted probability that user will convert on product
- **Use Case**: Used for ranking candidates in L2 reranker
- **Notes**: Primary objective function for organic recommendations

## Recall Metrics

### Recall@K
- **Formula**: `count(purchased_items_in_top_k) / count(all_purchased_items)`
- **Description**: Fraction of actual purchases that appeared in top-K recommendations
- **Variants**: Recall@1, Recall@2, Recall@10, Recall@100
- **Use Case**: Evaluates candidate generation quality

| Algorithm | Recall@100 |
|-----------|------------|
| Recent Interactions | 33% |
| Product SLIM | 22% |
| Merchant SLIM | 19% |
| NNCF | 5.7% |
| LLM CG | 0.9% |
| NEUT | 0.04% |

### L3P vs L3M Recall
- **L3P (Product-level)**: Recall measured at product granularity
- **L3M (Merchant-level)**: Recall measured at merchant granularity
- **Notes**: L3M typically higher since merchant cards show 4 products

## Ranking Quality Metrics

### NDCG (Normalized Discounted Cumulative Gain)
- **Formula**: `NDCG@K = DCG@K / IDCG@K`
- **Description**: Measures ranking quality by comparing actual ranking to ideal ranking
- **Use Case**: Evaluates how well the reranker orders items by relevance
- **Range**: 0 to 1 (1 = perfect ranking)
- **Key Insight**: Unlike Recall, NDCG captures *position quality* - whether relevant items appear early in the list

#### DCG (Discounted Cumulative Gain)
- **Formula**: `DCG@K = Σ(rel_i / log2(i+1))` for i=1 to K
- **Description**: Sum of relevance scores discounted by position
- **Intuition**: Items at top positions contribute more to the score

#### IDCG (Ideal DCG)
- **Formula**: `IDCG@K = DCG@K` for ideal ordering (highest relevance first)
- **Description**: Maximum possible DCG if items were perfectly ranked

#### Relevance Scoring Options
| Event | Binary Relevance | Graded Relevance |
|-------|------------------|------------------|
| No interaction | 0 | 0 |
| View/Impression | 0 | 1 |
| Click | 1 | 2 |
| Add to Cart | 1 | 3 |
| Purchase | 1 | 4 |

#### NDCG vs Recall Comparison
| Aspect | Recall@K | NDCG@K |
|--------|----------|--------|
| Measures | Coverage (is item present?) | Ranking quality (is item ranked correctly?) |
| Position sensitive | No (binary) | Yes (discounted by log position) |
| Use case | Candidate generation (L1) | Reranking quality (L2/L3) |
| Ideal value | 1.0 (100% coverage) | 1.0 (perfect ranking) |

#### Interpretation Guide
| NDCG@K | Interpretation |
|--------|----------------|
| > 0.8 | Excellent - near-optimal ranking |
| 0.6 - 0.8 | Good - relevant items mostly at top |
| 0.4 - 0.6 | Fair - some ranking inefficiency |
| < 0.4 | Poor - significant ranking issues |

#### When to Use NDCG
- **Reranker evaluation**: Is L2 ordering items correctly?
- **Position optimization**: Are high-converting items at the top?
- **A/B testing**: Compare ranking strategies
- **Algorithm comparison**: Which CG source produces better-ordered lists?

## Attribution Metrics

### Order Attribution
- **Description**: Linking orders back to recommendation impressions
- **Attribution Window**: Typically 24-48 hours
- **Fields**: `attributed_orders`, `attributed_revenue_usd`

### Revenue per Impression
- **Formula**: `revenue_usd / impressions`
- **Use Case**: Measures monetary efficiency of recommendations

## Staleness Metrics

### Session Start Freshness
- **Description**: How fresh recommendations are when user starts session
- **Fields**: `latency_bucket`, `has_fresh_recs`
- **Target**: Minimize stale recommendations

### Recommendation Staleness
- **Description**: How long since recommendations were generated
- **Impact**: Stale recs have lower CTR/CVR
- **Fields**: `fresh_impressions`, `stale_impressions`

## Diversity Metrics

### Effective Number of Categories
- **Description**: Measures taxonomy diversity in recommendations
- **Use Case**: Ensures users see varied product types
- **Optimization**: Balance relevance with diversity

### Merchant Diversity
- **Description**: Number of unique merchants in recommendations
- **Target**: Avoid over-concentration on single merchants

## Business Metrics (Ads)

### Shop Cash Fees
- **Description**: Revenue from advertising recommendations
- **Use Case**: Combined with pConv for ads optimization
- **Formula**: `harmonic_mean(pConv_rank, fee_rank)`

### Harmonic Mean Score
- **Description**: Balanced score between relevance and revenue
- **Use Case**: Ads ranking to balance user experience and monetization
- **Formula**: `2 * (pConv * fee) / (pConv + fee)`

## User Segment Dimensions

### app_user_segment_l365d
- **Description**: User engagement segment over last 365 days
- **Values**: `new`, `active`, `dormant`, `churned`
- **Use Case**: Segment analysis to identify user-specific issues

## Feed Position Metrics

### section_y_pos
- **Description**: Vertical position of card in feed
- **Use Case**: Position decay analysis
- **Expected**: CTR decreases with increasing position

### section_y_pos_bucket
- **Description**: Grouped position ranges for analysis
- **Values**: `1-5`, `6-10`, `11-20`, `21+`

## Module-Specific Metrics

### is_full_card_viewed
- **Description**: Whether user saw all products in merchant card
- **Use Case**: Viewability analysis

### distinct_unified_rec_products_viewed vs distinct_padding_products_viewed
- **Description**: Breakdown of unified rec vs padding product views
- **Use Case**: Evaluate padding effectiveness

## Data Quality Metrics

### duplicate_merchants / duplicate_products
- **Description**: Count of duplicate entities in recommendations
- **Target**: Minimize duplicates for better UX

