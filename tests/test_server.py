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
    
    def test_optimization_requires_dimension(self, client):
        """Optimization endpoint should accept dimension parameter."""
        for dimension in ['surface', 'segment', 'category']:
            response = client.get(f'/api/optimization?dimension={dimension}&days_back=7')
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
    
    def test_gmv_opportunity_accepts_dimension(self, client):
        """GMV opportunity endpoint should accept dimension parameter."""
        for dimension in ['surface', 'segment', 'category']:
            response = client.get(f'/api/gmv_opportunity?dimension={dimension}&days_back=7')
            assert response.status_code in [200, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

