"""
Unit tests for NDCG calculation functions.

Tests cover:
- Relevance scoring (binary and graded)
- DCG calculation
- IDCG calculation  
- NDCG calculation
- Ideal ranking generation
"""

import math
import pytest
import sys
from pathlib import Path

# Add tools directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent / "tools"))

from ndcg_visualizer import (
    get_relevance_score,
    calculate_dcg,
    calculate_idcg,
    calculate_ndcg,
    get_ideal_ranking,
)


class TestRelevanceScore:
    """Tests for get_relevance_score function."""
    
    def test_purchased_graded(self):
        """Purchased item should have relevance 4 in graded scoring."""
        item = {"purchased": True, "clicked": True}
        assert get_relevance_score(item, graded=True) == 4
    
    def test_clicked_only_graded(self):
        """Clicked (not purchased) item should have relevance 2 in graded scoring."""
        item = {"purchased": False, "clicked": True}
        assert get_relevance_score(item, graded=True) == 2
    
    def test_no_interaction_graded(self):
        """No interaction item should have relevance 0 in graded scoring."""
        item = {"purchased": False, "clicked": False}
        assert get_relevance_score(item, graded=True) == 0
    
    def test_purchased_binary(self):
        """Purchased item should have relevance 1 in binary scoring."""
        item = {"purchased": True, "clicked": True}
        assert get_relevance_score(item, graded=False) == 1
    
    def test_clicked_only_binary(self):
        """Clicked (not purchased) item should have relevance 0 in binary scoring."""
        item = {"purchased": False, "clicked": True}
        assert get_relevance_score(item, graded=False) == 0
    
    def test_no_interaction_binary(self):
        """No interaction item should have relevance 0 in binary scoring."""
        item = {"purchased": False, "clicked": False}
        assert get_relevance_score(item, graded=False) == 0


class TestDCGCalculation:
    """Tests for calculate_dcg function."""
    
    def test_dcg_perfect_ranking(self):
        """DCG when purchased item is at position 1."""
        items = [
            {"purchased": True, "clicked": True},   # rel=4, pos=1 -> 4/log2(2) = 4.0
            {"purchased": False, "clicked": False}, # rel=0, pos=2 -> 0
            {"purchased": False, "clicked": False}, # rel=0, pos=3 -> 0
        ]
        dcg = calculate_dcg(items, k=3, graded=True)
        expected = 4 / math.log2(2)  # 4.0
        assert abs(dcg - expected) < 0.001
    
    def test_dcg_mixed_items(self):
        """DCG with mix of purchased, clicked, and no interaction items."""
        items = [
            {"purchased": False, "clicked": False}, # rel=0, pos=1 -> 0
            {"purchased": True, "clicked": True},   # rel=4, pos=2 -> 4/log2(3) ≈ 2.52
            {"purchased": False, "clicked": True},  # rel=2, pos=3 -> 2/log2(4) = 1.0
        ]
        dcg = calculate_dcg(items, k=3, graded=True)
        expected = 0 + 4/math.log2(3) + 2/math.log2(4)
        assert abs(dcg - expected) < 0.001
    
    def test_dcg_empty_list(self):
        """DCG of empty list should be 0."""
        assert calculate_dcg([], k=10, graded=True) == 0.0
    
    def test_dcg_all_zeros(self):
        """DCG when no items have relevance."""
        items = [
            {"purchased": False, "clicked": False},
            {"purchased": False, "clicked": False},
        ]
        assert calculate_dcg(items, k=2, graded=True) == 0.0
    
    def test_dcg_respects_k(self):
        """DCG should only consider first k items."""
        items = [
            {"purchased": True, "clicked": True},   # rel=4, pos=1
            {"purchased": True, "clicked": True},   # rel=4, pos=2 (excluded if k=1)
        ]
        dcg_k1 = calculate_dcg(items, k=1, graded=True)
        dcg_k2 = calculate_dcg(items, k=2, graded=True)
        assert dcg_k1 < dcg_k2  # k=2 should include more


class TestIDCGCalculation:
    """Tests for calculate_idcg function."""
    
    def test_idcg_sorts_by_relevance(self):
        """IDCG should sort items by relevance (purchased first)."""
        items = [
            {"purchased": False, "clicked": False}, # rel=0
            {"purchased": True, "clicked": True},   # rel=4
            {"purchased": False, "clicked": True},  # rel=2
        ]
        idcg = calculate_idcg(items, k=3, graded=True)
        # Ideal order: rel=4 at pos 1, rel=2 at pos 2, rel=0 at pos 3
        expected = 4/math.log2(2) + 2/math.log2(3) + 0
        assert abs(idcg - expected) < 0.001
    
    def test_idcg_equals_dcg_for_perfect_ranking(self):
        """IDCG should equal DCG when items are already perfectly ranked."""
        items = [
            {"purchased": True, "clicked": True},   # rel=4
            {"purchased": False, "clicked": True},  # rel=2
            {"purchased": False, "clicked": False}, # rel=0
        ]
        dcg = calculate_dcg(items, k=3, graded=True)
        idcg = calculate_idcg(items, k=3, graded=True)
        assert abs(dcg - idcg) < 0.001


class TestNDCGCalculation:
    """Tests for calculate_ndcg function."""
    
    def test_ndcg_perfect_ranking(self):
        """NDCG should be 1.0 for perfect ranking."""
        items = [
            {"purchased": True, "clicked": True},   # rel=4
            {"purchased": False, "clicked": True},  # rel=2
            {"purchased": False, "clicked": False}, # rel=0
        ]
        ndcg = calculate_ndcg(items, k=3, graded=True)
        assert abs(ndcg - 1.0) < 0.001
    
    def test_ndcg_worst_ranking(self):
        """NDCG should be < 1.0 when purchased item is at bottom."""
        items = [
            {"purchased": False, "clicked": False}, # rel=0
            {"purchased": False, "clicked": False}, # rel=0
            {"purchased": True, "clicked": True},   # rel=4
        ]
        ndcg = calculate_ndcg(items, k=3, graded=True)
        assert ndcg < 1.0
        assert ndcg > 0  # Still some DCG contribution
    
    def test_ndcg_all_zero_relevance(self):
        """NDCG should be 0 when no items have relevance."""
        items = [
            {"purchased": False, "clicked": False},
            {"purchased": False, "clicked": False},
        ]
        ndcg = calculate_ndcg(items, k=2, graded=True)
        assert ndcg == 0.0
    
    def test_ndcg_range(self):
        """NDCG should always be between 0 and 1."""
        items = [
            {"purchased": False, "clicked": True},
            {"purchased": True, "clicked": True},
            {"purchased": False, "clicked": False},
        ]
        ndcg = calculate_ndcg(items, k=3, graded=True)
        assert 0.0 <= ndcg <= 1.0
    
    def test_ndcg_single_item(self):
        """NDCG with single relevant item at position 1 should be 1.0."""
        items = [{"purchased": True, "clicked": True}]
        ndcg = calculate_ndcg(items, k=1, graded=True)
        assert abs(ndcg - 1.0) < 0.001


class TestIdealRanking:
    """Tests for get_ideal_ranking function."""
    
    def test_ideal_ranking_orders_correctly(self):
        """Ideal ranking should put purchased items first, then clicked, then none."""
        items = [
            {"id": 1, "purchased": False, "clicked": False},
            {"id": 2, "purchased": True, "clicked": True},
            {"id": 3, "purchased": False, "clicked": True},
        ]
        ideal = get_ideal_ranking(items, graded=True)
        
        # Should be ordered: purchased (id=2), clicked (id=3), none (id=1)
        assert ideal[0]["id"] == 2  # purchased (rel=4)
        assert ideal[1]["id"] == 3  # clicked (rel=2)
        assert ideal[2]["id"] == 1  # none (rel=0)
    
    def test_ideal_ranking_preserves_items(self):
        """Ideal ranking should not modify or lose any items."""
        items = [
            {"id": 1, "purchased": False, "clicked": False},
            {"id": 2, "purchased": True, "clicked": True},
        ]
        ideal = get_ideal_ranking(items, graded=True)
        
        assert len(ideal) == len(items)
        original_ids = {item["id"] for item in items}
        ideal_ids = {item["id"] for item in ideal}
        assert original_ids == ideal_ids


class TestEdgeCases:
    """Edge case tests."""
    
    def test_single_purchased_item(self):
        """Single purchased item should have NDCG of 1.0."""
        items = [{"purchased": True, "clicked": True}]
        ndcg = calculate_ndcg(items, k=10, graded=True)
        assert abs(ndcg - 1.0) < 0.001
    
    def test_k_larger_than_list(self):
        """k larger than item list should work correctly."""
        items = [
            {"purchased": True, "clicked": True},
            {"purchased": False, "clicked": False},
        ]
        ndcg = calculate_ndcg(items, k=100, graded=True)
        assert 0.0 <= ndcg <= 1.0
    
    def test_binary_vs_graded_scoring(self):
        """Binary scoring should only consider purchases."""
        items = [
            {"purchased": False, "clicked": True},  # graded=2, binary=0
            {"purchased": True, "clicked": True},   # graded=4, binary=1
        ]
        
        ndcg_graded = calculate_ndcg(items, k=2, graded=True)
        ndcg_binary = calculate_ndcg(items, k=2, graded=False)
        
        # With graded, first item has some relevance
        # With binary, first item has no relevance
        # So rankings differ in effectiveness
        assert ndcg_graded != ndcg_binary


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

