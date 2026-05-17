import os
from dotenv import load_dotenv
load_dotenv()
import uuid
import threading
from authlib.integrations.flask_client import OAuth
from flask import Flask, request, jsonify, render_template, redirect, session, url_for
from gradio_client import Client, handle_file
from werkzeug.utils import secure_filename

app = Flask(__name__)
# Initialize Hugging Face Gradio Client for PaddleOCR-VL-1.5
client = Client("PaddlePaddle/PaddleOCR-VL-1.5_Online_Demo")

# Configure upload folder
UPLOAD_FOLDER = os.path.join(os.path.dirname(os.path.abspath(__file__)), 'uploads')
app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.secret_key = os.urandom(24)

os.makedirs(UPLOAD_FOLDER, exist_ok=True)

# OAuth Setup
oauth = OAuth(app)
google = oauth.register(
    name='google',
    client_id=os.getenv("GOOGLE_CLIENT_ID", "YOUR_CLIENT_ID_HERE"),
    client_secret=os.getenv("GOOGLE_CLIENT_SECRET", "YOUR_CLIENT_SECRET_HERE"),
    access_token_url='https://accounts.google.com/o/oauth2/token',
    access_token_params=None,
    authorize_url='https://accounts.google.com/o/oauth2/auth',
    authorize_params=None,
    api_base_url='https://www.googleapis.com/oauth2/v1/',
    client_kwargs={'scope': 'openid email profile'},
    server_metadata_url='https://accounts.google.com/.well-known/openid-configuration'
)

# Dictionary to store background job statuses
jobs = {}

@app.route('/api/evaluate', methods=['POST'])
def evaluate_pdf():
    files = request.files.getlist('files')
    if not files or all(f.filename == '' for f in files):
        return jsonify({'error': 'No files selected for uploading (Make sure to upload PDFs)'}), 400
        
    teacher_answer = request.form.get('teacher_answer', '').strip()
    total_marks_str = request.form.get('total_marks', '10')
    difficulty = request.form.get('difficulty', 'Medium')
    evaluation_model = request.form.get('evaluation_model', 'NexGen')
    ocr_engine = request.form.get('ocr_engine', 'Paddle OCR')
    
    if not teacher_answer:
        return jsonify({'error': 'Teacher reference answer is required for grading.'}), 400
        
    try:
        total_marks = float(total_marks_str)
    except ValueError:
        total_marks = 10.0
        
    valid_files = [f for f in files if f.filename.lower().endswith('.pdf')]
    if not valid_files:
        return jsonify({'error': 'Invalid file format. Please upload PDF files.'}), 400
        
    job_id = str(uuid.uuid4())
    jobs[job_id] = {'status': 'processing', 'progress': 'Initializing...', 'result': [], 'error': None}
    
    saved_files = []
    for file in valid_files:
        filename = secure_filename(file.filename)
        filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
        file.save(filepath)
        saved_files.append({"path": filepath, "original_name": file.filename})

    def process_job():
        try:
            from pdf_processor import process_student_pdf
            from evaluator import evaluate_student_answer
            
            total_files = len(saved_files)
            for i, sf in enumerate(saved_files):
                current_path = sf["path"]
                original_name = sf["original_name"]
                
                def update_progress(jid, msg):
                    overall_progress = f"Evaluating student {i+1} of {total_files}"
                    jobs[jid]['progress'] = f"{overall_progress} - {msg}"
                    
                if ocr_engine == "Gemini OCR" and evaluation_model == "Gemini":
                    update_progress(job_id, "Fast Track: Reading PDF and evaluating directly with Gemini...")
                    from evaluator import evaluate_pdf_directly_with_gemini
                    evaluation = evaluate_pdf_directly_with_gemini(current_path, teacher_answer, total_marks, difficulty)
                else:
                    student_text = process_student_pdf(current_path, job_id, update_progress, ocr_engine)
                    update_progress(job_id, f"Evaluating answer against teacher key using {evaluation_model}...")
                    evaluation = evaluate_student_answer(student_text, teacher_answer, total_marks, difficulty, evaluation_model)
                
                # Store filename and append to array
                evaluation['filename'] = original_name
                jobs[job_id]['result'].append(evaluation)
                
                # Immediate cleanup
                if os.path.exists(current_path):
                    try: os.remove(current_path)
                    except: pass
                    
            jobs[job_id]['status'] = 'completed'
            jobs[job_id]['progress'] = "All evaluations completed!"
            
        except Exception as e:
            jobs[job_id]['status'] = 'error'
            jobs[job_id]['error'] = str(e)
        finally:
            for sf in saved_files:
                if os.path.exists(sf["path"]):
                    try: os.remove(sf["path"])
                    except: pass
    
    threading.Thread(target=process_job).start()
    
    return jsonify({
        'success': True,
        'job_id': job_id
    })

@app.route('/api/status/<job_id>', methods=['GET'])
def get_status(job_id):
    if job_id not in jobs:
        return jsonify({'error': 'Job not found'}), 404
    return jsonify(jobs[job_id])

@app.route('/login')
def login_page():
    if 'user' in session:
        return redirect('/')
    return render_template('login.html')

@app.route('/login/google')
def login_google():
    client_id = google.client_id
    if client_id == "YOUR_CLIENT_ID_HERE" or not client_id:
        # Mock login if credentials are not configured yet
        session['user'] = {
            "given_name": "Demo",
            "picture": "https://ui-avatars.com/api/?name=Demo+Teacher&background=6366f1&color=fff",
            "email": "demo@example.com"
        }
        return redirect('/')
        
    redirect_uri = url_for('authorize', _external=True)
    return google.authorize_redirect(redirect_uri)

@app.route('/authorize')
def authorize():
    token = google.authorize_access_token()
    resp = google.get('userinfo')
    user_info = resp.json()
    session['user'] = user_info
    return redirect('/')

@app.route('/logout')
def logout():
    session.pop('user', None)
    return redirect('/login')

@app.route('/')
def index():
    if 'user' not in session:
        return redirect(url_for('login_page'))
    return render_template('index.html', user=session['user'])

if __name__ == '__main__':
    app.run(debug=True, use_reloader=False, port=5000)
