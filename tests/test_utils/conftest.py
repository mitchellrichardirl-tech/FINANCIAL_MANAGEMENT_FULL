import pytest
import logging
import numpy as np

# Disable logging during tests to reduce noise
@pytest.fixture(autouse=True)
def disable_logging():
    logging.disable(logging.CRITICAL)
    yield
    logging.disable(logging.NOTSET)

# Set random seed for reproducibility
@pytest.fixture(autouse=True)
def set_random_seed():
    np.random.seed(42)
    yield

# Mark slow tests
def pytest_configure(config):
    config.addinivalue_line(
        "markers", "integration: mark test as an integration test"
    )

# Image fixtures
@pytest.fixture
def sample_gray_image():
    """Create a sample grayscale image with some structure."""
    image = np.ones((100, 100), dtype=np.uint8) * 128
    # Add some rectangles for structure
    image[25:75, 25:75] = 150
    image[40:60, 40:60] = 100
    return image

@pytest.fixture
def uniform_gray_image():
    """Create a perfectly uniform grayscale image."""
    return np.ones((100, 100), dtype=np.uint8) * 128

@pytest.fixture
def noisy_gray_image():
    """Create a grayscale image with noise."""
    base = np.ones((100, 100), dtype=np.uint8) * 128
    noise = np.random.randint(-20, 20, (100, 100), dtype=np.int16)
    return np.clip(base.astype(np.int16) + noise, 0, 255).astype(np.uint8)

@pytest.fixture
def sample_color_image():
    """Create a sample color image (BGR)."""
    return np.ones((100, 100, 3), dtype=np.uint8) * 128

@pytest.fixture
def sample_rgba_image():
    """Create a sample RGBA image."""
    return np.ones((100, 100, 4), dtype=np.uint8) * 128

@pytest.fixture
def large_image():
    """Create a large image that exceeds max dimension."""
    return np.ones((2000, 2000, 3), dtype=np.uint8) * 128

@pytest.fixture
def document_like_image():
    """Create an image that looks like a document."""
    img = np.ones((800, 600), dtype=np.uint8) * 255  # White background
    # Add some "text" (dark rectangles)
    img[100:120, 50:500] = 50
    img[150:170, 50:400] = 50
    img[200:220, 50:450] = 50
    return img