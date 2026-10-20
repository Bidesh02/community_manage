/**
 * AegisGate - Real-Time OpenCV Automated Face & Biometric Recognition Gate Controller
 * Automatically scans faces, verifies biometric similarity, and lifts the motorized barrier gate!
 */
document.addEventListener('DOMContentLoaded', () => {
  // Video & HUD elements
  const videoFeed = document.getElementById('videoFeed');
  const overlayCanvas = document.getElementById('overlayCanvas');
  const annotatedImage = document.getElementById('annotatedImage');
  const btnStartCam = document.getElementById('btnStartCam');
  const btnStopCam = document.getElementById('btnStopCam');
  const btnScanNow = document.getElementById('btnScanNow');
  const btnAutoScan = document.getElementById('btnAutoScan');
  const fileUploadInput = document.getElementById('fileUploadInput');

  // Scanner status
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

  // Motorized Barrier Gate elements
  const physicalBarrierArm = document.getElementById('physicalBarrierArm');
  const trafficLedRed = document.getElementById('trafficLedRed');
  const trafficLedAmber = document.getElementById('trafficLedAmber');
  const trafficLedGreen = document.getElementById('trafficLedGreen');
  const gateStatusText = document.getElementById('gateStatusText');
  const badgeLedDot = document.getElementById('badgeLedDot');
  const matrixFillBar = document.getElementById('matrixFillBar');
  const biometricSimilarityVal = document.getElementById('biometricSimilarityVal');
  const biometricStageLabel = document.getElementById('biometricStageLabel');
  const gateCountdownText = document.getElementById('gateCountdownText');
  const laneWarningText = document.getElementById('laneWarningText');
  const btnManualOpen = document.getElementById('btnManualOpen');
  const btnEmergencyLock = document.getElementById('btnEmergencyLock');

  let stream = null;
  let autoScanInterval = null;
  let isScanning = false;
  let isGateOpen = false;
  let gateCountdownInterval = null;

  // -----------------------------------------------------------
  // WEB AUDIO SOUND EFFECTS & VOICE ANNOUNCEMENTS
  // -----------------------------------------------------------
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
        gain.gain.setValueAtTime(0.2, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.45);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.45);
      } else {
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(220, audioCtx.currentTime);
        osc.frequency.setValueAtTime(164.8, audioCtx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.25, audioCtx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.35);
        osc.start();
        osc.stop(audioCtx.currentTime + 0.35);
      }
    } catch (e) {
      // Audio restricted
    }
  }

  // Motorized Servo Sound
  function playMotorSound(isOpen) {
    try {
      const audioCtx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = audioCtx.createOscillator();
      const gain = audioCtx.createGain();
      osc.type = 'triangle';
      osc.connect(gain);
      gain.connect(audioCtx.destination);

      if (isOpen) {
        osc.frequency.setValueAtTime(130, audioCtx.currentTime);
        osc.frequency.linearRampToValueAtTime(320, audioCtx.currentTime + 0.9);
      } else {
        osc.frequency.setValueAtTime(280, audioCtx.currentTime);
        osc.frequency.linearRampToValueAtTime(120, audioCtx.currentTime + 0.9);
      }
      gain.gain.setValueAtTime(0.12, audioCtx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, audioCtx.currentTime + 0.95);
      osc.start();
      osc.stop(audioCtx.currentTime + 0.95);
    } catch (e) {}
  }

  // Natural Voice Announcement
  function speakAnnouncement(text) {
    try {
      if ('speechSynthesis' in window) {
        window.speechSynthesis.cancel();
        const utterance = new SpeechSynthesisUtterance(text);
        utterance.rate = 1.0;
        utterance.pitch = 1.05;
        window.speechSynthesis.speak(utterance);
      }
    } catch (e) {}
  }

  // -----------------------------------------------------------
  // AUTOMATED BARRIER GATE OPENING ROUTINE
  // -----------------------------------------------------------
  function triggerAutomatedGateOpening(personName, role, flatUnit, confidence) {
    if (isGateOpen) return;
    isGateOpen = true;

    // Traffic Signal Transition: Amber off, Red off -> Green Active
    if (trafficLedRed) trafficLedRed.classList.remove('active');
    if (trafficLedAmber) trafficLedAmber.classList.remove('active');
    if (trafficLedGreen) trafficLedGreen.classList.add('active');

    if (badgeLedDot) {
      badgeLedDot.className = 'signal-led green active';
    }
    if (gateStatusText) {
      gateStatusText.innerText = 'GATE OPEN • PROCEED';
      gateStatusText.style.color = '#34d399';
    }
    if (laneWarningText) {
      laneWarningText.innerText = '🟢 BARRIER LIFTED • ACCESS AUTHORIZED • PROCEED SAFELY 🟢';
      laneWarningText.style.color = '#34d399';
    }

    // Biometric Similarity HUD Update
    if (biometricStageLabel) biometricStageLabel.innerText = 'BIOMETRIC SIMILARITY CONFIRMED';
    if (biometricSimilarityVal) {
      biometricSimilarityVal.innerText = `${confidence}% MATCH`;
      biometricSimilarityVal.style.color = '#10b981';
    }
    if (matrixFillBar) {
      matrixFillBar.style.width = `${confidence}%`;
      matrixFillBar.style.background = 'linear-gradient(90deg, #06b6d4, #10b981)';
    }

    // Physically lift the barrier arm via CSS transform
    if (physicalBarrierArm) {
      physicalBarrierArm.classList.add('open');
    }

    // Sounds & Voice
    playMotorSound(true);
    playChime(true);
    const greetingName = personName.split(' ')[0] || personName;
    const unitPart = flatUnit && flatUnit !== 'Gate Review' ? `, Unit ${flatUnit}` : '';
    speakAnnouncement(`Biometrics verified. Welcome ${greetingName}${unitPart}. Gate is opening.`);

    // 5-second Passage Window with countdown
    let secondsLeft = 5;
    if (gateCountdownText) gateCountdownText.innerText = `Auto-Closing in ${secondsLeft}s`;

    if (gateCountdownInterval) clearInterval(gateCountdownInterval);
    gateCountdownInterval = setInterval(() => {
      secondsLeft -= 1;
      if (gateCountdownText) {
        gateCountdownText.innerText = `Auto-Closing in ${secondsLeft}s`;
      }

      if (secondsLeft <= 0) {
        clearInterval(gateCountdownInterval);
        gateCountdownInterval = null;
        closeGateSafely();
      }
    }, 1000);
  }

  function closeGateSafely() {
    // Lower the barrier arm smoothly
    if (physicalBarrierArm) {
      physicalBarrierArm.classList.remove('open');
    }
    playMotorSound(false);

    // Reset Traffic Light back to Red
    if (trafficLedGreen) trafficLedGreen.classList.remove('active');
    if (trafficLedAmber) trafficLedAmber.classList.remove('active');
    if (trafficLedRed) trafficLedRed.classList.add('active');

    if (badgeLedDot) {
      badgeLedDot.className = 'signal-led red active';
    }
    if (gateStatusText) {
      gateStatusText.innerText = 'GATE LOCKED';
      gateStatusText.style.color = '#ffffff';
    }
    if (laneWarningText) {
      laneWarningText.innerText = '▲ AUTOMATED STOP LINE • STAND IN FRONT OF SENSOR ▲';
      laneWarningText.style.color = 'var(--text-dim)';
    }
    if (gateCountdownText) {
      gateCountdownText.innerText = '';
    }
    if (biometricStageLabel) {
      biometricStageLabel.innerText = 'BIOMETRIC SIMILARITY STATUS';
    }
    if (biometricSimilarityVal) {
      biometricSimilarityVal.innerText = 'STANDBY';
      biometricSimilarityVal.style.color = 'var(--text-dim)';
    }
    if (matrixFillBar) {
      matrixFillBar.style.width = '0%';
    }

    // Short cooldown before scanning next vehicle/person
    setTimeout(() => {
      isGateOpen = false;
    }, 800);
  }

  function triggerGateDenied(confidence, message) {
    // Red Traffic Light Flashing
    if (trafficLedRed) trafficLedRed.classList.add('active');
    if (trafficLedAmber) trafficLedAmber.classList.remove('active');
    if (trafficLedGreen) trafficLedGreen.classList.remove('active');

    if (badgeLedDot) {
      badgeLedDot.className = 'signal-led red active';
    }
    if (gateStatusText) {
      gateStatusText.innerText = 'ACCESS DENIED • GATE LOCKED';
      gateStatusText.style.color = '#fb7185';
    }
    if (laneWarningText) {
      laneWarningText.innerText = '⛔ ACCESS DENIED • UNREGISTERED BIOMETRICS • REPORT TO GUARD ⛔';
      laneWarningText.style.color = '#fb7185';
    }

    // Matrix Bar Error Red
    if (biometricStageLabel) biometricStageLabel.innerText = 'BIOMETRIC SIMILARITY FAILED';
    if (biometricSimilarityVal) {
      biometricSimilarityVal.innerText = `${confidence}% (UNDER THRESHOLD)`;
      biometricSimilarityVal.style.color = '#f43f5e';
    }
    if (matrixFillBar) {
      matrixFillBar.style.width = `${Math.max(20, confidence)}%`;
      matrixFillBar.style.background = '#f43f5e';
    }

    // Barrier stays firmly locked
    if (physicalBarrierArm) {
      physicalBarrierArm.classList.remove('open');
    }

    playChime(false);
    speakAnnouncement("Access denied. Unregistered biometrics. Please report to security.");
  }

  // -----------------------------------------------------------
  // MANUAL OVERRIDE BUTTONS
  // -----------------------------------------------------------
  if (btnManualOpen) {
    btnManualOpen.addEventListener('click', () => {
      triggerAutomatedGateOpening('Security Override', 'Officer', 'Gate 1', 100);
    });
  }

  if (btnEmergencyLock) {
    btnEmergencyLock.addEventListener('click', () => {
      if (gateCountdownInterval) clearInterval(gateCountdownInterval);
      closeGateSafely();
    });
  }

  // -----------------------------------------------------------
  // CAMERA STREAMING & CONTINUOUS SCANNING
  // -----------------------------------------------------------
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

        statusText.innerText = 'AUTONOMOUS BIOMETRIC SENSOR ONLINE';
        statusIndicator.style.background = '#06b6d4';

        // Automatically start the continuous recognition loop
        startAutomatedRecognitionLoop();
      } catch (err) {
        console.error("Camera access error:", err);
        statusText.innerText = 'CAMERA UNAVAILABLE (USE IMAGE UPLOAD OR ENROLLED SAMPLES BELOW)';
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
      btnAutoScan.classList.remove('btn-cyan');
      btnAutoScan.classList.add('btn-secondary');
    }
    if (btnStartCam) btnStartCam.style.display = 'inline-flex';
    if (btnStopCam) btnStopCam.style.display = 'none';
    if (btnScanNow) btnScanNow.disabled = true;
    if (btnAutoScan) btnAutoScan.disabled = true;
    if (statusText) statusText.innerText = 'GATE SCANNER STANDBY';
    if (statusIndicator) statusIndicator.style.background = '#64748b';
  }

  function startAutomatedRecognitionLoop() {
    if (autoScanInterval) clearInterval(autoScanInterval);
    btnAutoScan.innerText = 'Autonomous Scan Active (2s)';
    btnAutoScan.classList.remove('btn-secondary');
    btnAutoScan.classList.add('btn-cyan');

    autoScanInterval = setInterval(() => {
      // Don't scan if gate is currently open or currently in middle of an API roundtrip
      if (!isScanning && !isGateOpen) {
        const b64 = captureCurrentFrame();
        if (b64) {
          sendForRecognition({ image_base64: b64, gate_name: 'Main Gate 1' });
        }
      }
    }, 2200);
  }

  // Toggle Auto-Scan button manually
  if (btnAutoScan) {
    btnAutoScan.addEventListener('click', () => {
      if (autoScanInterval) {
        clearInterval(autoScanInterval);
        autoScanInterval = null;
        btnAutoScan.innerText = 'Enable Auto-Scan';
        btnAutoScan.classList.remove('btn-cyan');
        btnAutoScan.classList.add('btn-secondary');
      } else {
        startAutomatedRecognitionLoop();
      }
    });
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

  // -----------------------------------------------------------
  // RECOGNITION API CALL & RESULT PARSING
  // -----------------------------------------------------------
  async function sendForRecognition(payload) {
    if (isScanning || isGateOpen) return;
    isScanning = true;

    // Show Amber scanning on traffic light & HUD
    if (trafficLedAmber) trafficLedAmber.classList.add('active');
    if (trafficLedRed) trafficLedRed.classList.remove('active');
    statusText.innerText = 'SCANNING BIOMETRICS & MATCHING VECTOR...';
    statusIndicator.style.background = '#8b5cf6';
    if (biometricStageLabel) biometricStageLabel.innerText = 'COMPARING FACIAL GEOMETRY...';
    if (biometricSimilarityVal) biometricSimilarityVal.innerText = 'PROCESSING...';
    if (matrixFillBar) matrixFillBar.style.width = '65%';

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
      statusText.innerText = 'BIOMETRIC PIPELINE ERROR';
      statusIndicator.style.background = '#f43f5e';
      if (trafficLedRed) trafficLedRed.classList.add('active');
      if (trafficLedAmber) trafficLedAmber.classList.remove('active');
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
      // BIOMETRIC SIMILARITY CONFIRMED -> OPEN THE AUTOMATED GATE!
      statusText.innerText = `BIOMETRIC MATCH CONFIRMED (${data.confidence}%) - OPENING GATE`;
      statusIndicator.style.background = '#10b981';

      resultCard.className = 'match-result-card success fade-in';
      resultName.innerText = data.name;
      resultRole.innerText = data.role;
      resultFlat.innerText = data.flat;
      resultVehicle.innerText = data.vehicle;
      resultConfidence.innerText = data.confidence + '%';
      resultMessage.innerText = `${data.message} Physical barrier arm has lifted.`;

      // Trigger Motorized Gate Barrier Opening
      triggerAutomatedGateOpening(data.name, data.role, data.flat, data.confidence);

      // Prepend to live audit table
      prependLiveLog(data.name, data.role, data.flat, data.confidence, 'GRANTED', data.timestamp || 'Just Now');
    } else if (data.face_detected) {
      // FACE DETECTED BUT SIMILARITY NOT FOUND (UNREGISTERED)
      statusText.innerText = 'ACCESS DENIED - UNREGISTERED BIOMETRICS';
      statusIndicator.style.background = '#f43f5e';

      resultCard.className = 'match-result-card denied fade-in';
      resultName.innerText = 'Unregistered Visitor';
      resultRole.innerText = 'Guest / Unknown';
      resultFlat.innerText = 'Direct to Security Booth';
      resultVehicle.innerText = 'N/A';
      resultConfidence.innerText = data.confidence ? data.confidence + '%' : 'Under Threshold';
      resultMessage.innerText = data.message;

      // Gate remains firmly locked
      triggerGateDenied(data.confidence || 0, data.message);

      prependLiveLog('Unregistered Guest', 'Guest', 'Security Guard Review', data.confidence || 0, 'DENIED', data.timestamp || 'Just Now');
    } else {
      // No face in scanning target area
      statusText.innerText = data.message || 'SCANNING... NO FACE IN TARGET AREA';
      statusIndicator.style.background = '#f59e0b';
      if (trafficLedRed) trafficLedRed.classList.add('active');
      if (trafficLedAmber) trafficLedAmber.classList.remove('active');
      if (matrixFillBar) matrixFillBar.style.width = '0%';
      if (biometricStageLabel) biometricStageLabel.innerText = 'ALIGN FACE IN CAMERA TARGET';
      if (biometricSimilarityVal) biometricSimilarityVal.innerText = 'AWAITING FACE';
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

  // Expose testResidentPhoto globally for the Enrolled Resident Roster "Test" buttons
  window.testResidentPhoto = async function(photoUrl, name) {
    statusText.innerText = `FETCHING BIOMETRIC PROFILE FOR ${name.toUpperCase()}...`;
    statusIndicator.style.background = '#8b5cf6';
    if (trafficLedAmber) trafficLedAmber.classList.add('active');
    if (trafficLedRed) trafficLedRed.classList.remove('active');
    if (biometricStageLabel) biometricStageLabel.innerText = 'READING ENROLLED BIOMETRICS...';
    if (biometricSimilarityVal) biometricSimilarityVal.innerText = 'CALCULATING...';
    if (matrixFillBar) matrixFillBar.style.width = '75%';

    try {
      const response = await fetch(photoUrl);
      const blob = await response.blob();
      const formData = new FormData();
      formData.append('image_file', blob, 'sample.jpg');
      formData.append('gate_name', 'Gate 1 - North Simulation');

      const apiRes = await fetch('/api/face-recognize/', {
        method: 'POST',
        body: formData
      });
      const data = await apiRes.json();

      // Show annotated image
      if (videoFeed) videoFeed.style.display = 'none';
      displayResult(data);
    } catch (e) {
      console.error(e);
      statusText.innerText = 'SIMULATION FAILED';
      if (trafficLedRed) trafficLedRed.classList.add('active');
      if (trafficLedAmber) trafficLedAmber.classList.remove('active');
    }
  };
});
