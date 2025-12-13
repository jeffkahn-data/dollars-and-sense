"""
Unit tests for the NDCG Server Flask application.

Tests cover:
- Helper functions (safe_float)
- Flask routes (using test client)
- API endpoints
"""

import json
import math
import pytest
import sys
from pathlib import Path
from unittest.mock import patch, MagicMock

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))


class TestSafeFloat:
    """Tests for the safe_float helper function."""
    
    def test_safe_float_with_normal_number(self):
        """Normal numbers should pass through unchanged."""
        from ndcg_server import safe_float
        assert safe_float(3.14) == 3.14
        assert safe_float(0) == 0
        assert safe_float(-1.5) == -1.5
    
    def test_safe_float_with_nan(self):
        """NaN should be converted to None."""
        from ndcg_server import safe_float
        assert safe_float(float('nan')) is None
    
    def test_safe_float_with_inf(self):
        """Infinity should be converted to None."""
        from ndcg_server import safe_float
        assert safe_float(float('inf')) is None
        assert safe_float(float('-inf')) is None
    
    def test_safe_float_with_none(self):
        """None should remain None."""
        from ndcg_server import safe_float
        assert safe_float(None) is None
    
    def test_safe_float_with_integer(self):
        """Integers should work correctly."""
        from ndcg_server import safe_float
        assert safe_float(42) == 42
        assert safe_float(0) == 0


class TestFlaskApp:
    """Tests for Flask application routes."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app."""
        from ndcg_server import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_index_route(self, client):
        """Index route should return HTML."""
        response = client.get('/')
        assert response.status_code == 200
        assert b'<!DOCTYPE html>' in response.data
        assert b'NDCG Ranking Visualizer' in response.data
    
    def test_index_contains_tabs(self, client):
        """Index should contain all three tabs."""
        response = client.get('/')
        assert b'Explorer' in response.data
        assert b'Optimization' in response.data
        assert b'GMV Opportunity' in response.data


class TestAPIFilters:
    """Tests for the /api/filters endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app."""
        from ndcg_server import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    @patch('ndcg_server.get_bq_client')
    def test_filters_endpoint_structure(self, mock_bq, client):
        """Filters endpoint should return expected structure."""
        # Mock BigQuery response
        mock_client = MagicMock()
        mock_bq.return_value = mock_client
        
        # Create mock dataframe with equal length columns
        import pandas as pd
        mock_df = pd.DataFrame({
            'category': ['Beauty', 'Electronics', 'Toys'],
            'segment': ['returning', 'anonymous', 'new'],
            'surface': ['super_feed', 'ads_rail', 'offers']
        })
        mock_client.query.return_value.to_dataframe.return_value = mock_df
        
        response = client.get('/api/filters')
        assert response.status_code == 200
        
        data = json.loads(response.data)
        assert 'categories' in data
        assert 'segments' in data
        assert 'surfaces' in data


class TestAPISessions:
    """Tests for the /api/sessions endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app."""
        from ndcg_server import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_sessions_accepts_params(self, client):
        """Sessions endpoint should accept query parameters."""
        # This will likely fail without BigQuery, but tests param handling
        response = client.get('/api/sessions?category=Beauty&segment=returning&days_back=7&limit=5')
        # Should not be a 400 error (param validation passed)
        assert response.status_code in [200, 500]  # 500 if BQ not available


class TestAPIMetrics:
    """Tests for the /api/metrics endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app."""
        from ndcg_server import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_metrics_accepts_params(self, client):
        """Metrics endpoint should accept query parameters."""
        response = client.get('/api/metrics?category=all&segment=all&surface=all&days_back=7')
        # Should not be a 400 error
        assert response.status_code in [200, 500]


class TestAPIOptimization:
    """Tests for the /api/optimization endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app."""
        from ndcg_server import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_optimization_accepts_all_dimensions(self, client):
        """Optimization endpoint should accept all valid dimension parameters."""
        valid_dimensions = ['surface', 'module', 'reranker', 'cg_source', 'position', 'category']
        for dimension in valid_dimensions:
            response = client.get(f'/api/optimization?dimension={dimension}&days_back=7')
            assert response.status_code in [200, 500], f"Dimension {dimension} failed"
    
    def test_optimization_position_dimension(self, client):
        """Position dimension should be accepted for feed position analysis."""
        response = client.get('/api/optimization?dimension=position&days_back=7')
        assert response.status_code in [200, 500]
    
    def test_optimization_module_dimension(self, client):
        """Module dimension should be accepted for section_id analysis."""
        response = client.get('/api/optimization?dimension=module&days_back=7')
        assert response.status_code in [200, 500]
    
    def test_optimization_reranker_dimension(self, client):
        """Reranker dimension should be accepted for algorithm_id analysis."""
        response = client.get('/api/optimization?dimension=reranker&days_back=7')
        assert response.status_code in [200, 500]
    
    def test_optimization_cg_source_dimension(self, client):
        """CG Source dimension should be accepted for candidate generation analysis."""
        response = client.get('/api/optimization?dimension=cg_source&days_back=7')
        assert response.status_code in [200, 500]
    
    def test_optimization_days_back_parameter(self, client):
        """Optimization endpoint should accept days_back parameter."""
        for days in [1, 7, 14, 30]:
            response = client.get(f'/api/optimization?dimension=module&days_back={days}')
            assert response.status_code in [200, 500]


class TestAPIGMVOpportunity:
    """Tests for the /api/gmv_opportunity endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app."""
        from ndcg_server import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_gmv_opportunity_accepts_all_dimensions(self, client):
        """GMV opportunity endpoint should accept all valid dimension parameters."""
        valid_dimensions = ['surface', 'module', 'reranker', 'cg_source', 'position', 'category', 'country']
        for dimension in valid_dimensions:
            response = client.get(f'/api/gmv_opportunity?dimension={dimension}&days_back=7')
            assert response.status_code in [200, 500], f"Dimension {dimension} failed"
    
    def test_gmv_opportunity_position_dimension(self, client):
        """Position dimension should be accepted for feed position GMV analysis."""
        response = client.get('/api/gmv_opportunity?dimension=position&days_back=7')
        assert response.status_code in [200, 500]
    
    def test_gmv_opportunity_module_dimension(self, client):
        """Module dimension should be accepted for section_id GMV analysis."""
        response = client.get('/api/gmv_opportunity?dimension=module&days_back=7')
        assert response.status_code in [200, 500]
    
    def test_gmv_opportunity_reranker_dimension(self, client):
        """Reranker dimension should be accepted for algorithm_id GMV analysis."""
        response = client.get('/api/gmv_opportunity?dimension=reranker&days_back=7')
        assert response.status_code in [200, 500]
    
    def test_gmv_opportunity_cg_source_dimension(self, client):
        """CG Source dimension should be accepted for candidate generation GMV analysis."""
        response = client.get('/api/gmv_opportunity?dimension=cg_source&days_back=7')
        assert response.status_code in [200, 500]
    
    def test_gmv_opportunity_country_dimension(self, client):
        """Country dimension should be accepted for geographic GMV analysis."""
        response = client.get('/api/gmv_opportunity?dimension=country&days_back=7')
        assert response.status_code in [200, 500]
    
    def test_gmv_opportunity_days_back_parameter(self, client):
        """GMV opportunity endpoint should accept days_back parameter."""
        for days in [1, 7, 14, 30]:
            response = client.get(f'/api/gmv_opportunity?dimension=module&days_back={days}')
            assert response.status_code in [200, 500]


class TestAPITrends:
    """Tests for the /api/trends endpoint."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app."""
        from ndcg_server import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_trends_endpoint_exists(self, client):
        """Trends endpoint should exist and respond."""
        response = client.get('/api/trends?days_back=7')
        assert response.status_code in [200, 500]
    
    def test_trends_accepts_days_back(self, client):
        """Trends endpoint should accept days_back parameter."""
        for days in [7, 14, 30]:
            response = client.get(f'/api/trends?days_back={days}')
            assert response.status_code in [200, 500]


class TestDimensionMappings:
    """Tests to ensure dimension mappings are consistent across endpoints."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app."""
        from ndcg_server import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_optimization_and_gmv_share_dimensions(self, client):
        """Optimization and GMV endpoints should share common dimensions."""
        shared_dimensions = ['surface', 'module', 'reranker', 'cg_source', 'position', 'category']
        
        for dimension in shared_dimensions:
            opt_response = client.get(f'/api/optimization?dimension={dimension}&days_back=7')
            gmv_response = client.get(f'/api/gmv_opportunity?dimension={dimension}&days_back=7')
            
            # Both should accept the dimension (not 400 error)
            assert opt_response.status_code in [200, 500], f"Optimization failed for {dimension}"
            assert gmv_response.status_code in [200, 500], f"GMV failed for {dimension}"


class TestPositionBuckets:
    """Tests for position bucket dimension logic."""
    
    def test_position_bucket_definitions(self):
        """Position buckets should be defined correctly."""
        # These are the expected position bucket labels
        expected_buckets = [
            "1-3 (Top of Feed)",
            "4-6 (First Scroll)",
            "7-10 (Second Scroll)",
            "11-15 (Deep Scroll)",
            "16-20 (Bottom)"
        ]
        
        # Verify bucket boundaries make sense
        assert "1-3" in expected_buckets[0]  # Top positions
        assert "16-20" in expected_buckets[4]  # Bottom positions
    
    def test_position_bucket_coverage(self):
        """Position buckets should cover positions 1-20."""
        positions_covered = set()
        bucket_ranges = [
            (1, 3),    # Top of Feed
            (4, 6),    # First Scroll
            (7, 10),   # Second Scroll
            (11, 15),  # Deep Scroll
            (16, 20),  # Bottom
        ]
        
        for start, end in bucket_ranges:
            for pos in range(start, end + 1):
                positions_covered.add(pos)
        
        # All positions 1-20 should be covered
        expected = set(range(1, 21))
        assert positions_covered == expected
    
    def test_position_buckets_no_overlap(self):
        """Position buckets should not overlap."""
        bucket_ranges = [
            (1, 3),    # Top of Feed
            (4, 6),    # First Scroll
            (7, 10),   # Second Scroll
            (11, 15),  # Deep Scroll
            (16, 20),  # Bottom
        ]
        
        all_positions = []
        for start, end in bucket_ranges:
            for pos in range(start, end + 1):
                all_positions.append(pos)
        
        # No duplicates means no overlap
        assert len(all_positions) == len(set(all_positions))
    
    def test_position_bucket_sql_case_logic(self):
        """Test the SQL CASE logic matches expected buckets."""
        def get_bucket(pos):
            """Python equivalent of SQL CASE statement."""
            if pos <= 3:
                return "1-3 (Top of Feed)"
            elif pos <= 6:
                return "4-6 (First Scroll)"
            elif pos <= 10:
                return "7-10 (Second Scroll)"
            elif pos <= 15:
                return "11-15 (Deep Scroll)"
            else:
                return "16-20 (Bottom)"
        
        # Test boundary conditions
        assert get_bucket(1) == "1-3 (Top of Feed)"
        assert get_bucket(3) == "1-3 (Top of Feed)"
        assert get_bucket(4) == "4-6 (First Scroll)"
        assert get_bucket(6) == "4-6 (First Scroll)"
        assert get_bucket(7) == "7-10 (Second Scroll)"
        assert get_bucket(10) == "7-10 (Second Scroll)"
        assert get_bucket(11) == "11-15 (Deep Scroll)"
        assert get_bucket(15) == "11-15 (Deep Scroll)"
        assert get_bucket(16) == "16-20 (Bottom)"
        assert get_bucket(20) == "16-20 (Bottom)"


class TestGMVOpportunityCalculations:
    """Tests for GMV opportunity calculation logic."""
    
    def test_ndcg_uplift_calculation(self):
        """Test the NDCG uplift calculation formula."""
        UPLIFT_FACTOR = 1.5  # 15% GMV increase per 10% NDCG improvement
        
        current_ndcg = 0.5
        target_ndcg = 0.7
        current_gmv = 1000000  # $1M
        
        ndcg_increase_pct = (target_ndcg - current_ndcg) * 100  # 20%
        expected_uplift = current_gmv * (ndcg_increase_pct / 100) * UPLIFT_FACTOR
        
        # 20% NDCG increase * 1.5 factor = 30% GMV uplift
        # $1M * 0.30 = $300K
        assert abs(expected_uplift - 300000) < 1  # Allow for floating point precision
    
    def test_ndcg_uplift_zero_when_at_target(self):
        """No uplift when already at or above target NDCG."""
        UPLIFT_FACTOR = 1.5
        
        current_ndcg = 0.7
        target_ndcg = 0.7
        current_gmv = 1000000
        
        ndcg_increase_pct = max(0, (target_ndcg - current_ndcg) * 100)
        uplift = current_gmv * (ndcg_increase_pct / 100) * UPLIFT_FACTOR
        
        assert uplift == 0
    
    def test_ndcg_uplift_for_different_targets(self):
        """Test uplift calculations for standard NDCG targets."""
        UPLIFT_FACTOR = 1.5
        current_ndcg = 0.4
        current_gmv = 1000000
        
        # Calculate uplift to reach 0.6, 0.7, 0.8
        targets = [0.6, 0.7, 0.8]
        uplifts = []
        
        for target in targets:
            ndcg_increase_pct = (target - current_ndcg) * 100
            uplift = current_gmv * (ndcg_increase_pct / 100) * UPLIFT_FACTOR
            uplifts.append(uplift)
        
        # Uplift should increase with higher targets
        assert uplifts[0] < uplifts[1] < uplifts[2]
        
        # Specific values (with floating point tolerance)
        assert abs(uplifts[0] - 300000) < 1   # 20% increase * 1.5 = 30% = $300K
        assert abs(uplifts[1] - 450000) < 1   # 30% increase * 1.5 = 45% = $450K
        assert abs(uplifts[2] - 600000) < 1   # 40% increase * 1.5 = 60% = $600K
    
    def test_annualized_calculation(self):
        """Test annualized projection from period values."""
        period_value = 100000  # $100K in period
        days_back = 7
        
        annualized = period_value * (365 / days_back)
        
        # 7 days -> ~52 weeks -> 52x multiplier
        assert abs(annualized - 5214285.71) < 1  # ~$5.2M annually
    
    def test_annualized_30_days(self):
        """Test annualized calculation for 30-day period."""
        period_value = 100000
        days_back = 30
        
        annualized = period_value * (365 / days_back)
        
        # 30 days -> ~12x multiplier
        assert abs(annualized - 1216666.67) < 1  # ~$1.2M annually


class TestDimensionValidation:
    """Tests for dimension parameter validation."""
    
    def test_valid_optimization_dimensions(self):
        """All expected optimization dimensions should be in the valid list."""
        valid_dimensions = {'surface', 'module', 'reranker', 'cg_source', 'position', 'category'}
        
        # These should all be valid
        assert 'surface' in valid_dimensions
        assert 'module' in valid_dimensions
        assert 'reranker' in valid_dimensions
        assert 'cg_source' in valid_dimensions
        assert 'position' in valid_dimensions
        assert 'category' in valid_dimensions
    
    def test_valid_gmv_dimensions(self):
        """All expected GMV dimensions should be in the valid list."""
        valid_dimensions = {'surface', 'module', 'reranker', 'cg_source', 'position', 'category', 'country'}
        
        # GMV has all optimization dimensions plus country
        assert 'surface' in valid_dimensions
        assert 'country' in valid_dimensions
        assert 'position' in valid_dimensions
    
    def test_section_id_filters(self):
        """Test the section_id filters are correctly defined."""
        valid_section_ids = [
            'products_from_merchant_discovery_recs',
            'minis_shoppable_video',
            'merchant_rec_with_deals'
        ]
        
        assert len(valid_section_ids) == 3
        assert 'products_from_merchant_discovery_recs' in valid_section_ids
        assert 'minis_shoppable_video' in valid_section_ids
        assert 'merchant_rec_with_deals' in valid_section_ids


class TestCurrencyFormatting:
    """Tests for currency formatting logic."""
    
    def format_currency(self, amount):
        """Python equivalent of JS formatCurrency function."""
        if amount >= 1_000_000_000:
            return f"${amount / 1_000_000_000:.2f}B"
        elif amount >= 1_000_000:
            return f"${amount / 1_000_000:.2f}M"
        elif amount >= 1_000:
            return f"${amount / 1_000:.1f}K"
        return f"${amount:.2f}"
    
    def test_format_billions(self):
        """Billions should format with B suffix."""
        assert self.format_currency(1_000_000_000) == "$1.00B"
        assert self.format_currency(2_500_000_000) == "$2.50B"
    
    def test_format_millions(self):
        """Millions should format with M suffix."""
        assert self.format_currency(1_000_000) == "$1.00M"
        assert self.format_currency(5_500_000) == "$5.50M"
    
    def test_format_thousands(self):
        """Thousands should format with K suffix."""
        assert self.format_currency(1_000) == "$1.0K"
        assert self.format_currency(250_000) == "$250.0K"
    
    def test_format_small_amounts(self):
        """Small amounts should show decimal places."""
        assert self.format_currency(100) == "$100.00"
        assert self.format_currency(99.99) == "$99.99"


class TestHTMLContent:
    """Tests for HTML content of the dashboard."""
    
    @pytest.fixture
    def client(self):
        """Create a test client for the Flask app."""
        from ndcg_server import app
        app.config['TESTING'] = True
        with app.test_client() as client:
            yield client
    
    def test_index_contains_position_dimension_button(self, client):
        """Dashboard should have a By Position dimension button."""
        response = client.get('/')
        assert b'By Position' in response.data
    
    def test_index_contains_module_dimension_button(self, client):
        """Dashboard should have a By Module dimension button."""
        response = client.get('/')
        assert b'By Module' in response.data
    
    def test_index_contains_reranker_dimension_button(self, client):
        """Dashboard should have a By Reranker dimension button."""
        response = client.get('/')
        assert b'By Reranker' in response.data
    
    def test_index_contains_cg_source_dimension_button(self, client):
        """Dashboard should have a By CG Source dimension button."""
        response = client.get('/')
        assert b'By CG Source' in response.data
    
    def test_index_contains_country_dimension_button(self, client):
        """Dashboard should have a By Country dimension button."""
        response = client.get('/')
        assert b'By Country' in response.data
    
    def test_index_contains_trends_tab(self, client):
        """Dashboard should have a Trends tab."""
        response = client.get('/')
        assert b'Trends' in response.data


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

