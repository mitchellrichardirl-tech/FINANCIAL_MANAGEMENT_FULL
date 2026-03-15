import cv2
import numpy as np
import pytesseract
from PIL import Image, ImageEnhance, ImageFilter
import pdf2image
import re
from datetime import datetime
import os
from typing import Dict, List, Optional, Tuple
import logging

print("✓ All imports successful!")
print(f"OpenCV version: {cv2.__version__}")
print(f"NumPy version: {np.__version__}")
print(f"Pillow version: {Image.__version__}")
print(f"Tesseract command: {pytesseract.pytesseract.tesseract_cmd}")