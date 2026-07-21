
from src.receipts.engines.paddle_engine import PaddleEngine
import cv2

engine = PaddleEngine(use_gpu=False)
img = cv2.imread("/workspaces/FINANCIAL_MANAGEMENT_FULL/data/uploads/receipt__20260316_072643_44766b5843bb.png")
text = engine.extract_text(img)
print(repr(text[:200]))