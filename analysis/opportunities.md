# Optimization Opportunities

This document tracks identified optimization opportunities for A/B testing.

## How to Add an Opportunity

When you find a potential optimization, add it here with:
1. **What you found** - The observation/data
2. **Supporting evidence** - Queries, charts, metrics
3. **Proposed solution** - What to change
4. **Expected impact** - Estimated lift
5. **Status** - Draft / Proposed / Testing / Shipped / Rejected

---

## Active Opportunities

### [OPP-001] NEUT Algorithm Underperformance
**Status**: Draft  
**Added**: 2025-12-12  
**Author**: Jeff Kahn

**What we found:**
NEUT (Neural Embedding User Tower) has significantly lower CTR (0.5%) and CVR (0.001%) compared to other L1 algorithms, and the lowest Recall@100 (0.04%).

**Supporting evidence:**
```sql
-- From algorithm_performance.sql
-- NEUT: CTR 0.5%, CVR 0.001%, Recall@100 0.04%
-- Compare to HSTU: CTR 0.9%, CVR 0.06%
```

**Proposed solution:**
- Option A: Reduce NEUT's candidate contribution weight in L2
- Option B: Replace NEUT with improved embedding approach
- Option C: Disable NEUT and reallocate to higher-performing CGs

**Expected impact:**
- If we redirect NEUT impressions to HSTU: +80% relative CTR improvement
- At current volume: ~X additional clicks/day

**Next steps:**
- [ ] Quantify NEUT's current impression share
- [ ] Estimate incremental value vs other CGs
- [ ] Discuss with MLE team

---

### [OPP-002] LLM CG Neutral Results
**Status**: Draft  
**Added**: 2025-12-12  
**Author**: Jeff Kahn

**What we found:**
LLM-based Candidate Generation (v3.1) was disabled due to neutral-to-negative results. CTR of 0.92% vs NNCF at 1.64%.

**Supporting evidence:**
- From onboarding doc: "Status: Neutral to negative results so far"
- Recall@100: 0.9%

**Proposed solution:**
- Investigate why semantic understanding isn't translating to better recommendations
- Consider hybrid approach: LLM for interest profiling + traditional CG for retrieval

**Expected impact:**
TBD - Need to understand failure modes

**Next steps:**
- [ ] Review experiment results in detail
- [ ] Identify specific failure cases
- [ ] Propose iteration

---

### [OPP-003] Position Decay Optimization
**Status**: Draft  
**Added**: 2025-12-12  
**Author**: Jeff Kahn

**What we found:**
CTR drops significantly after position 10 in the feed. Need to understand optimal position strategy.

**Supporting evidence:**
```sql
-- Run queries/exploration/module_performance.sql Query 2
-- Expected: CTR at position 1 >> CTR at position 20+
```

**Proposed solution:**
- More aggressive ranking decay for lower positions
- Surface higher-confidence recs earlier in feed
- Consider lazy loading after position X

**Expected impact:**
TBD - Need position decay data

**Next steps:**
- [ ] Run position decay analysis
- [ ] Quantify drop-off curve
- [ ] Model optimal position strategy

---

### [OPP-004] Merchant Card Padding Effectiveness
**Status**: Draft  
**Added**: 2025-12-12  
**Author**: Jeff Kahn

**What we found:**
Merchant cards show 4 products, but if unified recs only provide 1-2, padding with "best sellers" may not be optimal.

**Supporting evidence:**
- Module query 3 shows padding vs unified rec performance
- Need to compare CTR of padded products vs rec products

**Proposed solution:**
- If padding CTR << rec CTR: Consider showing fewer products per card
- If padding CTR competitive: Expand padding criteria
- Alternative: Use model-scored padding instead of best sellers

**Expected impact:**
TBD - Need padding effectiveness data

**Next steps:**
- [ ] Run padding analysis query
- [ ] Compare unified rec vs padding CTR
- [ ] Propose card design changes if warranted

---

### [OPP-005] User Segment Gaps
**Status**: Draft  
**Added**: 2025-12-12  
**Author**: Jeff Kahn

**What we found:**
Different user segments (new, active, dormant, churned) may have different optimal recommendation strategies.

**Supporting evidence:**
```sql
-- Run algorithm_performance.sql Query 2
-- Look for segment-specific underperformance
```

**Proposed solution:**
- Segment-specific algorithm weighting
- Different objective functions by segment
- Cold-start strategies for new users

**Expected impact:**
TBD - Need segment analysis

**Next steps:**
- [ ] Analyze performance by segment
- [ ] Identify segments with biggest gaps
- [ ] Propose segment-specific optimizations

---

### [OPP-006] Ranking Quality Optimization (NDCG)
**Status**: Draft  
**Added**: 2025-12-12  
**Author**: Jeff Kahn

**What we found:**
NDCG (Normalized Discounted Cumulative Gain) analysis reveals that certain CG sources produce candidates that the reranker struggles to order effectively. Even when Recall is high (candidates are relevant), NDCG may be low (relevant items are not ranked at the top).

**Supporting evidence:**
```sql
-- Run queries/exploration/ndcg_analysis.sql
-- Compare NDCG@10 across algorithms
-- Look for: High Recall + Low NDCG = Reranking issue
```

**Proposed solution:**
- For high-recall, low-NDCG sources: Add source-specific features to reranker
- For low-NDCG overall: Review reranker objective function
- Consider source-aware ranking adjustments
- Add NDCG as an online evaluation metric

**Expected impact:**
- +5-10% lift in conversion rate if top-10 ranking improves
- Better user experience with more relevant items visible earlier

**Next steps:**
- [ ] Compute NDCG by algorithm using start-here notebook
- [ ] Identify algorithms with high recall but low NDCG
- [ ] Review reranker features for those sources
- [ ] Propose feature engineering improvements

---

### [OPP-007] High-Position Conversion Optimization
**Status**: Draft  
**Added**: 2025-12-12  
**Author**: Jeff Kahn

**What we found:**
Items in positions 1-5 should have significantly higher conversion rates than items in positions 6+. NDCG analysis helps quantify how much "conversion potential" is lost by suboptimal ranking in these premium positions.

**Supporting evidence:**
```sql
-- From NDCG analysis:
-- DCG discounts items heavily by position (1/log2(rank+1))
-- Position 1: full credit, Position 10: ~30% credit
```

**Proposed solution:**
- Separate optimization for "above the fold" (positions 1-5)
- More aggressive pConv threshold for top positions
- Consider A/B test: stricter top-5 ranking vs current approach

**Expected impact:**
- Each 0.1 increase in NDCG@5 could translate to ~X% more first-scroll conversions
- Focus on the most valuable real estate

**Next steps:**
- [ ] Compute NDCG@5 specifically
- [ ] Analyze conversion rates by position
- [ ] Quantify revenue impact of position swaps
- [ ] Propose position-aware ranking experiment

---

### [OPP-008] Algorithm-Specific Reranking
**Status**: Draft  
**Added**: 2025-12-12  
**Author**: Jeff Kahn

**What we found:**
Different L1 candidate sources may need different reranking strategies. NDCG by source shows which CG algorithms produce candidates that rank well vs poorly.

**Supporting evidence:**
- From Recall vs NDCG diagnostic:
  - High Recall + Low NDCG sources: Good candidates, bad ranking → reranker issue
  - Low Recall + High NDCG sources: Bad candidates, good ranking → CG issue

**Proposed solution:**
- Add `cg_source` as a feature in the reranker
- Consider source-specific score adjustments
- Evaluate if certain sources should have higher base scores

**Expected impact:**
- Better calibration across sources
- Improved NDCG for currently low-performing source combinations

**Next steps:**
- [ ] Run Recall vs NDCG diagnostic in notebook
- [ ] Identify source-specific patterns
- [ ] Work with MLE to add source features to reranker
- [ ] A/B test source-aware ranking

---

## Shipped Opportunities

_None yet - this section tracks successful optimizations_

---

## Rejected Opportunities

_None yet - this section tracks ideas that didn't work out_

---

## Template

```markdown
### [OPP-XXX] Title
**Status**: Draft  
**Added**: YYYY-MM-DD  
**Author**: Name

**What we found:**
[Observation]

**Supporting evidence:**
[Queries, charts, metrics]

**Proposed solution:**
[What to change]

**Expected impact:**
[Estimated lift]

**Next steps:**
- [ ] Step 1
- [ ] Step 2
```

