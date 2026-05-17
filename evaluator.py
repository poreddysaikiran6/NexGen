import nltk
from nltk.corpus import stopwords
from nltk.tokenize import word_tokenize
from thefuzz import fuzz
import string
import json
import requests
import re
import base64

try:
    nltk.data.find('corpora/stopwords')
except LookupError:
    nltk.download('stopwords')
try:
    nltk.data.find('tokenizers/punkt')
except LookupError:
    nltk.download('punkt')
try:
    nltk.data.find('tokenizers/punkt_tab')
except LookupError:
    nltk.download('punkt_tab')

def extract_keywords(text):
    """
    Extract meaningful keywords from the teacher's text by removing punctuation and stopwords.
    Returns a list of significant words.
    """
    if not text or not isinstance(text, str):
        return []
    text = text.lower()
    
    text = text.translate(str.maketrans('', '', string.punctuation))
    
    words = text.split()

    stop_words = set(stopwords.words('english'))
    custom_stops = {'explain', 'describe', 'what', 'why', 'how', 'is', 'are', 'the', 'a', 'an'}
    stop_words = stop_words.union(custom_stops)
    
    keywords = [w for w in words if w not in stop_words and len(w) > 2]
    
    # Return unique keywords while preserving order roughly
    seen = set()
    unique_keywords = []
    for k in keywords:
        if k not in seen:
            unique_keywords.append(k)
            seen.add(k)
            
    return unique_keywords

def extract_json_from_text(text):
    # Helps safely extract JSON if the LLM wraps it in markdown (e.g. ```json ... ```)
    match = re.search(r'```json\s*(.*?)\s*```', text, re.DOTALL)
    if match:
        text = match.group(1)
    # Also strip out any other markdown
    text = text.strip()
    try:
        return json.loads(text)
    except Exception as e:
        # Fallback to standard regex finding an object
        match = re.search(r'\{.*\}', text, re.DOTALL)
        if match:
            try:
                return json.loads(match.group(0))
            except:
                pass
        raise e

def evaluate_pdf_directly_with_gemini(pdf_path, teacher_text, total_marks, difficulty):
    import os
    API_KEYS = {
        "Gemini": os.environ.get("GEMINI_API_KEY", "")
    }
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEYS['Gemini']}"
    
    try:
        with open(pdf_path, "rb") as pdf_file:
            encoded_pdf = base64.b64encode(pdf_file.read()).decode("utf-8")
            
        system_prompt = f"""You are an expert academic evaluator and OCR transcriptionist.
Your task is to read the attached student answer sheet PDF, transcribe it accurately, and grade it against a teacher's reference key.
Total Marks: {total_marks}
Grading Strictness: {difficulty} (Easy = lenient, Hard = very strict).

You MUST return ONLY a valid JSON object with the following schema. NO Markdown formatting, NO comments.
{{
  "marks": float,
  "matched_keywords": ["concept1", "concept2"],
  "missed_keywords": ["missed1"],
  "feedback": "A short 1-2 sentence feedback.",
  "student_text": "The full transcribed text from the PDF."
}}"""

        user_prompt = f"Teacher Key:\n{teacher_text}"

        payload = {
            "contents": [
                {
                    "parts": [
                        {"text": system_prompt + "\n\n" + user_prompt},
                        {
                            "inlineData": {
                                "mimeType": "application/pdf",
                                "data": encoded_pdf
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
        result_text = data['candidates'][0]['content']['parts'][0]['text']
        
        parsed = extract_json_from_text(result_text)
        
        parsed['total_marks'] = float(total_marks)
        
        if 'student_text' not in parsed:
            parsed['student_text'] = "[Transcribed text was missing from JSON]"
            
        return parsed
        
    except Exception as e:
        print(f"Direct Gemini Evaluation Error: {e}")
        return {
            'marks': 0,
            'total_marks': float(total_marks),
            'matched_keywords': [],
            'missed_keywords': [],
            'feedback': f"Direct Gemini Evaluation Failed: {str(e)}",
            'student_text': "[Evaluation Failed]"
        }

def evaluate_with_llm(student_text, teacher_text, total_marks, difficulty, model):
    system_prompt = f"""You are an expert academic evaluator. 
Your task is to grade a student's answer against a teacher's reference key.
Total Marks: {total_marks}
Grading Strictness: {difficulty} (Easy = lenient, Hard = very strict).

You MUST return ONLY a valid JSON object with the following schema. NO Markdown formatting, NO comments.
{{
  "marks": float,
  "matched_keywords": ["concept1", "concept2"],
  "missed_keywords": ["missed1"],
  "feedback": "A short 1-2 sentence feedback."
}}"""

    user_prompt = f"Teacher Key:\n{teacher_text}\n\nStudent Answer:\n{student_text}"
    
    API_KEYS = {
        "Groq": os.environ.get("GROQ_API_KEY", ""),
        "Gemini": os.environ.get("GEMINI_API_KEY", ""),
        "DeepSeek": os.environ.get("DEEPSEEK_API_KEY", ""),
        "Cerebras": os.environ.get("CEREBRAS_API_KEY", "")
    }

    try:
        if model == "Gemini":
            url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-2.5-flash:generateContent?key={API_KEYS['Gemini']}"
            payload = {
                "contents": [{"parts": [{"text": system_prompt + "\n\n" + user_prompt}]}]
            }
            headers = {"Content-Type": "application/json"}
            response = requests.post(url, json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            result_text = data['candidates'][0]['content']['parts'][0]['text']
            
        elif model in ["Groq", "DeepSeek", "Cerebras"]:
            endpoints = {
                "Groq": "https://api.groq.com/openai/v1/chat/completions",
                "DeepSeek": "https://api.deepseek.com/chat/completions",
                "Cerebras": "https://api.cerebras.ai/v1/chat/completions"
            }
            models_mapping = {
                "Groq": "llama-3.3-70b-versatile",
                "DeepSeek": "deepseek-chat",
                "Cerebras": "llama3.1-8b"
            }
            
            headers = {
                "Authorization": f"Bearer {API_KEYS[model]}",
                "Content-Type": "application/json"
            }
            payload = {
                "model": models_mapping[model],
                "messages": [
                    {"role": "system", "content": system_prompt},
                    {"role": "user", "content": user_prompt}
                ],
                "temperature": 0.2
            }
            # DeepSeek specific check to map to standard endpoint
            if model == "DeepSeek":
                headers["Accept"] = "application/json"
                
            response = requests.post(endpoints[model], json=payload, headers=headers)
            response.raise_for_status()
            data = response.json()
            result_text = data['choices'][0]['message']['content']
        else:
            raise ValueError("Unknown model selected")

        parsed = extract_json_from_text(result_text)
        
        parsed['student_text'] = student_text
        parsed['total_marks'] = float(total_marks)
        return parsed

    except Exception as e:
        print(f"LLM API Error ({model}): {e}")
        return {
            'marks': 0,
            'total_marks': float(total_marks),
            'matched_keywords': [],
            'missed_keywords': [],
            'feedback': f"LLM Evaluation Failed ({model}): {str(e)}",
            'student_text': student_text
        }

def evaluate_student_answer(student_text, teacher_text, total_marks=10, difficulty="Medium", model="NexGen"):
    """
    Evaluates student text against teacher text using fuzzy keyword matching or LLM API.
    """
    if model != "NexGen":
        return evaluate_with_llm(student_text, teacher_text, total_marks, difficulty, model)

    keywords = extract_keywords(teacher_text)
    
    if not keywords:
        # If no keywords found, fallback
        return {
            'marks': 0,
            'total_marks': float(total_marks),
            'matched_keywords': [],
            'missed_keywords': [],
            'feedback': "Teacher provided no scorable text.",
            'student_text': student_text
        }

    # Set thresholds based on difficulty
    if difficulty == "Easy":
        ratio_thresh = 70
        partial_thresh = 75
    elif difficulty == "Hard":
        ratio_thresh = 95
        partial_thresh = 98
    else: # Medium
        ratio_thresh = 85
        partial_thresh = 90

    matched = []
    missed = []
    
    student_lower = student_text.lower()
    student_words = student_lower.split()
    
    for kw in keywords:
        found = False
        if kw in student_words:
            matched.append(kw)
            continue
            
        for word in student_words:
            if fuzz.ratio(kw, word) >= ratio_thresh:
                found = True
                matched.append(f"{kw} (matched as '{word}')")
                break
                
        if not found:
            if fuzz.partial_ratio(kw, student_lower) >= partial_thresh:
                matched.append(kw)
            else:
                missed.append(kw)
                
    clean_matched = [m.split(' (')[0] if ' (' in m else m for m in matched]
    unique_matched = list(set(clean_matched))
    
    score_percentage = len(unique_matched) / len(keywords) if keywords else 0
    marks = round(score_percentage * float(total_marks), 1)
    
    feedback = f"Found {len(unique_matched)} out of {len(keywords)} key concepts."
    if score_percentage == 1.0:
        feedback += " Excellent perfect answer!"
    elif score_percentage > 0.7:
        feedback += " Good grasp of the topic."
    elif score_percentage > 0.4:
        feedback += " Average answer, missed some details."
    else:
        feedback += " Poor answer, missed most key concepts."

    return {
        'marks': marks,
        'total_marks': float(total_marks),
        'matched_keywords': matched,
        'missed_keywords': missed,
        'feedback': feedback,
        'student_text': student_text
    }
