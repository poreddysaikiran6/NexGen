import fitz  # PyMuPDF
import os
import tempfile
import logging
import base64
import requests

# Suppress debug logs
logging.getLogger("ppocr").setLevel(logging.WARNING)
os.environ["FLAGS_use_mkldnn"] = "0"
os.environ["KMP_DUPLICATE_LIB_OK"] = "TRUE"

from paddleocr import PaddleOCR

# Initialize local PaddleOCR Client
try:
    ocr = PaddleOCR(use_angle_cls=False, lang='en', enable_mkldnn=False, use_gpu=False, show_log=False)
except Exception as e:
    print(f"Failed to initialize local PaddleOCR: {e}")
    ocr = None

def convert_pdf_to_images(pdf_path):
    """
    Converts a PDF file into a list of image file paths (saved temporarily).
    """
    image_paths = []
    try:
        pdf_document = fitz.open(pdf_path)
        temp_dir = tempfile.mkdtemp()
        
        for page_num in range(len(pdf_document)):
            page = pdf_document[page_num]
            # Use high resolution for OCR
            pix = page.get_pixmap(matrix=fitz.Matrix(2, 2))
            
            img_path = os.path.join(temp_dir, f"page_{page_num + 1}.png")
            pix.save(img_path)
            image_paths.append(img_path)
            
        pdf_document.close()
    except Exception as e:
        print(f"Error converting PDF to images: {e}")
        
    return image_paths

def extract_text_with_gemini(image_paths, job_id=None, progress_callback=None):
    """
    Sends images to the Gemini API and extracts text efficiently over the cloud.
    """
    api_key = os.environ.get("GEMINI_API_KEY", "")
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={api_key}"
    
    full_text = []
    total = len(image_paths)
    
    for i, img_path in enumerate(image_paths):
        if progress_callback:
            progress_callback(job_id, f"Performing Gemini OCR: page {i+1} out of {total} done.")
            
        try:
            with open(img_path, "rb") as image_file:
                encoded_image = base64.b64encode(image_file.read()).decode("utf-8")
                
            payload = {
                "contents": [
                    {
                        "parts": [
                            {"text": "Extract all handwriting and printed text from this image perfectly. Maintain the general structure. Provide ONLY the extracted text exactly as written, with no conversational filler, markdown formatting, or explanations."},
                            {
                                "inlineData": {
                                    "mimeType": "image/png",
                                    "data": encoded_image
                                }
                            }
                        ]
                    }
                ]
            }
            
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            
            page_text = data['candidates'][0]['content']['parts'][0]['text']
            full_text.append(page_text.strip())
            
        except Exception as e:
            print(f"Error extracting text with Gemini from {img_path}: {e}")
            full_text.append("[Gemini OCR Error on this page]")
            
    return "\n\n".join(full_text)

def extract_text_from_images(image_paths, job_id=None, progress_callback=None):
    """
    Sends images to the local PaddleOCR model and concatenates the text.
    """
    if not ocr:
        return "OCR Client is not initialized."

    full_text = []
    total = len(image_paths)
    
    for i, img_path in enumerate(image_paths):
        if progress_callback:
            progress_callback(job_id, f"Performing Paddle OCR extraction: page {i+1} out of {total} done.")
            
        try:
            result = ocr.ocr(img_path, cls=False)
            
            page_text = ""
            if result and result[0]:
                for line in result[0]:
                    text = line[1][0]
                    page_text += text + " "
                    
            full_text.append(page_text.strip())
        except Exception as e:
            print(f"Error extracting text from {img_path}: {e}")
            full_text.append("[OCR Error on this page]")
            
    return "\n\n".join(full_text)

def process_student_pdf(pdf_path, job_id=None, progress_callback=None, ocr_engine="Paddle OCR"):
    """
    High-level function: PDF -> Images -> Text.
    Returns the concatenated student text and cleans up temp images.
    """
    if progress_callback:
        progress_callback(job_id, "Converting PDF to images...")
        
    image_paths = convert_pdf_to_images(pdf_path)
    
    if ocr_engine == "Gemini OCR":
        student_text = extract_text_with_gemini(image_paths, job_id, progress_callback)
    else:
        student_text = extract_text_from_images(image_paths, job_id, progress_callback)
    
    if progress_callback:
        progress_callback(job_id, "Cleaning up temporary files...")
        
    # Cleanup temporary images
    for img in image_paths:
        try:
            os.remove(img)
        except:
            pass

    try:
        temp_dir = os.path.dirname(image_paths[0])
        os.rmdir(temp_dir)
    except:
        pass
        
    return student_text
