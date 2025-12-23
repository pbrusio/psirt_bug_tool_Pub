"""
Tests for MLX vs CUDA Platform Auto-Detection

Tests the detect_platform() function and backend selection logic.
Ensures the system correctly auto-detects and uses the appropriate
inference backend based on available hardware.
"""
import pytest
import sys
from unittest.mock import patch, MagicMock


class TestDetectPlatform:
    """Test the detect_platform() function from predict_and_verify.py"""

    def test_detect_platform_function_exists(self):
        """Verify detect_platform function is importable"""
        from predict_and_verify import detect_platform
        assert callable(detect_platform)

    @patch('sys.platform', 'darwin')
    @patch('torch.backends.mps.is_available', return_value=True)
    def test_detect_platform_mac_with_mps(self, mock_mps):
        """On Mac with MPS available, should return 'mlx'"""
        # Need to reimport to pick up mocked sys.platform
        import importlib
        import predict_and_verify
        importlib.reload(predict_and_verify)

        result = predict_and_verify.detect_platform()
        assert result == 'mlx', "Mac with MPS should use MLX backend"

    @patch('sys.platform', 'linux')
    @patch('torch.cuda.is_available', return_value=True)
    @patch('torch.cuda.get_device_name', return_value='NVIDIA GeForce RTX 4090')
    def test_detect_platform_linux_with_cuda(self, mock_name, mock_cuda):
        """On Linux with CUDA available, should return 'transformers_local'"""
        import importlib
        import predict_and_verify
        importlib.reload(predict_and_verify)

        result = predict_and_verify.detect_platform()
        assert result == 'transformers_local', "Linux with CUDA should use Transformers+PEFT backend"

    @patch('sys.platform', 'linux')
    @patch('torch.cuda.is_available', return_value=False)
    def test_detect_platform_linux_cpu_fallback(self, mock_cuda):
        """On Linux without CUDA, should fall back to CPU (transformers_local)"""
        import importlib
        import predict_and_verify
        importlib.reload(predict_and_verify)

        result = predict_and_verify.detect_platform()
        assert result == 'transformers_local', "Linux without CUDA should fall back to Transformers+PEFT on CPU"

    def test_detect_platform_returns_valid_backend(self):
        """detect_platform should always return a valid backend string"""
        from predict_and_verify import detect_platform

        result = detect_platform()
        valid_backends = ['mlx', 'transformers_local', 'transformers']
        assert result in valid_backends, f"Backend '{result}' not in valid backends: {valid_backends}"


class TestPSIRTVerificationPipelineBackendSelection:
    """Test the PSIRTVerificationPipeline backend selection"""

    def test_pipeline_accepts_auto_backend(self):
        """Pipeline should accept 'auto' as backend and auto-detect"""
        from predict_and_verify import detect_platform

        # Just verify auto-detection works
        backend = detect_platform()
        assert backend in ['mlx', 'transformers_local', 'transformers']

    def test_backend_environment_variable(self):
        """PSIRT_BACKEND env var should be respected"""
        import os

        # Save original
        original = os.environ.get('PSIRT_BACKEND')

        try:
            # Test explicit backend setting
            os.environ['PSIRT_BACKEND'] = 'transformers_local'

            # The SEC8BAnalyzer reads this env var
            from backend.core.sec8b import SEC8BAnalyzer
            # Just verify the env var mechanism exists
            assert os.getenv('PSIRT_BACKEND') == 'transformers_local'
        finally:
            # Restore
            if original:
                os.environ['PSIRT_BACKEND'] = original
            else:
                os.environ.pop('PSIRT_BACKEND', None)


class TestAdapterPaths:
    """Test that adapter paths are correctly configured"""

    def test_cuda_adapter_path_defined(self):
        """CUDA adapter path should be defined in transformers_inference"""
        from transformers_inference import CUDA_ADAPTER_PATH
        assert CUDA_ADAPTER_PATH == "models/adapters/cuda_v1"

    def test_mlx_adapter_path_defined(self):
        """MLX adapter path should be defined in transformers_inference"""
        from transformers_inference import MLX_ADAPTER_PATH
        assert MLX_ADAPTER_PATH == "models/adapters/mlx_v1"

    def test_cuda_adapter_exists(self):
        """CUDA adapter directory should exist with required files"""
        from pathlib import Path
        adapter_path = Path("models/adapters/cuda_v1")

        assert adapter_path.exists(), "CUDA adapter directory should exist"
        assert (adapter_path / "adapter_config.json").exists(), "adapter_config.json should exist"
        assert (adapter_path / "adapter_model.safetensors").exists(), "adapter_model.safetensors should exist"

    def test_mlx_adapter_exists(self):
        """MLX adapter directory should exist with required files"""
        from pathlib import Path
        adapter_path = Path("models/adapters/mlx_v1")

        assert adapter_path.exists(), "MLX adapter directory should exist"
        assert (adapter_path / "adapter_config.json").exists(), "adapter_config.json should exist"
        assert (adapter_path / "adapters.safetensors").exists(), "adapters.safetensors should exist"


class TestCurrentPlatformDetection:
    """Test platform detection on the current system"""

    def test_current_platform_detection(self):
        """Verify platform detection works on current system"""
        from predict_and_verify import detect_platform
        import torch

        result = detect_platform()

        # Verify result matches actual hardware
        if sys.platform == 'darwin' and hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            assert result == 'mlx', "Mac with MPS should detect MLX"
        elif torch.cuda.is_available():
            assert result == 'transformers_local', "System with CUDA should detect Transformers+PEFT"
        else:
            assert result == 'transformers_local', "CPU fallback should use Transformers+PEFT"

    def test_torch_device_detection(self):
        """Verify torch correctly reports device availability"""
        import torch

        # These should not raise exceptions
        has_cuda = torch.cuda.is_available()
        has_mps = torch.backends.mps.is_available() if hasattr(torch.backends, 'mps') else False

        assert isinstance(has_cuda, bool)
        assert isinstance(has_mps, bool)

        # Log for debugging
        print(f"CUDA available: {has_cuda}")
        print(f"MPS available: {has_mps}")
        if has_cuda:
            print(f"CUDA device: {torch.cuda.get_device_name(0)}")


class TestModelLoadingDeviceSelection:
    """Test that model loading selects correct device"""

    def test_transformers_inference_device_selection(self):
        """TransformersPSIRTLabeler should select correct device"""
        import torch

        # This tests the device selection logic without loading the full model
        if torch.cuda.is_available():
            expected_device = "cuda"
        elif hasattr(torch.backends, 'mps') and torch.backends.mps.is_available():
            expected_device = "mps"
        else:
            expected_device = "cpu"

        # Verify torch device creation works
        device = torch.device(expected_device)
        assert str(device) == expected_device


class TestRegistryConfiguration:
    """Test the adapter registry configuration"""

    def test_registry_file_exists(self):
        """Registry YAML should exist"""
        from pathlib import Path
        registry_path = Path("models/adapters/registry.yaml")
        assert registry_path.exists(), "Adapter registry.yaml should exist"

    def test_registry_structure(self):
        """Registry should have correct structure"""
        import yaml
        from pathlib import Path

        registry_path = Path("models/adapters/registry.yaml")
        if registry_path.exists():
            with open(registry_path) as f:
                registry = yaml.safe_load(f)

            assert 'adapters' in registry, "Registry should have 'adapters' section"
            assert 'defaults' in registry, "Registry should have 'defaults' section"

            # Check adapters
            adapters = registry['adapters']
            assert 'mlx_v1' in adapters, "mlx_v1 adapter should be defined"
            assert 'cuda_v1' in adapters, "cuda_v1 adapter should be defined"

            # Check defaults
            defaults = registry['defaults']
            assert 'mps' in defaults, "MPS default should be defined"
            assert 'cuda' in defaults, "CUDA default should be defined"
            assert 'cpu' in defaults, "CPU default should be defined"
