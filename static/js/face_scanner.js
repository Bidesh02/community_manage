/**
 * AegisGate - Real-Time OpenCV Automated Face & Biometric Recognition Controller
 * Lean, modern controller for automated gate recognition and boom barrier operation.
 */
document.addEventListener('DOMContentLoaded', () => {
  const $ = id => document.getElementById(id);

  let stream = null;
  let autoScan = null;
  let isScanning = false;
  let isGateOpen = false;
  let gateTimer = null;

  // -----------------------------------------------------------
  // AUDIO & VOICE SYNTHESIS
  // -----------------------------------------------------------
  function playSound(type) {
    try {
      const ctx = new (window.AudioContext || window.webkitAudioContext)();
      const osc = ctx.createOscillator();
      const gain = ctx.createGain();
      osc.connect(gain);
      gain.connect(ctx.destination);

      if (type === 'grant') {
        osc.frequency.setValueAtTime(587.33, ctx.currentTime);
        osc.frequency.setValueAtTime(880, ctx.currentTime + 0.1);
        gain.gain.setValueAtTime(0.2, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.45);
        osc.start();
        osc.stop(ctx.currentTime + 0.45);
      } else {
        osc.type = 'sawtooth';
        osc.frequency.setValueAtTime(220, ctx.currentTime);
        osc.frequency.setValueAtTime(160, ctx.currentTime + 0.15);
        gain.gain.setValueAtTime(0.2, ctx.currentTime);
        gain.gain.exponentialRampToValueAtTime(0.01, ctx.currentTime + 0.35);
        osc.start();
        osc.stop(ctx.currentTime + 0.35);
      }
    } catch (e) {}
  }

  function speak(text) {
    if ('speechSynthesis' in window) {
      window.speechSynthesis.cancel();
      const u = new SpeechSynthesisUtterance(text);
      u.rate = 1.0;
      window.speechSynthesis.speak(u);
    }
  }

  // -----------------------------------------------------------
  // MOTORIZED BOOM BARRIER GATE CONTROL
  // -----------------------------------------------------------
  function setTrafficLight(color) {
    const r = $('trafficLedRed'), a = $('trafficLedAmber'), g = $('trafficLedGreen');
    if (r) r.classList.toggle('active', color === 'red');
    if (a) a.classList.toggle('active', color === 'amber');
    if (g) g.classList.toggle('active', color === 'green');
  }

  function openGate(name, role, flat, conf) {
    if (isGateOpen) return;
    isGateOpen = true;

    setTrafficLight('green');
    $('physicalBarrierArm')?.classList.add('open');
    if ($('gateStatusText')) {
      $('gateStatusText').innerText = 'GATE OPEN • PROCEED';
      $('gateStatusText').style.color = '#34d399';
    }
    if ($('badgeLedDot')) $('badgeLedDot').className = 'signal-led green active';
    if ($('biometricStageLabel')) $('biometricStageLabel').innerText = 'BIOMETRIC SIMILARITY CONFIRMED';
    if ($('biometricSimilarityVal')) {
      $('biometricSimilarityVal').innerText = `${conf}% MATCH`;
      $('biometricSimilarityVal').style.color = '#10b981';
    }
    if ($('matrixFillBar')) {
      $('matrixFillBar').style.width = `${conf}%`;
      $('matrixFillBar').style.background = 'linear-gradient(90deg, #06b6d4, #10b981)';
    }

    playSound('grant');
    const firstName = name.split(' ')[0] || name;
    const flatText = flat && flat !== 'Gate Review' ? `, Unit ${flat}` : '';
    speak(`Biometrics verified. Welcome ${firstName}${flatText}. Gate is open.`);

    // 5-second passage window
    let left = 5;
    if ($('gateCountdownText')) $('gateCountdownText').innerText = `Auto-Closing in ${left}s`;
    if (gateTimer) clearInterval(gateTimer);

    gateTimer = setInterval(() => {
      left--;
      if ($('gateCountdownText')) $('gateCountdownText').innerText = left > 0 ? `Auto-Closing in ${left}s` : '';
      if (left <= 0) {
        clearInterval(gateTimer);
        closeGate();
      }
    }, 1000);
  }

  function closeGate() {
    $('physicalBarrierArm')?.classList.remove('open');
    setTrafficLight('red');
    if ($('gateStatusText')) {
      $('gateStatusText').innerText = 'GATE LOCKED';
      $('gateStatusText').style.color = '#ffffff';
    }
    if ($('badgeLedDot')) $('badgeLedDot').className = 'signal-led red active';
    if ($('biometricStageLabel')) $('biometricStageLabel').innerText = 'BIOMETRIC SIMILARITY STATUS';
    if ($('biometricSimilarityVal')) {
      $('biometricSimilarityVal').innerText = 'STANDBY';
      $('biometricSimilarityVal').style.color = 'var(--text-dim)';
    }
    if ($('matrixFillBar')) $('matrixFillBar').style.width = '0%';
    if ($('gateCountdownText')) $('gateCountdownText').innerText = '';

    setTimeout(() => { isGateOpen = false; }, 800);
  }

  // -----------------------------------------------------------
  // API RECOGNITION & RESULT DISPLAY
  // -----------------------------------------------------------
  async function sendForRecognition(payload) {
    if (isScanning || isGateOpen) return;
    isScanning = true;

    setTrafficLight('amber');
    if ($('scannerStatusText')) $('scannerStatusText').innerText = 'SCANNING BIOMETRICS & MATCHING VECTOR...';
    if ($('biometricStageLabel')) $('biometricStageLabel').innerText = 'COMPARING FACIAL GEOMETRY...';
    if ($('biometricSimilarityVal')) $('biometricSimilarityVal').innerText = 'PROCESSING...';
    if ($('matrixFillBar')) $('matrixFillBar').style.width = '65%';

    try {
      const isForm = payload instanceof FormData;
      const res = await fetch('/api/face-recognize/', {
        method: 'POST',
        headers: isForm ? {} : { 'Content-Type': 'application/json' },
        body: isForm ? payload : JSON.stringify(payload)
      });
      const data = await res.json();
      handleResult(data);
    } catch (e) {
      console.error(e);
      setTrafficLight('red');
      if ($('scannerStatusText')) $('scannerStatusText').innerText = 'BIOMETRIC PIPELINE ERROR';
    } finally {
      isScanning = false;
    }
  }

  function handleResult(data) {
    const card = $('scanResultCard');
    if (card) card.style.display = 'block';

    if (data.annotated_image && $('annotatedImage')) {
      $('annotatedImage').src = 'data:image/jpeg;base64,' + data.annotated_image;
      $('annotatedImage').style.display = 'block';
    }

    if (data.match) {
      if ($('scannerStatusText')) $('scannerStatusText').innerText = `BIOMETRIC MATCH (${data.confidence}%) - GATE UNLOCKED`;
      card.className = 'match-result-card success fade-in';
      if ($('resultName')) $('resultName').innerText = data.name;
      if ($('resultRole')) $('resultRole').innerText = data.role;
      if ($('resultFlat')) $('resultFlat').innerText = data.flat;
      if ($('resultVehicle')) $('resultVehicle').innerText = data.vehicle;
      if ($('resultConfidence')) $('resultConfidence').innerText = data.confidence + '%';
      if ($('resultMessage')) $('resultMessage').innerText = `${data.message} Barrier lifted.`;

      openGate(data.name, data.role, data.flat, data.confidence);
      addLog(data.name, data.role, data.flat, data.confidence, 'GRANTED');
    } else if (data.face_detected) {
      if ($('scannerStatusText')) $('scannerStatusText').innerText = 'ACCESS DENIED - UNREGISTERED BIOMETRICS';
      card.className = 'match-result-card denied fade-in';
      if ($('resultName')) $('resultName').innerText = 'Unregistered Visitor';
      if ($('resultRole')) $('resultRole').innerText = 'Guest / Unknown';
      if ($('resultFlat')) $('resultFlat').innerText = 'Direct to Security Booth';
      if ($('resultConfidence')) $('resultConfidence').innerText = (data.confidence || 0) + '%';
      if ($('resultMessage')) $('resultMessage').innerText = data.message;

      setTrafficLight('red');
      playSound('deny');
      speak('Access denied. Unregistered biometrics. Please report to security.');
      addLog('Unregistered Guest', 'Guest', 'Security Review', data.confidence || 0, 'DENIED');
    } else {
      if ($('scannerStatusText')) $('scannerStatusText').innerText = 'SCANNING... NO FACE IN TARGET AREA';
      setTrafficLight('red');
      if ($('matrixFillBar')) $('matrixFillBar').style.width = '0%';
      if ($('biometricStageLabel')) $('biometricStageLabel').innerText = 'ALIGN FACE IN CAMERA TARGET';
      if ($('biometricSimilarityVal')) $('biometricSimilarityVal').innerText = 'AWAITING FACE';
    }
  }

  function addLog(name, role, flat, conf, status) {
    const tb = $('liveLogsTbody');
    if (!tb) return;
    const tr = document.createElement('tr');
    tr.className = 'fade-in';
    const ok = status === 'GRANTED';
    tr.innerHTML = `
      <td><strong>${name}</strong></td>
      <td><span class="badge ${ok ? 'badge-resolved' : 'badge-urgent'}">${role}</span></td>
      <td>${flat}</td>
      <td><span class="badge-code">${conf}%</span></td>
      <td><span class="badge ${ok ? 'badge-resolved' : 'badge-urgent'}">${status}</span></td>
      <td style="color:var(--text-dim);font-size:0.8rem;">Just Now</td>
    `;
    tb.insertBefore(tr, tb.firstChild);
  }

  // -----------------------------------------------------------
  // CAMERA STREAMING & CONTROLS
  // -----------------------------------------------------------
  $('btnStartCam')?.addEventListener('click', async () => {
    try {
      stream = await navigator.mediaDevices.getUserMedia({
        video: { width: { ideal: 1280 }, height: { ideal: 720 }, facingMode: 'user' }
      });
      const v = $('videoFeed');
      v.srcObject = stream;
      v.style.display = 'block';
      if ($('annotatedImage')) $('annotatedImage').style.display = 'none';

      $('btnStartCam').style.display = 'none';
      if ($('btnStopCam')) $('btnStopCam').style.display = 'inline-flex';
      if ($('btnScanNow')) $('btnScanNow').disabled = false;
      if ($('scannerStatusText')) $('scannerStatusText').innerText = 'AUTONOMOUS BIOMETRIC SENSOR ONLINE';

      // Start continuous scanning loop (every 2.2s)
      autoScan = setInterval(() => {
        if (!isScanning && !isGateOpen && v.videoWidth) {
          const c = document.createElement('canvas');
          c.width = v.videoWidth;
          c.height = v.videoHeight;
          c.getContext('2d').drawImage(v, 0, 0);
          sendForRecognition({ image_base64: c.toDataURL('image/jpeg', 0.88), gate_name: 'Main Gate 1' });
        }
      }, 2200);
    } catch (e) {
      if ($('scannerStatusText')) $('scannerStatusText').innerText = 'CAMERA UNAVAILABLE (USE IMAGE UPLOAD OR ENROLLED SAMPLES BELOW)';
    }
  });

  $('btnStopCam')?.addEventListener('click', () => {
    if (stream) stream.getTracks().forEach(t => t.stop());
    stream = null;
    if (autoScan) clearInterval(autoScan);
    $('btnStartCam').style.display = 'inline-flex';
    if ($('btnStopCam')) $('btnStopCam').style.display = 'none';
    if ($('btnScanNow')) $('btnScanNow').disabled = true;
    if ($('scannerStatusText')) $('scannerStatusText').innerText = 'GATE SCANNER STANDBY';
  });

  $('btnScanNow')?.addEventListener('click', () => {
    const v = $('videoFeed');
    if (v && v.videoWidth) {
      const c = document.createElement('canvas');
      c.width = v.videoWidth;
      c.height = v.videoHeight;
      c.getContext('2d').drawImage(v, 0, 0);
      sendForRecognition({ image_base64: c.toDataURL('image/jpeg', 0.88), gate_name: 'Main Gate 1' });
    }
  });

  $('fileUploadInput')?.addEventListener('change', e => {
    if (e.target.files[0]) {
      const fd = new FormData();
      fd.append('image_file', e.target.files[0]);
      fd.append('gate_name', 'Gate 1 - Photo Test');
      sendForRecognition(fd);
    }
  });

  // Manual Overrides
  $('btnManualOpen')?.addEventListener('click', () => openGate('Security Override', 'Officer', 'Gate 1', 100));
  $('btnEmergencyLock')?.addEventListener('click', closeGate);

  // Global Enrolled Profile Simulation
  window.testResidentPhoto = async function(url, name) {
    if ($('scannerStatusText')) $('scannerStatusText').innerText = `BIOMETRIC SCAN FOR ${name.toUpperCase()}...`;
    setTrafficLight('amber');
    try {
      const blob = await (await fetch(url)).blob();
      const fd = new FormData();
      fd.append('image_file', blob, 'sample.jpg');
      fd.append('gate_name', 'Gate 1 - Simulation');
      if ($('videoFeed')) $('videoFeed').style.display = 'none';
      sendForRecognition(fd);
    } catch (e) {
      if ($('scannerStatusText')) $('scannerStatusText').innerText = 'SIMULATION FAILED';
      setTrafficLight('red');
    }
  };
});
