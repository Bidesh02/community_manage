/**
 * AegisGate - Real-Time OpenCV Face Recognition Gate Scanner
 */
document.addEventListener('DOMContentLoaded', () => {
  const videoFeed = document.getElementById('videoFeed');
  const overlayCanvas = document.getElementById('overlayCanvas');
  const annotatedImage = document.getElementById('annotatedImage');
  const btnStartCam = document.getElementById('btnStartCam');
  const btnStopCam = document.getElementById('btnStopCam');
  const btnScanNow = document.getElementById('btnScanNow');
  const btnAutoScan = document.getElementById('btnAutoScan');
  const fileUploadInput = document.getElementById('fileUploadInput');
  
  const statusIndicator = document.getElementById('scannerStatusIndicator');
  const statusText = document.getElementById('scannerStatusText');
  const resultCard = document.getElementById('scanResultCard');
  const resultName = document.getElementById('resultName');
  const resultRole = document.getElementById('resultRole');
  const resultFlat = document.getElementById('resultFlat');
  const resultVehicle = document.getElementById('resultVehicle');
  const resultConfidence = document.getElementById('resultConfidence');
  const resultMessage = document.getElementById('resultMessage');
  const liveLogsTbody = document.getElementById('liveLogsTbody');

  let stream = null;
  let autoScanInterval = null;
  let isScanning = false;

  // Sound Synthesizer for Access Chimes (Web Audio API)
  function playChime(isSuccess) {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.connect(gain);
      gain.connect(audioCtx.destination);

      if (isSuccess) {
        osc.frequency.setValueAtTime(587.33, audioCtx.currentTime); // D5
        osc.frequency.setValueAtTime(880, audioCtx.currentTime + 0.1); // A5
        gain.gain.setValueAtTime(0.15, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.4);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.4);
      } else {
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(220, audioCtx.currentTime);
        osc.frequency.setValueAtTime(164.8, audioCtx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.35);
      }
    } catch (e) {
      // AudioContext unavailable or restricted
    }
  }

  // Camera Management
  if (btnStartCam) {
    btnStartCam.addEventListener('click', async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' }
        });
        videoFeed.srcObject = stream;
        videoFeed.style.display = 'block';
        if (annotatedImage) annotatedImage.style.display = 'none';

        btnStartCam.style.display = 'none';
        btnStopCam.style.display = 'inline-flex';
        btnScanNow.disabled = false;
        btnAutoScan.disabled = false;

        statusText.innerText = 'CAMERA ONLINE - READY';
        statusIndicator.style.background = '#06b6d4';
      } catch (err) {
        console.error("Camera access error:", err);
        statusText.innerText = 'CAMERA UNAVAILABLE (USE IMAGE UPLOAD BELOW)';
        statusIndicator.style.background = '#f43f5e';
      }
    });
  }

  if (btnStopCam) {
    btnStopCam.addEventListener('click', () => {
      stopCamera();
    });
  }

  function stopCamera() {
    if (stream) {
      stream.getTracks().forEach(track => track.stop());
      stream = null;
    }
    if (autoScanInterval) {
      clearInterval(autoScanInterval);
      autoScanInterval = null;
      btnAutoScan.innerText = 'Enable Auto-Scan';
    }
    if (btnStartCam) btnStartCam.style.display = 'inline-flex';
    if (btnStopCam) btnStopCam.style.display = 'none';
    if (btnScanNow) btnScanNow.disabled = true;
    if (btnAutoScan) btnAutoScan.disabled = true;
    if (statusText) statusText.innerText = 'CAMERA STANDBY';
    if (statusIndicator) statusIndicator.style.background = '#64748b';
  }

  // Capture frame from video feed to base64
  function captureCurrentFrame() {
    if (!videoFeed || videoFeed.videoWidth === 0) return null;
    const canvas = document.createElement('canvas');
    canvas.width = videoFeed.videoWidth;
    canvas.height = videoFeed.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoFeed, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.88);
  }

  // Perform Face Recognition API Request
  async function sendForRecognition(payload) {
    if (isScanning) return;
    isScanning = true;
    statusText.innerText = 'OPENCV ANALYSIS IN PROGRESS...';
    statusIndicator.style.background = '#8b5cf6';

    try {
      let response;
      if (payload instanceof FormData) {
        response = await fetch('/api/face-recognize/', {
          method: 'POST',
          body: payload
        });
      } else {
        response = await fetch('/api/face-recognize/', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify(payload)
        });
      }

      const data = await response.json();
      displayResult(data);
    } catch (err) {
      console.error("Recognition error:", err);
      statusText.innerText = 'ANALYSIS ERROR';
      statusIndicator.style.background = '#f43f5e';
    } finally {
      isScanning = false;
    }
  }

  function displayResult(data) {
    if (resultCard) resultCard.style.display = 'block';

    if (data.annotated_image && annotatedImage) {
      annotatedImage.src = 'data:image/jpeg;base64,' + data.annotated_image;
      annotatedImage.style.display = 'block';
    }

    if (data.match) {
      playChime(true);
      statusText.innerText = 'ACCESS GRANTED - GATE UNLOCKED';
      statusIndicator.style.background = '#10b981';

      resultCard.className = 'match-result-card success fade-in';
      resultName.innerText = data.name;
      resultRole.innerText = data.role;
      resultFlat.innerText = data.flat;
      resultVehicle.innerText = data.vehicle;
      resultConfidence.innerText = data.confidence + '%';
      resultMessage.innerText = data.message;

      // Prepend to live table
      prependLiveLog(data.name, data.role, data.flat, data.confidence, 'GRANTED', data.timestamp || 'Just Now');
    } else if (data.face_detected) {
      playChime(false);
      statusText.innerText = 'ACCESS DENIED - UNRECOGNIZED VISITOR';
      statusIndicator.style.background = '#f43f5e';

      resultCard.className = 'match-result-card denied fade-in';
      resultName.innerText = 'Unregistered Visitor';
      resultRole.innerText = 'Guest / Unknown';
      resultFlat.innerText = 'Direct to Security Booth';
      resultVehicle.innerText = 'N/A';
      resultConfidence.innerText = data.confidence ? data.confidence + '%' : 'N/A';
      resultMessage.innerText = data.message;

      prependLiveLog('Unregistered Guest', 'Guest', 'Security Guard Review', data.confidence || 0, 'DENIED', data.timestamp || 'Just Now');
    } else {
      statusText.innerText = data.message || 'NO FACE DETECTED';
      statusIndicator.style.background = '#f59e0b';
      resultMessage.innerText = data.message || 'No human face detected in frame. Align face with scanner.';
    }
  }

  function prependLiveLog(name, role, flat, confidence, status, time) {
    if (!liveLogsTbody) return;
    const row = document.createElement('tr');
    row.className = 'fade-in';
    const isGranted = status === 'GRANTED';
    row.innerHTML = `
      <td><strong>${name}</strong></td>
      <td><span class="badge ${isGranted ? 'badge-resolved' : 'badge-urgent'}">${role}</span></td>
      <td>${flat}</td>
      <td><span class="badge-code">${confidence}%</span></td>
      <td><span class="badge ${isGranted ? 'badge-resolved' : 'badge-urgent'}">${status}</span></td>
      <td style="color: var(--text-dim); font-size: 0.8rem;">${time}</td>
    `;
    liveLogsTbody.insertBefore(row, liveLogsTbody.firstChild);
  }

  // Manual Scan Button
  if (btnScanNow) {
    btnScanNow.addEventListener('click', () => {
      const b64 = captureCurrentFrame();
      if (b64) {
        sendForRecognition({ image_base64: b64, gate_name: 'Main Gate 1' });
      }
    });
  }

  // Toggle Auto-Scan
  if (btnAutoScan) {
    btnAutoScan.addEventListener('click', () => {
      if (autoScanInterval) {
        clearInterval(autoScanInterval);
        autoScanInterval = null;
        btnAutoScan.innerText = 'Enable Auto-Scan';
        btnAutoScan.classList.remove('btn-cyan');
        btnAutoScan.classList.add('btn-secondary');
      } else {
        btnAutoScan.innerText = 'Auto-Scanning Active (2.5s)';
        btnAutoScan.classList.remove('btn-secondary');
        btnAutoScan.classList.add('btn-cyan');
        autoScanInterval = setInterval(() => {
          if (!isScanning) {
            const b64 = captureCurrentFrame();
            if (b64) sendForRecognition({ image_base64: b64, gate_name: 'Main Gate 1' });
          }
        }, 2500);
      }
    });
  }

  // Upload Photo for Testing
  if (fileUploadInput) {
    fileUploadInput.addEventListener('change', (e) => {
      const file = e.target.files[0];
      if (file) {
        const formData = new FormData();
        formData.append('image_file', file);
        formData.append('gate_name', 'Gate 1 - Photo Test');
        sendForRecognition(formData);
      }
    });
  }
});
