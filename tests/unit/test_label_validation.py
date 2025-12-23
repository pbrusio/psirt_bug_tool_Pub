"""
Unit tests for label validation against taxonomy
"""
import pytest


@pytest.mark.unit
class TestLabelValidation:
    """Test label validation logic"""

    def test_valid_labels(self, sample_taxonomy):
        """Test that valid labels pass validation"""
        valid_labels_list = [f["label"] for f in sample_taxonomy]

        predicted_labels = ["APP_IOx", "MGMT_SSH_HTTP"]

        # All predicted labels should be in taxonomy
        for label in predicted_labels:
            assert label in valid_labels_list

    def test_invalid_labels_filtered(self, sample_taxonomy):
        """Test that invalid labels are filtered out"""
        valid_labels_set = {f["label"] for f in sample_taxonomy}

        predicted_labels = ["APP_IOx", "INVALID_LABEL", "MGMT_SSH_HTTP", "FAKE_LABEL"]

        # Filter to valid only
        filtered_labels = [l for l in predicted_labels if l in valid_labels_set]

        assert len(filtered_labels) == 2
        assert "APP_IOx" in filtered_labels
        assert "MGMT_SSH_HTTP" in filtered_labels
        assert "INVALID_LABEL" not in filtered_labels
        assert "FAKE_LABEL" not in filtered_labels

    def test_empty_labels(self, sample_taxonomy):
        """Test handling of empty label list"""
        valid_labels_set = {f["label"] for f in sample_taxonomy}

        predicted_labels = []
        filtered_labels = [l for l in predicted_labels if l in valid_labels_set]

        assert len(filtered_labels) == 0

    def test_duplicate_labels(self, sample_taxonomy):
        """Test that duplicate labels are deduplicated"""
        predicted_labels = ["APP_IOx", "APP_IOx", "MGMT_SSH_HTTP"]

        # Remove duplicates
        unique_labels = list(set(predicted_labels))

        assert len(unique_labels) == 2
        assert "APP_IOx" in unique_labels
        assert "MGMT_SSH_HTTP" in unique_labels

    def test_case_sensitivity(self, sample_taxonomy):
        """Test that label matching is case-sensitive"""
        valid_labels_set = {f["label"] for f in sample_taxonomy}

        # Lowercase version shouldn't match
        predicted_labels = ["app_iox", "APP_IOx"]

        filtered_labels = [l for l in predicted_labels if l in valid_labels_set]

        # Only exact match should pass
        assert len(filtered_labels) == 1
        assert "APP_IOx" in filtered_labels
        assert "app_iox" not in filtered_labels


@pytest.mark.unit
class TestLabelEnrichment:
    """Test enrichment of labels with metadata"""

    def test_enrich_with_config_regex(self, sample_taxonomy):
        """Test adding config regex to labels"""
        label_index = {f["label"]: f for f in sample_taxonomy}

        predicted_labels = ["APP_IOx", "MGMT_SSH_HTTP"]

        # Enrich each label
        enriched = []
        for label in predicted_labels:
            feature = label_index.get(label)
            if feature:
                enriched.append({
                    "label": label,
                    "config_regex": feature["presence"]["config_regex"]
                })

        assert len(enriched) == 2
        assert enriched[0]["label"] == "APP_IOx"
        assert "^iox$" in enriched[0]["config_regex"]

    def test_enrich_with_show_commands(self, sample_taxonomy):
        """Test adding show commands to labels"""
        label_index = {f["label"]: f for f in sample_taxonomy}

        predicted_labels = ["APP_IOx", "MGMT_SSH_HTTP"]

        enriched = []
        for label in predicted_labels:
            feature = label_index.get(label)
            if feature:
                enriched.append({
                    "label": label,
                    "show_cmds": feature["presence"]["show_cmds"]
                })

        assert len(enriched) == 2
        assert enriched[0]["label"] == "APP_IOx"
        assert "show iox" in enriched[0]["show_cmds"]

    def test_enrich_with_domain(self, sample_taxonomy):
        """Test adding domain to labels"""
        label_index = {f["label"]: f for f in sample_taxonomy}

        predicted_labels = ["APP_IOx", "SEC_CoPP"]

        enriched = []
        for label in predicted_labels:
            feature = label_index.get(label)
            if feature:
                enriched.append({
                    "label": label,
                    "domain": feature["domain"]
                })

        assert len(enriched) == 2
        assert enriched[0]["domain"] == "Application"
        assert enriched[1]["domain"] == "Security"

    def test_enrich_invalid_label(self, sample_taxonomy):
        """Test that invalid labels are skipped during enrichment"""
        label_index = {f["label"]: f for f in sample_taxonomy}

        predicted_labels = ["APP_IOx", "INVALID_LABEL"]

        enriched = []
        for label in predicted_labels:
            feature = label_index.get(label)
            if feature:
                enriched.append({
                    "label": label,
                    "config_regex": feature["presence"]["config_regex"]
                })

        # Only valid label should be enriched
        assert len(enriched) == 1
        assert enriched[0]["label"] == "APP_IOx"


@pytest.mark.unit
class TestMaxLabelsPolicy:
    """Test max labels = 3 policy"""

    def test_enforce_max_three_labels(self):
        """Test that only top 3 labels are kept"""
        predicted_labels = ["LABEL1", "LABEL2", "LABEL3", "LABEL4", "LABEL5"]

        # Keep only first 3
        limited_labels = predicted_labels[:3]

        assert len(limited_labels) == 3
        assert limited_labels == ["LABEL1", "LABEL2", "LABEL3"]

    def test_fewer_than_max_labels(self):
        """Test that fewer than 3 labels are allowed"""
        predicted_labels = ["LABEL1", "LABEL2"]

        limited_labels = predicted_labels[:3]

        assert len(limited_labels) == 2

    def test_no_labels(self):
        """Test handling of no labels"""
        predicted_labels = []

        limited_labels = predicted_labels[:3]

        assert len(limited_labels) == 0
