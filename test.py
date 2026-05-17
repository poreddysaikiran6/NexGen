import os
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"
from paddleocr import PaddleOCR
ocr = PaddleOCR(use_angle_cls=False, lang='en', enable_mkldnn=False, use_gpu=False)
result = ocr.ocr('c:\\MPS\\PaddleOCR 10-03-26\\handwriting-app\\test_image.png', cls=False)
print(result)
