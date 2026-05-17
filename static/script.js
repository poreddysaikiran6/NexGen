document.addEventListener('DOMContentLoaded', () => {
    const dropZone = document.getElementById('drop-zone');
    const fileInput = document.getElementById('file-input');
    const previewContainer = document.getElementById('preview-container');
    const fileNameDisplay = document.getElementById('file-name');
    const analyzeBtn = document.getElementById('analyze-btn');
    const clearBtn = document.getElementById('clear-btn');
    
    // Form Inputs
    const teacherAnswerInput = document.getElementById('teacher-answer');
    const totalMarksInput = document.getElementById('total-marks');
    
    // Results
    const resultsSection = document.getElementById('results-section');
    const loadingIndicator = document.getElementById('loading');
    const evaluationContainer = document.getElementById('evaluation-container');
    
    const leaderboardSection = document.querySelector('.leaderboard-section');
    const leaderboardList = document.getElementById('leaderboard-list');
    
    const detailedStudentView = document.getElementById('detailed-student-view');
    const detailStudentName = document.getElementById('detail-student-name');
    const finalMarksElem = document.getElementById('final-marks');
    const outOfMarksElem = document.getElementById('out-of-marks');
    const evalFeedbackElem = document.getElementById('eval-feedback');
    const matchedTagsElem = document.getElementById('matched-tags');
    const missedTagsElem = document.getElementById('missed-tags');
    
    // Raw Text Toggle
    const toggleTextBtn = document.getElementById('toggle-text-btn');
    const extractedTextContainer = document.getElementById('extracted-text-container');

    let currentFiles = [];
    const svgEyeClosed = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg> Hide Raw Extracted Text';
    const svgEyeOpen = '<svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg> View Raw Extracted Text';

    // Handle Drag & Drop
    dropZone.addEventListener('click', () => fileInput.click());

    dropZone.addEventListener('dragover', (e) => {
        e.preventDefault();
        dropZone.classList.add('drop-zone--over');
    });

    ['dragleave', 'dragend'].forEach(type => {
        dropZone.addEventListener(type, (e) => {
            dropZone.classList.remove('drop-zone--over');
        });
    });

    dropZone.addEventListener('drop', (e) => {
        e.preventDefault();
        dropZone.classList.remove('drop-zone--over');

        if (e.dataTransfer.files.length) {
            handleFiles(e.dataTransfer.files);
        }
    });

    fileInput.addEventListener('change', (e) => {
        if (fileInput.files.length) {
            handleFiles(fileInput.files);
        }
    });

    function handleFiles(files) {
        const validFiles = Array.from(files).filter(f => f.type === 'application/pdf');
        
        if (validFiles.length === 0) {
            alert('Please select valid PDF files.');
            return;
        }

        currentFiles = validFiles;
        
        if (currentFiles.length === 1) {
            fileNameDisplay.textContent = currentFiles[0].name;
            analyzeBtn.querySelector('.btn-text').textContent = 'Evaluate Student';
        } else {
            fileNameDisplay.textContent = `${currentFiles.length} PDFs selected ready for bulk evaluation`;
            analyzeBtn.querySelector('.btn-text').textContent = 'Evaluate All Students';
        }
        
        dropZone.style.display = 'none';
        previewContainer.style.display = 'flex';
        resultsSection.style.display = 'none';
    }

    clearBtn.addEventListener('click', () => {
        currentFiles = [];
        fileInput.value = '';
        dropZone.style.display = 'flex';
        previewContainer.style.display = 'none';
        resultsSection.style.display = 'none';
    });

    toggleTextBtn.addEventListener('click', () => {
        if (extractedTextContainer.style.display === 'none') {
            extractedTextContainer.style.display = 'block';
            toggleTextBtn.innerHTML = svgEyeClosed;
        } else {
            extractedTextContainer.style.display = 'none';
            toggleTextBtn.innerHTML = svgEyeOpen;
        }
    });

    analyzeBtn.addEventListener('click', async () => {
        if (currentFiles.length === 0) return;
        
        const teacherAns = teacherAnswerInput.value.trim();
        if (!teacherAns) {
            alert('Please enter a Teacher Reference Answer before evaluating.');
            teacherAnswerInput.focus();
            return;
        }

        // UI updates for loading
        analyzeBtn.disabled = true;
        clearBtn.disabled = true;
        resultsSection.style.display = 'block';
        loadingIndicator.style.display = 'flex';
        evaluationContainer.style.display = 'none';
        detailedStudentView.style.display = 'none';
        extractedTextContainer.style.display = 'none';
        toggleTextBtn.innerHTML = svgEyeOpen;

        const formData = new FormData();
        currentFiles.forEach(file => {
            formData.append('files', file);
        });
        formData.append('teacher_answer', teacherAns);
        formData.append('total_marks', totalMarksInput.value || '10');
        
        const difficultyInputs = document.getElementsByName('difficulty');
        let selectedDifficulty = 'Medium';
        for (const rb of difficultyInputs) {
            if (rb.checked) {
                selectedDifficulty = rb.value;
                break;
            }
        }
        formData.append('difficulty', selectedDifficulty);
        
        const evaluationModel = document.getElementById('evaluation-model').value;
        formData.append('evaluation_model', evaluationModel);

        const ocrEngine = document.getElementById('ocr-engine-model').value;
        formData.append('ocr_engine', ocrEngine);

        try {
            const response = await fetch('/api/evaluate', {
                method: 'POST',
                body: formData
            });

            const data = await response.json();

            if (data.error) {
                throw new Error(data.error);
            }
            
            const jobId = data.job_id;
            const loadingText = loadingIndicator.querySelector('p');
            
            // Start polling for status
            const pollInterval = setInterval(async () => {
                try {
                    const statusRes = await fetch(`/api/status/${jobId}`);
                    const statusData = await statusRes.json();
                    
                    if (statusData.progress) {
                        loadingText.textContent = statusData.progress;
                    }
                    
                    if (statusData.status === 'completed') {
                        clearInterval(pollInterval);
                        displayDashboard(statusData.result);
                        loadingIndicator.style.display = 'none';
                        analyzeBtn.disabled = false;
                        clearBtn.disabled = false;
                    } else if (statusData.status === 'error') {
                        clearInterval(pollInterval);
                        throw new Error(statusData.error);
                    }
                } catch (err) {
                    clearInterval(pollInterval);
                    alert(`Polling Error: ${err.message}`);
                    resultsSection.style.display = 'none';
                    loadingIndicator.style.display = 'none';
                    analyzeBtn.disabled = false;
                    clearBtn.disabled = false;
                }
            }, 1000);

        } catch (error) {
            alert(`Error: ${error.message}`);
            resultsSection.style.display = 'none';
            loadingIndicator.style.display = 'none';
            analyzeBtn.disabled = false;
            clearBtn.disabled = false;
        }
    });

    function displayDashboard(evalDataList) {
        evaluationContainer.style.display = 'block';
        leaderboardList.innerHTML = '';
        
        if (!evalDataList || evalDataList.length === 0) {
            leaderboardSection.style.display = 'none';
            return;
        }
        
        if (evalDataList.length === 1) {
            // Only one file, go straight to detailed view
            leaderboardSection.style.display = 'none';
            showDetailedView(evalDataList[0]);
        } else {
            // Multiple files, populate leaderboard
            leaderboardSection.style.display = 'block';
            evalDataList.forEach((evalData, index) => {
                const card = document.createElement('div');
                card.className = 'leaderboard-card';
                card.innerHTML = `
                    <div class="lb-details">
                        <span class="lb-name">
                            <svg class="lb-name-icon" width="20" height="20" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2"><path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z"></path><polyline points="14 2 14 8 20 8"></polyline><line x1="16" y1="13" x2="8" y2="13"></line><line x1="16" y1="17" x2="8" y2="17"></line><polyline points="10 9 9 9 8 9"></polyline></svg>
                            ${evalData.filename}
                        </span>
                        <span class="lb-score"><strong>${evalData.marks}</strong> / ${evalData.total_marks}</span>
                    </div>
                    <button class="btn btn-outline btn-small view-details-btn" data-index="${index}">View Student Insights</button>
                `;
                leaderboardList.appendChild(card);
            });

            // Add event listeners
            document.querySelectorAll('.view-details-btn').forEach(btn => {
                btn.addEventListener('click', (e) => {
                    const idx = parseInt(e.target.getAttribute('data-index'));
                    showDetailedView(evalDataList[idx]);
                    detailedStudentView.scrollIntoView({ behavior: 'smooth', block: 'start' });
                });
            });
            
            // Show the first one initially
            showDetailedView(evalDataList[0]);
        }
    }

    function showDetailedView(evalData) {
        detailedStudentView.style.display = 'block';
        detailStudentName.textContent = evalData.filename;

        // 1. Populate Score
        finalMarksElem.textContent = evalData.marks;
        outOfMarksElem.textContent = evalData.total_marks;
        evalFeedbackElem.textContent = evalData.feedback;

        // 2. Populate Tags
        matchedTagsElem.innerHTML = '';
        if (evalData.matched_keywords && evalData.matched_keywords.length > 0) {
            evalData.matched_keywords.forEach(kw => {
                const tag = document.createElement('span');
                tag.className = 'tag tag-success';
                tag.textContent = kw;
                matchedTagsElem.appendChild(tag);
            });
        } else {
            matchedTagsElem.innerHTML = '<span style="color:var(--text-muted);font-style:italic">No concepts matched.</span>';
        }

        missedTagsElem.innerHTML = '';
        if (evalData.missed_keywords && evalData.missed_keywords.length > 0) {
            evalData.missed_keywords.forEach(kw => {
                const tag = document.createElement('span');
                tag.className = 'tag tag-danger';
                tag.textContent = kw;
                missedTagsElem.appendChild(tag);
            });
        } else {
            missedTagsElem.innerHTML = '<span style="color:var(--text-muted);font-style:italic">Wow, nothing missed!</span>';
        }

        // 3. Raw Text
        extractedTextContainer.textContent = evalData.student_text || "No text extracted.";
        extractedTextContainer.style.display = 'none';
        toggleTextBtn.innerHTML = svgEyeOpen;
    }
});
