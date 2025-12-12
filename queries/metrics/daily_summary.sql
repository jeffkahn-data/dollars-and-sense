-- Daily Summary Metrics
-- Standard query for daily recommendations performance monitoring
-- Run this to get a high-level view of system health

-- Note: Run in BigQuery console or via bq command
-- Project: sdp-prd-shop-ml

-- ============================================
-- Daily Executive Summary
-- ============================================

SELECT
  period,
  surface,
  recommendation_grain,
  metric_type,
  ROUND(SUM(value), 4) AS value
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_executive_summary_metrics`
WHERE period = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
  AND period_type = 'daily'
GROUP BY 1, 2, 3, 4
ORDER BY surface, recommendation_grain, metric_type;


-- ============================================
-- Daily Performance by Algorithm (Top 10)
-- ============================================

SELECT
  algorithm_id,
  SUM(impressions) AS impressions,
  SUM(clicks) AS clicks,
  SUM(orders) AS orders,
  ROUND(SAFE_DIVIDE(SUM(clicks), SUM(impressions)) * 100, 3) AS ctr_pct,
  ROUND(SAFE_DIVIDE(SUM(orders), SUM(impressions)) * 100, 4) AS cvr_pct
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`
WHERE event_day = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
GROUP BY 1
ORDER BY impressions DESC
LIMIT 10;


-- ============================================
-- Daily Recall Summary
-- ============================================

SELECT
  algorithm_id,
  recommendation_grain,
  ROUND(AVG(recall_at_1), 4) AS recall_at_1,
  ROUND(AVG(recall_at_10), 4) AS recall_at_10,
  ROUND(AVG(recall_at_100), 4) AS recall_at_100
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_recall_metrics`
WHERE period = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
  AND period_type = 'daily'
GROUP BY 1, 2
ORDER BY recall_at_100 DESC;


-- ============================================
-- Yesterday vs Last Week Comparison
-- ============================================

WITH yesterday AS (
  SELECT
    algorithm_id,
    SUM(impressions) AS impressions,
    SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
    SAFE_DIVIDE(SUM(orders), SUM(impressions)) AS cvr
  FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`
  WHERE event_day = DATE_SUB(CURRENT_DATE(), INTERVAL 1 DAY)
  GROUP BY 1
),

last_week AS (
  SELECT
    algorithm_id,
    SUM(impressions) AS impressions,
    SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
    SAFE_DIVIDE(SUM(orders), SUM(impressions)) AS cvr
  FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`
  WHERE event_day = DATE_SUB(CURRENT_DATE(), INTERVAL 8 DAY)
  GROUP BY 1
)

SELECT
  y.algorithm_id,
  y.impressions AS yesterday_impressions,
  lw.impressions AS last_week_impressions,
  ROUND((y.ctr - lw.ctr) / lw.ctr * 100, 2) AS ctr_change_pct,
  ROUND((y.cvr - lw.cvr) / lw.cvr * 100, 2) AS cvr_change_pct
FROM yesterday y
LEFT JOIN last_week lw USING (algorithm_id)
WHERE y.impressions > 1000
ORDER BY y.impressions DESC;

