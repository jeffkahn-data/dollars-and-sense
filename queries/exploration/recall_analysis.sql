-- Recall Analysis Queries
-- Evaluates candidate generation quality through recall metrics
-- Use this to identify which CG sources are capturing purchase intent

-- Note: Run in BigQuery console or via bq command
-- Project: sdp-prd-shop-ml

-- ============================================
-- Query 1: Recall@K by Algorithm (Daily)
-- ============================================

SELECT
  period,
  algorithm_id,
  algorithm_type,
  algorithm_level,
  is_online,
  recommendation_grain,
  app_user_segment_l365d,
  AVG(recall_at_1) AS recall_at_1,
  AVG(recall_at_2) AS recall_at_2,
  AVG(recall_at_10) AS recall_at_10,
  AVG(recall_at_100) AS recall_at_100,
  COUNT(*) AS sample_size
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_recall_metrics`
WHERE period >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND period_type = 'daily'
GROUP BY 1, 2, 3, 4, 5, 6, 7
HAVING sample_size > 100
ORDER BY period, algorithm_id;


-- ============================================
-- Query 2: Product-Level Recall Facts for Experiments
-- ============================================

SELECT
  experiment_handle,
  variant,
  subject_id,
  first_assigned_at,
  recall_at_1,
  recall_at_2,
  recall_at_10,
  recall_at_100
FROM `sdp-prd-shop-ml.measures.measures__shop_personalization__recommendation_l3p_recall_facts`
WHERE first_assigned_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
ORDER BY experiment_handle, variant, first_assigned_at;


-- ============================================
-- Query 3: Merchant-Level Recall Facts for Experiments
-- ============================================

SELECT
  experiment_handle,
  variant,
  subject_id,
  first_assigned_at,
  recall_at_1,
  recall_at_2,
  recall_at_10,
  recall_at_100
FROM `sdp-prd-shop-ml.measures.measures__shop_personalization__recommendation_l3m_recall_facts`
WHERE first_assigned_at >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
ORDER BY experiment_handle, variant, first_assigned_at;


-- ============================================
-- Query 4: Recall T-Test Results (Product Level)
-- ============================================
-- Statistical significance tests for recall improvements

SELECT
  experiment_handle,
  variant,
  COUNT(DISTINCT subject_id) AS subjects,
  AVG(recall_at_1) AS mean_recall_at_1,
  STDDEV(recall_at_1) AS stddev_recall_at_1,
  AVG(recall_at_10) AS mean_recall_at_10,
  STDDEV(recall_at_10) AS stddev_recall_at_10,
  AVG(recall_at_100) AS mean_recall_at_100,
  STDDEV(recall_at_100) AS stddev_recall_at_100
FROM `sdp-prd-shop-ml.measures.measures__shop_personalization__l3p_recall_at_100_ttest`
GROUP BY 1, 2
ORDER BY experiment_handle, variant;


-- ============================================
-- Query 5: Incremental Recall by CG Source
-- ============================================
-- Shows incremental value each CG source adds

WITH base_recall AS (
  SELECT
    algorithm_id,
    AVG(recall_at_100) AS recall_at_100
  FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_recall_metrics`
  WHERE period >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    AND period_type = 'daily'
    AND is_online = TRUE
  GROUP BY 1
),

total_recall AS (
  SELECT
    'all_sources' AS algorithm_id,
    AVG(recall_at_100) AS recall_at_100
  FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_recall_metrics`
  WHERE period >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    AND period_type = 'daily'
    AND is_online = TRUE
    AND algorithm_id = 'combined'  -- or however combined recall is labeled
)

SELECT
  b.algorithm_id,
  b.recall_at_100 AS source_recall,
  t.recall_at_100 AS total_recall,
  b.recall_at_100 / t.recall_at_100 AS recall_contribution_pct
FROM base_recall b
CROSS JOIN total_recall t
ORDER BY b.recall_at_100 DESC;


-- ============================================
-- Query 6: Recall by User Segment
-- ============================================
-- Identifies which user segments have poor recall

SELECT
  app_user_segment_l365d,
  algorithm_type,
  AVG(recall_at_1) AS recall_at_1,
  AVG(recall_at_10) AS recall_at_10,
  AVG(recall_at_100) AS recall_at_100,
  COUNT(DISTINCT period) AS days_measured
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_recall_metrics`
WHERE period >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND period_type = 'daily'
GROUP BY 1, 2
ORDER BY app_user_segment_l365d, algorithm_type;


-- ============================================
-- Query 7: Recall Trend Analysis
-- ============================================
-- Week-over-week recall trends to identify degradation

WITH weekly_recall AS (
  SELECT
    DATE_TRUNC(period, WEEK) AS week_start,
    algorithm_id,
    AVG(recall_at_100) AS recall_at_100
  FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_recall_metrics`
  WHERE period >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
    AND period_type = 'daily'
  GROUP BY 1, 2
)

SELECT
  week_start,
  algorithm_id,
  recall_at_100,
  LAG(recall_at_100) OVER (PARTITION BY algorithm_id ORDER BY week_start) AS prev_week_recall,
  SAFE_DIVIDE(
    recall_at_100 - LAG(recall_at_100) OVER (PARTITION BY algorithm_id ORDER BY week_start),
    LAG(recall_at_100) OVER (PARTITION BY algorithm_id ORDER BY week_start)
  ) AS wow_change
FROM weekly_recall
ORDER BY algorithm_id, week_start;


-- ============================================
-- Query 8: Online vs Offline Recall Comparison
-- ============================================
-- Validates offline recall correlates with online performance

SELECT
  algorithm_id,
  AVG(CASE WHEN is_online = TRUE THEN recall_at_100 END) AS online_recall,
  AVG(CASE WHEN is_online = FALSE THEN recall_at_100 END) AS offline_recall,
  SAFE_DIVIDE(
    AVG(CASE WHEN is_online = TRUE THEN recall_at_100 END),
    AVG(CASE WHEN is_online = FALSE THEN recall_at_100 END)
  ) AS online_offline_ratio
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_recall_metrics`
WHERE period >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND period_type = 'daily'
GROUP BY 1
HAVING online_recall IS NOT NULL AND offline_recall IS NOT NULL
ORDER BY online_offline_ratio DESC;

