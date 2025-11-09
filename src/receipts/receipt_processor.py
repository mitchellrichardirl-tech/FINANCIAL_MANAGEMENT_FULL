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

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)