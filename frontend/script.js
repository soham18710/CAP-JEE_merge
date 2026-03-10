document.querySelectorAll(".drop-zone__input").forEach((inputElement) => {
    const dropZoneElement = inputElement.closest(".drop-zone");

    dropZoneElement.addEventListener("click", (e) => {
        inputElement.click();
    });

    inputElement.addEventListener("change", (e) => {
        if (inputElement.files.length) {
            updateThumbnail(dropZoneElement, inputElement.files[0]);
            checkInputs();
        }
    });

    dropZoneElement.addEventListener("dragover", (e) => {
        e.preventDefault();
        dropZoneElement.classList.add("drop-zone--over");
    });

    ["dragleave", "dragend"].forEach((type) => {
        dropZoneElement.addEventListener(type, (e) => {
            dropZoneElement.classList.remove("drop-zone--over");
        });
    });

    dropZoneElement.addEventListener("drop", (e) => {
        e.preventDefault();

        if (e.dataTransfer.files.length) {
            inputElement.files = e.dataTransfer.files;
            updateThumbnail(dropZoneElement, e.dataTransfer.files[0]);
        }

        dropZoneElement.classList.remove("drop-zone--over");
        checkInputs();
    });
});

function updateThumbnail(dropZoneElement, file) {
    let thumbnailElement = dropZoneElement.querySelector(".drop-zone__thumb");

    // First time - remove the prompt
    if (dropZoneElement.querySelector(".drop-zone__prompt")) {
        dropZoneElement.querySelector(".drop-zone__prompt").remove();
    }

    if (!thumbnailElement) {
        thumbnailElement = document.createElement("div");
        thumbnailElement.classList.add("drop-zone__thumb");
        dropZoneElement.appendChild(thumbnailElement);
    }

    thumbnailElement.dataset.label = file.name;
    thumbnailElement.innerHTML = `📄`;
}

function checkInputs() {
    const capFile = document.querySelector('input[name="cap_pdf"]').files[0];
    const jeeFile = document.querySelector('input[name="jee_pdf"]').files[0];
    const processBtn = document.getElementById("process-btn");
    
    processBtn.disabled = !(capFile && jeeFile);
}

document.getElementById("process-btn").addEventListener("click", async () => {
    const capFile = document.querySelector('input[name="cap_pdf"]').files[0];
    const jeeFile = document.querySelector('input[name="jee_pdf"]').files[0];
    const btn = document.getElementById("process-btn");
    const btnText = btn.querySelector(".btn-text");
    const btnLoader = btn.querySelector(".btn-loader");

    const formData = new FormData();
    formData.append("cap_pdf", capFile);
    formData.append("jee_pdf", jeeFile);

    // UI Feedback
    btn.disabled = true;
    btnText.textContent = "Processing PDF Data...";
    btnLoader.classList.remove("hidden");
    
    const progressContainer = document.getElementById("progress-container");
    const progressFill = document.getElementById("progress-bar-fill");
    const progressStage = document.getElementById("progress-stage");
    const progressPercent = document.getElementById("progress-percent");
    const progressMessage = document.getElementById("progress-message");

    progressContainer.classList.remove("hidden");
    progressFill.style.width = "0%";
    
    // Start listening to progress
    const eventSource = new EventSource("http://localhost:8000/progress");
    
    const progressCount = document.getElementById("progress-count");
    const progressSpeed = document.getElementById("progress-speed");
    const progressEta = document.getElementById("progress-eta");

    eventSource.onmessage = (event) => {
        const data = JSON.parse(event.data);
        progressStage.textContent = data.stage;
        progressPercent.textContent = `${data.percent}%`;
        progressFill.style.width = `${data.percent}%`;
        progressMessage.textContent = data.message;

        if (data.total > 0) {
            progressCount.textContent = `${data.current}/${data.total}`;
            
            // Calculate speed and ETA
            const now = Date.now() / 1000;
            const elapsed = now - data.start_time;
            
            if (elapsed > 0.5 && data.current > 0) {
                const speed = data.current / elapsed;
                progressSpeed.textContent = `${speed.toFixed(2)} p/s`;
                
                const remaining = data.total - data.current;
                const etaSeconds = remaining / speed;
                
                if (isFinite(etaSeconds)) {
                    const minutes = Math.floor(etaSeconds / 60);
                    const seconds = Math.floor(etaSeconds % 60);
                    progressEta.textContent = `${minutes.toString().padStart(2, '0')}:${seconds.toString().padStart(2, '0')}`;
                }
            }
        } else {
            progressCount.textContent = "-/-";
            progressSpeed.textContent = "- p/s";
            progressEta.textContent = "--:--";
        }
        
        if (data.stage === "Completed" || data.stage === "Error") {
            eventSource.close();
        }
    };

    eventSource.onerror = () => {
        eventSource.close();
    };

    try {
        const response = await fetch("http://localhost:8000/upload", {
            method: "POST",
            body: formData,
        });

        if (!response.ok) {
            const error = await response.json();
            throw new Error(error.detail || "Upload failed");
        }

        const data = await response.json();
        displayResults(data);
    } catch (error) {
        alert("Error: " + error.message);
        console.error(error);
        progressStage.textContent = "Error";
        progressMessage.textContent = error.message;
    } finally {
        btn.disabled = false;
        btnText.textContent = "Merge & Process";
        btnLoader.classList.add("hidden");
        // We keep the progress bar visible for a bit or until next upload
    }
});

function displayResults(data) {
    const section = document.getElementById("results-section");
    const body = document.getElementById("results-body");
    
    // Fill summary
    document.getElementById("total-count").textContent = data.summary.total_students;
    document.getElementById("matched-count").textContent = data.summary.matched_students;
    const rate = ((data.summary.matched_students / data.summary.total_students) * 100).toFixed(1);
    document.getElementById("success-rate").textContent = `${rate}%`;

    // Fill table
    body.innerHTML = "";
    data.preview.forEach(row => {
        const tr = document.createElement("tr");
        tr.innerHTML = `
            <td>${row.Merit_No || '-'}</td>
            <td>${row.Application_ID}</td>
            <td>${row.JEE_Name || '-'}</td>
            <td>${row.JEE_Main_Percentile || '-'}</td>
            <td>${row.MHT_CET_PCM_Total || '-'}</td>
        `;
        body.appendChild(tr);
    });

    section.classList.remove("hidden");
    section.scrollIntoView({ behavior: 'smooth' });
}
