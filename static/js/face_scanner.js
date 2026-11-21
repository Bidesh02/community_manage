/**
 * AegisGate - Real-Time OpenCV Automated Face & Biometric Recognition Gate Controller
 * Full Automated Mobile-Style Face Scanner & Motorized Boom Barrier Gate Controller
 */
document.addEventListener('DOMContentLoaded', () => {
  // Video & HUD elements
  const videoFeed = document.getElementById('videoFeed');
  const annotatedImage = document.getElementById('annotatedImage');
  const btnStartCam = document.getElementById('btnStartCam');
  const btnStopCam = document.getElementById('btnStopCam');
  const btnScanNow = document.getElementById('btnScanNow');
  const btnAutoScan = document.getElementById('btnAutoScan');
  const fileUploadInput = document.getElementById('fileUploadInput');

  // Scanner status elements
  const statusIndicator = document.getElementById('scannerStatusIndicator');
  const statusText = document.getElementById('scannerStatusText');
  const resultCard = document.getElementById('scanResultCard');
  const resultStatusBadge = document.getElementById('resultStatusBadge');
  const resultName = document.getElementById('resultName');
  const resultRole = document.getElementById('resultRole');
  const resultBlock = document.getElementById('resultBlock');
  const resultFlat = document.getElementById('resultFlat');
  const resultVehicle = document.getElementById('resultVehicle');
  const resultConfidence = document.getElementById('resultConfidence');
  const resultMessage = document.getElementById('resultMessage');
  const resultPassCode = document.getElementById('resultPassCode');
  const resultPassCodeContainer = document.getElementById('resultPassCodeContainer');
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

  // Delivery Agent Face Form elements
  const deliveryFaceForm = document.getElementById('deliveryFaceForm');
  const delCompany = document.getElementById('delCompany');
  const delFlat = document.getElementById('delFlat');
  const delName = document.getElementById('delName');
  const delPhoto = document.getElementById('delPhoto');
  const btnSnapDeliveryFace = document.getElementById('btnSnapDeliveryFace');

  let stream = null;
  let autoScanInterval = null;
  let isScanning = false;
  let isGateOpen = false;
  let gateCountdownInterval = null;
  let deliverySnappedBase64 = null;

  // CSRF token helper
  function getCSRFToken() {
    const input = document.querySelector('input[name="csrfmiddlewaretoken"]');
    if (input && input.value) return input.value;
    const cookie = document.cookie.split(';').map(c => c.trim()).find(c => c.startsWith('csrftoken='));
    return cookie ? decodeURIComponent(cookie.split('=')[1]) : '';
  }

  // -----------------------------------------------------------
  // WEB AUDIO SOUND EFFECTS & VOICE ANNOUNCEMENTS
  // -----------------------------------------------------------
  function playChime(isSuccess) {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);

      if (isSuccess) {
        osc.frequency.setValueAtTime(587.33, ctx.currentTime); // D5
        osc.frequency.setValueAtTime(880, ctx.currentTime + 0.1); // A5
        gain.gain.setValueAtTime(0.2, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.45);
        osc.start();
        osc.stop(ctx.currentTime + 0.45);
      } else {
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(220, ctx.currentTime);
        osc.frequency.setValueAtTime(160, ctx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.22, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);
        osc.start();
        osc.stop(ctx.currentTime + 0.35);
      }
    } catch (e) {}
  }

  function playMotorSound(isOpen) {
    try {
      const AudioCtx = window.AudioContext || window.webkitAudioContext;
      if (!AudioCtx) return;
      const ctx = new AudioCtx();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.type = 'triangle';
      osc.connect(gain);
      gain.connect(ctx.destination);

      if (isOpen) {
        osc.frequency.setValueAtTime(130, ctx.currentTime);
        osc.frequency.linearRampToValueAtTime(320, ctx.currentTime + 0.85);
      } else {
        osc.frequency.setValueAtTime(280, ctx.currentTime);
        osc.frequency.linearRampToValueAtTime(120, ctx.currentTime + 0.85);
      }
      gain.gain.setValueAtTime(0.12, ctx.currentTime);
      gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.9);
      osc.start();
      osc.stop(ctx.currentTime + 0.9);
    } catch (e) {}
  }

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
  function triggerAutomatedGateOpening(personName, role, block, flatUnit, confidence, isDelivery, passCode) {
    if (isGateOpen) return;
    isGateOpen = true;

    // Traffic Light: Green Active, Red & Amber Off
    if (trafficLedRed) trafficLedRed.classList.remove('active');
    if (trafficLedAmber) trafficLedAmber.classList.remove('active');
    if (trafficLedGreen) trafficLedGreen.classList.add('active');

    if (badgeLedDot) badgeLedDot.className = 'signal-led green active';
    if (statusIndicator) statusIndicator.style.background = '#10b981';

    if (gateStatusText) {
      gateStatusText.innerText = 'GATE OPEN • PROCEED';
      gateStatusText.style.color = '#34d399';
    }

    if (laneWarningText) {
      if (isDelivery) {
        laneWarningText.innerText = '🟢 DELIVERY AUTHORIZED • PROCEED TO UNIT ' + (flatUnit || '') + ' 🟢';
      } else {
        laneWarningText.innerText = '🟢 BARRIER LIFTED • ACCESS AUTHORIZED • PROCEED SAFELY 🟢';
      }
      laneWarningText.style.color = '#34d399';
    }

    // Biometric Similarity HUD Update
    if (biometricStageLabel) {
      biometricStageLabel.innerText = isDelivery ? 'DELIVERY CLEARANCE CONFIRMED' : 'BIOMETRIC SIMILARITY CONFIRMED';
    }
    if (biometricSimilarityVal) {
      biometricSimilarityVal.innerText = `${confidence}% MATCH`;
      biometricSimilarityVal.style.color = '#10b981';
    }
    if (matrixFillBar) {
      matrixFillBar.style.width = `${confidence}%`;
      matrixFillBar.style.background = 'linear-gradient(90deg, #06b6d4, #10b981)';
    }

    // Physically lift barrier arm
    if (physicalBarrierArm) {
      physicalBarrierArm.classList.add('open');
    }

    playMotorSound(true);
    playChime(true);

    const greetingName = personName ? (personName.split(' ')[0] || personName) : 'Visitor';
    const unitPart = flatUnit && flatUnit !== 'Gate Review' && flatUnit !== 'N/A' ? `, Unit ${flatUnit}` : '';
    if (isDelivery) {
      speakAnnouncement(`Delivery verified for ${unitPart || 'resident'}. Welcome ${greetingName}. Gate is opening.`);
    } else {
      speakAnnouncement(`Biometrics verified. Welcome ${greetingName}${unitPart}. Gate is opening.`);
    }

    // 5-second Passage Window with countdown
    let secondsLeft = 5;
    if (gateCountdownText) gateCountdownText.innerText = `Auto-Closing in ${secondsLeft}s`;

    if (gateCountdownInterval) clearInterval(gateCountdownInterval);
    gateCountdownInterval = setInterval(() => {
      secondsLeft -= 1;
      if (gateCountdownText) {
        gateCountdownText.innerText = secondsLeft > 0 ? `Auto-Closing in ${secondsLeft}s` : '';
      }

      if (secondsLeft <= 0) {
        clearInterval(gateCountdownInterval);
        gateCountdownInterval = null;
        closeGateSafely();
      }
    }, 1000);
  }

  function closeGateSafely() {
    if (gateCountdownInterval) {
      clearInterval(gateCountdownInterval);
      gateCountdownInterval = null;
    }

    if (physicalBarrierArm) {
      physicalBarrierArm.classList.remove('open');
    }
    playMotorSound(false);

    if (trafficLedGreen) trafficLedGreen.classList.remove('active');
    if (trafficLedAmber) trafficLedAmber.classList.remove('active');
    if (trafficLedRed) trafficLedRed.classList.add('active');

    if (badgeLedDot) badgeLedDot.className = 'signal-led red active';
    if (statusIndicator) statusIndicator.style.background = stream ? '#06b6d4' : '#64748b';

    if (gateStatusText) {
      gateStatusText.innerText = 'GATE LOCKED';
      gateStatusText.style.color = '#ffffff';
    }
    if (laneWarningText) {
      laneWarningText.innerText = '▲ AUTOMATED STOP LINE • STAND IN FRONT OF SENSOR ▲';
      laneWarningText.style.color = 'var(--text-dim)';
    }
    if (gateCountdownText) gateCountdownText.innerText = '';
    if (biometricStageLabel) biometricStageLabel.innerText = 'BIOMETRIC SIMILARITY STATUS';
    if (biometricSimilarityVal) {
      biometricSimilarityVal.innerText = 'STANDBY';
      biometricSimilarityVal.style.color = 'var(--text-dim)';
    }
    if (matrixFillBar) matrixFillBar.style.width = '0%';

    setTimeout(() => {
      isGateOpen = false;
    }, 800);
  }

  function triggerGateDenied(confidence, message) {
    if (trafficLedRed) trafficLedRed.classList.add('active');
    if (trafficLedAmber) trafficLedAmber.classList.remove('active');
    if (trafficLedGreen) trafficLedGreen.classList.remove('active');

    if (badgeLedDot) badgeLedDot.className = 'signal-led red active';
    if (statusIndicator) statusIndicator.style.background = '#f43f5e';

    if (gateStatusText) {
      gateStatusText.innerText = 'ACCESS DENIED • GATE LOCKED';
      gateStatusText.style.color = '#fb7185';
    }
    if (laneWarningText) {
      laneWarningText.innerText = '⛔ ACCESS DENIED • UNREGISTERED BIOMETRICS • REPORT TO GUARD ⛔';
      laneWarningText.style.color = '#fb7185';
    }

    if (biometricStageLabel) biometricStageLabel.innerText = 'BIOMETRIC SIMILARITY FAILED';
    if (biometricSimilarityVal) {
      biometricSimilarityVal.innerText = `${confidence}% (UNDER THRESHOLD)`;
      biometricSimilarityVal.style.color = '#f43f5e';
    }
    if (matrixFillBar) {
      matrixFillBar.style.width = `${Math.max(20, confidence)}%`;
      matrixFillBar.style.background = '#f43f5e';
    }

    if (physicalBarrierArm) {
      physicalBarrierArm.classList.remove('open');
    }

    playChime(false);
    speakAnnouncement("Access denied. Unregistered biometrics. Please report to security booth.");
  }

  // -----------------------------------------------------------
  // MANUAL OVERRIDES
  // -----------------------------------------------------------
  if (btnManualOpen) {
    btnManualOpen.addEventListener('click', () => {
      triggerAutomatedGateOpening('Security Officer', 'Manual Override', '', 'Gate 1', 100, false, null);
    });
  }

  if (btnEmergencyLock) {
    btnEmergencyLock.addEventListener('click', () => {
      closeGateSafely();
    });
  }

  // -----------------------------------------------------------
  // CAMERA STREAMING & AUTONOMOUS RECOGNITION LOOP
  // -----------------------------------------------------------
  if (btnStartCam) {
    btnStartCam.addEventListener('click', async () => {
      try {
        stream = await navigator.mediaDevices.getUserMedia({
          video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' }
        });
        if (videoFeed) {
          videoFeed.srcObject = stream;
          videoFeed.style.display = 'block';
        }
        if (annotatedImage) annotatedImage.style.display = 'none';

        btnStartCam.style.display = 'none';
        if (btnStopCam) btnStopCam.style.display = 'inline-flex';
        if (btnScanNow) btnScanNow.disabled = false;
        if (btnAutoScan) btnAutoScan.disabled = false;
        if (btnSnapDeliveryFace) btnSnapDeliveryFace.style.display = 'inline-flex';

        if (statusText) statusText.innerText = 'AUTONOMOUS BIOMETRIC SENSOR ONLINE';
        if (statusIndicator) statusIndicator.style.background = '#06b6d4';

        startAutomatedRecognitionLoop();
      } catch (err) {
        console.error("Camera access error:", err);
        if (statusText) statusText.innerText = 'CAMERA UNAVAILABLE (USE IMAGE UPLOAD OR DELIVERY PASS BELOW)';
        if (statusIndicator) statusIndicator.style.background = '#f43f5e';
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
    }
    if (btnAutoScan) {
      btnAutoScan.innerHTML = '<i class="fa-solid fa-bolt"></i> Enable Auto-Scan';
      btnAutoScan.classList.remove('btn-cyan');
      btnAutoScan.classList.add('btn-secondary');
      btnAutoScan.disabled = true;
    }
    if (videoFeed) {
      videoFeed.srcObject = null;
      videoFeed.style.display = 'none';
    }
    if (btnStartCam) btnStartCam.style.display = 'inline-flex';
    if (btnStopCam) btnStopCam.style.display = 'none';
    if (btnScanNow) btnScanNow.disabled = true;
    if (btnSnapDeliveryFace) btnSnapDeliveryFace.style.display = 'none';
    if (statusText) statusText.innerText = 'GATE SCANNER STANDBY';
    if (statusIndicator) statusIndicator.style.background = '#64748b';
  }

  function startAutomatedRecognitionLoop() {
    if (autoScanInterval) clearInterval(autoScanInterval);
    if (btnAutoScan) {
      btnAutoScan.innerHTML = '<i class="fa-solid fa-pause"></i> Auto-Scan Active (2s)';
      btnAutoScan.classList.remove('btn-secondary');
      btnAutoScan.classList.add('btn-cyan');
    }

    autoScanInterval = setInterval(() => {
      if (!isScanning && !isGateOpen && stream) {
        const b64 = captureCurrentFrame();
        if (b64) {
          sendForRecognition({ image_base64: b64, gate_name: 'Main Gate 1' });
        }
      }
    }, 2200);
  }

  if (btnAutoScan) {
    btnAutoScan.addEventListener('click', () => {
      if (autoScanInterval) {
        clearInterval(autoScanInterval);
        autoScanInterval = null;
        btnAutoScan.innerHTML = '<i class="fa-solid fa-bolt"></i> Enable Auto-Scan';
        btnAutoScan.classList.remove('btn-cyan');
        btnAutoScan.classList.add('btn-secondary');
        if (statusText) statusText.innerText = 'AUTO-SCAN PAUSED (USE SCAN FACE NOW FOR MANUAL SCAN)';
      } else {
        startAutomatedRecognitionLoop();
        if (statusText) statusText.innerText = 'AUTONOMOUS BIOMETRIC SENSOR ONLINE';
      }
    });
  }

  function captureCurrentFrame() {
    if (!videoFeed || !videoFeed.videoWidth || !videoFeed.videoHeight) return null;
    const canvas = document.createElement('canvas');
    canvas.width = videoFeed.videoWidth;
    canvas.height = videoFeed.videoHeight;
    const ctx = canvas.getContext('2d');
    ctx.drawImage(videoFeed, 0, 0, canvas.width, canvas.height);
    return canvas.toDataURL('image/jpeg', 0.88);
  }

  // -----------------------------------------------------------
  // API RECOGNITION & RESULT PARSING
  // -----------------------------------------------------------
  async function sendForRecognition(payload) {
    if (isScanning || isGateOpen) return;
    isScanning = true;

    if (trafficLedAmber) trafficLedAmber.classList.add('active');
    if (trafficLedRed) trafficLedRed.classList.remove('active');
    if (statusText) statusText.innerText = 'SCANNING BIOMETRICS & MATCHING VECTOR...';
    if (statusIndicator) statusIndicator.style.background = '#8b5cf6';
    if (biometricStageLabel) biometricStageLabel.innerText = 'COMPARING FACIAL GEOMETRY...';
    if (biometricSimilarityVal) biometricSimilarityVal.innerText = 'PROCESSING...';
    if (matrixFillBar) matrixFillBar.style.width = '65%';

    try {
      const isForm = payload instanceof FormData;
      const csrfToken = getCSRFToken();
      const headers = isForm
        ? (csrfToken ? { 'X-CSRFToken': csrfToken } : {})
        : (csrfToken ? { 'Content-Type': 'application/json', 'X-CSRFToken': csrfToken } : { 'Content-Type': 'application/json' });

      const response = await fetch('/api/face-recognize/', {
        method: 'POST',
        headers: headers,
        body: isForm ? payload : JSON.stringify(payload)
      });

      const data = await response.json();
      displayResult(data);
    } catch (err) {
      console.error("Recognition error:", err);
      if (statusText) statusText.innerText = 'BIOMETRIC PIPELINE ERROR';
      if (statusIndicator) statusIndicator.style.background = '#f43f5e';
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

      if (stream && videoFeed) {
        setTimeout(() => {
          if (stream && !isGateOpen && annotatedImage) {
            annotatedImage.style.display = 'none';
          }
        }, 2400);
      }
    }

    if (data.match) {
      // MATCH CONFIRMED (Resident OR Delivery Agent)
      const resName = data.name || 'Unknown';
      const resRole = data.role || (data.is_delivery ? 'Delivery Agent' : 'Resident');
      const resBlock = data.block || '';
      const resFlat = data.flat || 'N/A';
      const resVehicle = data.vehicle || 'No Vehicle Registered';
      const resConf = data.confidence || 98.4;
      const passCode = data.pass_code || null;

      if (statusText) {
        statusText.innerText = data.is_delivery
          ? `DELIVERY CLEARANCE (${resConf}%) - GATE UNLOCKED`
          : `BIOMETRIC MATCH (${resConf}%) - GATE UNLOCKED`;
      }
      if (statusIndicator) statusIndicator.style.background = '#10b981';

      if (resultCard) resultCard.className = 'match-result-card success fade-in';
      if (resultStatusBadge) {
        resultStatusBadge.innerText = data.is_delivery ? 'DELIVERY AUTHORIZED' : 'AUTHENTICATED';
        resultStatusBadge.className = 'badge badge-resolved';
      }

      if (resultName) resultName.innerText = resName;
      if (resultRole) resultRole.innerText = resRole;
      if (resultBlock) resultBlock.innerText = resBlock || '—';
      if (resultFlat) resultFlat.innerText = resFlat;
      if (resultVehicle) resultVehicle.innerText = resVehicle;
      if (resultConfidence) resultConfidence.innerText = resConf + '%';

      if (resultPassCodeContainer && resultPassCode) {
        if (passCode) {
          resultPassCode.innerText = passCode;
          resultPassCodeContainer.style.display = 'block';
        } else {
          resultPassCodeContainer.style.display = 'none';
        }
      }

      if (resultMessage) {
        resultMessage.innerText = data.message || `Gate Unlocked: Welcome back, ${resName}! Barrier lifted.`;
      }

      triggerAutomatedGateOpening(resName, resRole, resBlock, resFlat, resConf, data.is_delivery, passCode);
      prependLiveLog(resName, resRole, resBlock, resFlat, resConf, 'GRANTED', data.timestamp || 'Just Now');

    } else if (data.face_detected) {
      // FACE DETECTED BUT UNREGISTERED
      if (statusText) statusText.innerText = 'ACCESS DENIED - UNREGISTERED BIOMETRICS';
      if (statusIndicator) statusIndicator.style.background = '#f43f5e';

      if (resultCard) resultCard.className = 'match-result-card denied fade-in';
      if (resultStatusBadge) {
        resultStatusBadge.innerText = 'ACCESS DENIED';
        resultStatusBadge.className = 'badge badge-urgent';
      }

      if (resultName) resultName.innerText = 'Unregistered Visitor';
      if (resultRole) resultRole.innerText = 'Guest / Unknown';
      if (resultBlock) resultBlock.innerText = '—';
      if (resultFlat) resultFlat.innerText = 'Direct to Security Booth';
      if (resultVehicle) resultVehicle.innerText = '—';
      if (resultConfidence) resultConfidence.innerText = (data.confidence || 0) + '%';
      if (resultPassCodeContainer) resultPassCodeContainer.style.display = 'none';
      if (resultMessage) resultMessage.innerText = data.message || 'Face not recognized. If delivery courier, upload face and flat below.';

      triggerGateDenied(data.confidence || 0, data.message);
      prependLiveLog('Unregistered Guest', 'Guest', '—', 'Security Review', data.confidence || 0, 'DENIED', data.timestamp || 'Just Now');

    } else {
      // NO FACE IN TARGET
      if (statusText) statusText.innerText = data.message || 'SCANNING... NO FACE IN TARGET AREA';
      if (statusIndicator) statusIndicator.style.background = '#f59e0b';
      if (trafficLedRed) trafficLedRed.classList.add('active');
      if (trafficLedAmber) trafficLedAmber.classList.remove('active');
      if (matrixFillBar) matrixFillBar.style.width = '0%';
      if (biometricStageLabel) biometricStageLabel.innerText = 'ALIGN FACE IN CAMERA TARGET';
      if (biometricSimilarityVal) biometricSimilarityVal.innerText = 'AWAITING FACE';
    }
  }

  function prependLiveLog(name, role, block, flat, confidence, status, time) {
    if (!liveLogsTbody) return;
    const row = document.createElement('tr');
    row.className = 'fade-in';
    const isGranted = status === 'GRANTED';
    row.innerHTML = `
      <td><strong>${name}</strong></td>
      <td><span class="badge ${isGranted ? 'badge-resolved' : 'badge-urgent'}">${role}</span></td>
      <td style="color: var(--accent-cyan);">${block || '—'}</td>
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
        if (videoFeed) videoFeed.style.display = 'none';
        sendForRecognition(formData);
      }
    });
  }

  // Snap current camera frame for Delivery Agent form
  if (btnSnapDeliveryFace) {
    btnSnapDeliveryFace.addEventListener('click', () => {
      const b64 = captureCurrentFrame();
      if (b64) {
        deliverySnappedBase64 = b64;
        btnSnapDeliveryFace.innerHTML = '<i class="fa-solid fa-circle-check" style="color:#10b981;"></i> Camera Snapshot Ready';
        if (statusText) statusText.innerText = 'DELIVERY FACE SNAPSHOT READY. ENTER FLAT & SUBMIT.';
      }
    });
  }

  // Delivery Agent Face Upload Submission
  if (deliveryFaceForm) {
    deliveryFaceForm.addEventListener('submit', (e) => {
      e.preventDefault();
      const company = delCompany ? delCompany.value : 'Courier Delivery';
      const flat = delFlat ? delFlat.value.trim() : '';
      const name = delName && delName.value.trim() ? delName.value.trim() : `${company} Agent`;
      const file = delPhoto && delPhoto.files && delPhoto.files[0] ? delPhoto.files[0] : null;

      if (!flat) {
        alert('Please enter destination flat / unit number.');
        return;
      }

      if (!file && !deliverySnappedBase64) {
        alert('Please upload a delivery agent face photo or click "Use Cam Snapshot".');
        return;
      }

      const fd = new FormData();
      fd.append('is_delivery', 'true');
      fd.append('delivery_company', company);
      fd.append('delivery_flat', flat);
      fd.append('delivery_name', name);
      fd.append('gate_name', 'Gate 1 - Delivery Lane');

      if (file) {
        fd.append('image_file', file);
      } else if (deliverySnappedBase64) {
        fd.append('image_base64', deliverySnappedBase64);
      }

      if (statusText) statusText.innerText = `PROCESSING DELIVERY CLEARANCE FOR UNIT ${flat}...`;
      if (videoFeed) videoFeed.style.display = 'none';
      sendForRecognition(fd);

      // Reset snapshot state
      deliverySnappedBase64 = null;
      if (btnSnapDeliveryFace) btnSnapDeliveryFace.innerHTML = '<i class="fa-solid fa-camera"></i> Use Cam Snapshot';
      delPhoto.value = '';
    });
  }

  // Expose testResidentPhoto globally for the Enrolled Resident Roster "Test" buttons
  window.testResidentPhoto = async function(photoUrl, name) {
    if (statusText) statusText.innerText = `SCANNING BIOMETRICS FOR ${name.toUpperCase()}...`;
    if (statusIndicator) statusIndicator.style.background = '#8b5cf6';
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
      formData.append('gate_name', 'Gate 1 - Simulation');

      if (videoFeed) videoFeed.style.display = 'none';
      sendForRecognition(formData);
    } catch (e) {
      console.error(e);
      if (statusText) statusText.innerText = 'SIMULATION FAILED';
      if (trafficLedRed) trafficLedRed.classList.add('active');
      if (trafficLedAmber) trafficLedAmber.classList.remove('active');
    }
  };
});
