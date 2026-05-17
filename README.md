# NexGen Evaluation: Comprehensive Technical Reference

NexGen Evaluation is an advanced, AI-driven educational tool that automates the grading of handwritten student answer sheets. It functions as a complete, locally-hosted pipeline bridging Optical Character Recognition (OCR) and Natural Language Processing (NLP). 

This document serves as an exhaustive technical breakdown of the project architecture, data flow, and algorithmic logic.

---

## 📁 Project Directory Structure

```text
handwriting-app/
├── app.py                 # Core routing, server initialization, and background thread manager
├── pdf_processor.py       # Computer Vision module handling PDF parsing and PaddleOCR inference
├── evaluator.py           # NLP module handling keyword extraction and Levenshtein distance grading
├── README.md              # This documentation file
├── requirements.txt       # Python dependencies (Flask, NLTK, thefuzz, paddleocr, PyMuPDF, opencv-python)
│
├── static/
│   ├── script.js          # Client-side logic: AJAX polling, FormData handling, DOM manipulation
│   └── style.css          # Client-side styling: Glassmorphism, animations, layout grids
│
├── templates/
│   └── index.html         # The single-page application (SPA) frontend interface
│
└── uploads/               # Temporary directory where in-flight PDF files are queued
```

---

## 🌊 Complete Data Flow Analysis (Step-by-Step)

When a teacher attempts to grade a batch of student answer sheets, the following sequential pipeline is executed:

### Phase 1: Client-Side Packaging (`script.js`)
1. **Data Collection**: The teacher inputs the **Reference Answer**, **Total Marks** (e.g., 10), selects a **Grading Strictness** (Easy, Medium, or Hard), and drag-and-drops an array of PDF files into the `drop-zone`.
2. **Form Construction**: JavaScript intercepts the submission, prevents default browser reloading, and constructs a `FormData` object appending `files[]`, `teacher_answer`, `total_marks`, and `difficulty`.
3. **AJAX Submission**: An asynchronous `fetch('POST', '/api/evaluate')` dumps the payload to the Flask backend.
4. **Polling Initialization**: The UI immediately locks, displays the loading ring, and begins an interval loop (`setInterval(..., 1000)`) querying `/api/status/<job_id>`.

### Phase 2: Server-Side Ingestion (`app.py`)
1. **Validation & Storage**: `app.py` receives the payload, validates that the files are PDFs, and securely saves them to the `/uploads` directory to prevent memory overflow during multi-megabyte concurrent uploads.
2. **Job Registration**: It generates a unique UUID (`job_id`) and creates an entry in the global `jobs` dictionary: `{'status': 'processing', 'progress': 'Initializing...', 'result': [], 'error': None}`.
3. **Thread Spawning**: To prevent a Gunicorn/Werkzeug timeout (OCR takes minutes), Flask spawns an isolated background daemon thread (`threading.Thread`) targeting the `process_job()` function and immediately returns `{ success: True, job_id: "..." }` to the client.

### Phase 3: The Background Pipeline (`process_job()` thread)
The background thread iterates sequentially over the `saved_files` array to protect computer RAM:

#### A. Computer Vision & OCR (`pdf_processor.py`)
For the current PDF iteration, `process_student_pdf(filepath)` is invoked.
1. **PDF Slicing**: `fitz.open(pdf_path)` opens the document. The module iterates through every page, rendering it to a high-density pixmap matrix.
2. **Matrix Conversion**: The pixmap is converted into an OpenCV compatible RGB standard array (`np.frombuffer`).
3. **PaddleOCR Inference**: The local `PaddleOCR(use_angle_cls=True, lang="en")` model takes the image array. The neural network detects text boundaries, classifies the handwriting, and returns a nested array of strings.
4. **String Concatenation**: Every detected line of text across all pages is joined using newlines `\n` into one massive `student_text` string.

#### B. Natural Language Grading (`evaluator.py`)
With the massive `student_text` string ready, `evaluate_student_answer(student_text, teacher_text, total_marks, difficulty)` is invoked.
1. **Keyword Stripping (NLTK)**: `extract_keywords()` tokenizes the teacher's reference answer. It removes punctuation via `string.maketrans` and strips "Stopwords" (e.g., *the, and, why, explain*) using `nltk.corpus.stopwords`. What remains is an array of raw **Conceptual Keywords**.
2. **Difficulty Matrix**: The `difficulty` string sets the explicit mathematical thresholds for the fuzzy matcher:
   - **Easy**: `ratio_thresh = 70`, `partial_thresh = 75`
   - **Medium**: `ratio_thresh = 85`, `partial_thresh = 90`
   - **Hard**: `ratio_thresh = 95`, `partial_thresh = 98`
3. **Levenshtein Distance Matching (TheFuzz)**: The code iterates through the teacher's Conceptual Keywords, searching the `student_text`. It utilizes:
   - `fuzz.ratio(kw, word)`: Compares the keyword against single student words. If the student misspelled "Photosynthesis" as "Fotosynthsis", the mathematical string similarity might be 88%. Under Medium strictness (85% required), this passes as a Match.
   - `fuzz.partial_ratio(kw, string)`: If the keyword is a compound phrase, it checks if a highly similar substring exists anywhere in the entire text.
4. **Scoring**: It calculates `(Matched Concepts / Total Concepts) = Score Percentage`. The output is scaled by the `total_marks` parameter and rounded.

#### C. Cleanup
- The resulting JSON is appended to `jobs[job_id]['result']`.
- `os.remove()` deletes the local PDF file to free up hard drive space.

### Phase 4: Client-Side Rendering (`script.js`)
1. **Data Retrieval**: The AJAX polling hits `/api/status/<job_id>` and sees `status: 'completed'`.
2. **Dashboard Construction**: The JSON array is passed to `displayDashboard()`. The JS loops through the array, generating `div.leaderboard-card` objects containing the PDF filename and final calculated score.
3. **Insights Hydration**: When a user clicks "View Student Insights", the specific student's JSON object is parsed. Dynamic `span.tag-success` concepts are appended to the DOM, the circular SVG ring displays the grade, and the raw OCR string is injected into the toggleable debug container.

---

## ⚙️ Technical Deep-Dive: Fuzzy Threshold Parameters

The NLP engine's strictness acts as the primary defense against OCR misinterpretation. Since handwriting OCR inherently introduces "noise" (e.g., reading an 'm' as an 'rn'), the Fuzz matching allows the system to remain highly accurate.

* **fuzz.ratio**: Compares two strings in their entirety. "apple" vs "apel" = 75% similarity.
* **fuzz.partial_ratio**: Checks if string A exists as a substring inside string B. "apple" vs "the big apple" = 100% similarity.

By mapping the Teacher's UI selection (Easy/Medium/Hard) to absolute integers matching these ratios, the project grants educators granular control over grading leniency.
