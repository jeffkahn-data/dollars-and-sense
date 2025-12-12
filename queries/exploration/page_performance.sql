-- Page (Surface) Performance Analysis
-- Compares performance metrics across different recommendation surfaces
-- Use this to identify underperforming pages and optimization opportunities

-- Note: Run in BigQuery console or via bq command
-- Project: sdp-prd-shop-ml

-- ============================================
-- Query 1: Executive Summary by Surface
-- ============================================
-- High-level view of all surfaces

SELECT
  surface,
  period,
  period_type,
  metric_type,
  recommendation_grain,
  SUM(value) AS metric_value
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_executive_summary_metrics`
WHERE period >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND period_type = 'daily'
GROUP BY 1, 2, 3, 4, 5
ORDER BY surface, period, metric_type;


-- ============================================
-- Query 2: Organic vs Ads Performance Comparison
-- ============================================

WITH organic_metrics AS (
  SELECT
    'organic' AS surface_type,
    event_day,
    SUM(impressions) AS impressions,
    SUM(clicks) AS clicks,
    SUM(orders) AS orders,
    SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
    SAFE_DIVIDE(SUM(orders), SUM(impressions)) AS cvr
  FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`
  WHERE event_day >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  GROUP BY 1, 2
),

ads_metrics AS (
  SELECT
    'ads' AS surface_type,
    period AS event_day,
    SUM(impressions) AS impressions,
    SUM(clicks) AS clicks,
    SUM(orders) AS orders,
    SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
    SAFE_DIVIDE(SUM(orders), SUM(impressions)) AS cvr
  FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_ads_impressions_metrics`
  WHERE period >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
    AND period_type = 'daily'
  GROUP BY 1, 2
)

SELECT * FROM organic_metrics
UNION ALL
SELECT * FROM ads_metrics
ORDER BY event_day, surface_type;


-- ============================================
-- Query 3: Session-Level Performance by Surface
-- ============================================

SELECT
  period,
  app_user_segment_l365d,
  SUM(sessions) AS total_sessions,
  SUM(sessions_with_impressions) AS sessions_with_impressions,
  SUM(sessions_with_clicks) AS sessions_with_clicks,
  SUM(sessions_with_orders) AS sessions_with_orders,
  SAFE_DIVIDE(SUM(sessions_with_clicks), SUM(sessions_with_impressions)) AS session_ctr,
  SAFE_DIVIDE(SUM(sessions_with_orders), SUM(sessions_with_impressions)) AS session_cvr
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_sessions_metrics`
WHERE period >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND period_type = 'daily'
GROUP BY 1, 2
ORDER BY period, app_user_segment_l365d;


-- ============================================
-- Query 4: Ads Surface Breakdown
-- ============================================

SELECT
  surface,
  period,
  recommendation_grain,
  app_user_segment_l365d,
  SUM(impressions) AS impressions,
  SUM(clicks) AS clicks,
  SUM(orders) AS orders,
  SUM(revenue_usd) AS revenue_usd,
  SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
  SAFE_DIVIDE(SUM(orders), SUM(impressions)) AS cvr,
  SAFE_DIVIDE(SUM(revenue_usd), SUM(impressions)) AS revenue_per_impression
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_ads_impressions_metrics`
WHERE period >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND period_type = 'daily'
GROUP BY 1, 2, 3, 4
ORDER BY surface, period;


-- ============================================
-- Query 5: Order Attribution by Surface
-- ============================================
-- Shows how orders are attributed to different recommendation surfaces

SELECT
  period,
  surface,
  recommendation_grain,
  app_user_segment_l365d,
  SUM(attributed_orders) AS attributed_orders,
  SUM(attributed_revenue_usd) AS attributed_revenue_usd,
  SUM(total_orders) AS total_orders,
  SAFE_DIVIDE(SUM(attributed_orders), SUM(total_orders)) AS attribution_rate
FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_order_attribution_metrics`
WHERE period >= DATE_SUB(CURRENT_DATE(), INTERVAL 30 DAY)
  AND period_type = 'daily'
GROUP BY 1, 2, 3, 4
ORDER BY period, surface;


-- ============================================
-- Query 6: Surface Performance Trends
-- ============================================
-- Week-over-week trends to identify declining surfaces

WITH weekly_metrics AS (
  SELECT
    DATE_TRUNC(event_day, WEEK) AS week_start,
    section_id,
    SUM(impressions) AS impressions,
    SUM(clicks) AS clicks,
    SUM(orders) AS orders,
    SAFE_DIVIDE(SUM(clicks), SUM(impressions)) AS ctr,
    SAFE_DIVIDE(SUM(orders), SUM(impressions)) AS cvr
  FROM `sdp-prd-shop-ml.mart.mart__shop_personalization__recs_super_feed_impressions_metrics_daily`
  WHERE event_day >= DATE_SUB(CURRENT_DATE(), INTERVAL 90 DAY)
  GROUP BY 1, 2
)

SELECT
  week_start,
  section_id,
  impressions,
  ctr,
  cvr,
  LAG(ctr) OVER (PARTITION BY section_id ORDER BY week_start) AS prev_week_ctr,
  LAG(cvr) OVER (PARTITION BY section_id ORDER BY week_start) AS prev_week_cvr,
  SAFE_DIVIDE(ctr - LAG(ctr) OVER (PARTITION BY section_id ORDER BY week_start),
              LAG(ctr) OVER (PARTITION BY section_id ORDER BY week_start)) AS ctr_wow_change,
  SAFE_DIVIDE(cvr - LAG(cvr) OVER (PARTITION BY section_id ORDER BY week_start),
              LAG(cvr) OVER (PARTITION BY section_id ORDER BY week_start)) AS cvr_wow_change
FROM weekly_metrics
ORDER BY section_id, week_start;

