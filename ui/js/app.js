    // State
    let currentFileBase64 = null;
    let currentFitMode = 'crop';
    let isUploading = false;
    let isRainbow = false;
    let isSledRainbow = false;
    let currentRgb = [0, 255, 255];
    let currentSledRgb = [0, 255, 255];
    const isNativeBridge = !!(window.webkit && window.webkit.messageHandlers && window.webkit.messageHandlers.pybridge);

    // Elements
    const alertBox = document.getElementById('alertBox');
    const deviceBadge = document.getElementById('deviceBadge');
    const deviceText = document.getElementById('deviceText');

    // Tab Navigation
    document.querySelectorAll('.tab-btn').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.tab-btn').forEach(b => b.classList.remove('active'));
        document.querySelectorAll('.tab-pane').forEach(p => p.classList.remove('active'));
        btn.classList.add('active');
        const target = document.getElementById(btn.dataset.tab);
        if (target) target.classList.add('active');

        // Auto-fetch settings when entering device or lighting tabs
        if (btn.dataset.tab === 'tab-device' || btn.dataset.tab === 'tab-lighting' || btn.dataset.tab === 'tab-info') {
          fetchKeyboardSettings();
        }
        if (btn.dataset.tab === 'tab-lighting') {
          startKeyboardPreview();
        } else {
          stopKeyboardPreview();
        }
      });
    });


    // IPC Messaging
    function sendToPython(action, data = {}) {
      const msg = { action, ...data };
      if (isNativeBridge) {
        window.webkit.messageHandlers.pybridge.postMessage(JSON.stringify(msg));
      } else {
        const token = window.__AUTH_TOKEN__ || '';
        fetch('/api/' + action, {
          method: 'POST',
          headers: { 'Content-Type': 'application/json', 'X-Auth-Token': token },
          body: JSON.stringify(msg)
        }).catch(console.error);
      }
    }

    function openExternal(url) {
      if (isNativeBridge) {
        sendToPython('open_external', { url });
      } else {
        window.open(url, '_blank');
      }
    }

    function showAlert(type, message) {
      alertBox.className = `alert ${type}`;
      alertBox.textContent = message;
      alertBox.style.display = 'block';
      setTimeout(() => {
        if (type === 'success') hideAlert();
      }, 5000);
    }

    function hideAlert() {
      alertBox.style.display = 'none';
    }

    // Callbacks from Python
    window.onDeviceStatus = function(d) {
      if (d.connected) {
        deviceBadge.className = 'status-badge connected';
        deviceText.textContent = `Teclado: ${d.name} (${d.node})`;
        document.getElementById('infoDevId').textContent = d.dev_id || '1168';
        document.getElementById('infoNode').textContent = d.node;
        document.getElementById('infoUsbId').textContent = d.vid_pid;
      } else {
        deviceBadge.className = 'status-badge error';
        deviceText.textContent = d.conflict 
          ? `Conflito: feche o processo '${d.conflict}'`
          : 'Teclado não detectado (conecte o cabo USB)';
      }
    };

    window.onFeedback = function(res) {
      if (res.success) {
        showAlert('success', '✓ ' + res.message);
      } else {
        showAlert('error', '✗ ' + res.message);
      }
    };

    window.onSettingsLoaded = function(s) {
      // Debounce
      if (s.debounce !== undefined) {
        document.getElementById('debounceSlider').value = s.debounce;
        document.getElementById('debounceVal').textContent = s.debounce + ' ms';
      }
      // Options
      if (s.options) {
        document.getElementById('switchWinLock').checked = !!s.options.win_lock;
        document.getElementById('switchWasdSwap').checked = !!s.options.wasd_swap;
        document.getElementById('switchLedOff').checked = !!s.options.led_off;
        document.getElementById('switchSideLedOff').checked = !!s.options.side_led_off;
      }
      // Sleep
      if (s.sleep) {
        document.getElementById('selSleepRf').value = s.sleep.rf_sleep;
        document.getElementById('selSleepBt').value = s.sleep.bt_sleep;
        document.getElementById('selSleepDeep').value = s.sleep.rf_deep;
      }
      // LED
      if (s.led) {
        document.getElementById('selLedMode').value = s.led.mode;
        document.getElementById('sliderBrightness').value = s.led.brightness;
        document.getElementById('labelBrightness').textContent = s.led.brightness === 4 ? '4 (Máx)' : s.led.brightness;
        document.getElementById('sliderSpeed').value = s.led.speed;
        document.getElementById('labelSpeed').textContent = s.led.speed;

        isRainbow = !!s.led.rainbow;
        updateRainbowButtons();

        if (s.led.rgb && s.led.rgb.length === 3) {
          setSelectedColor(s.led.rgb[0], s.led.rgb[1], s.led.rgb[2]);
        }
      }
      // Side LED (SLEDPARAM)
      if (s.sled) {
        document.getElementById('selSledMode').value = s.sled.mode;
        document.getElementById('sliderSledBrightness').value = s.sled.brightness;
        document.getElementById('labelSledBrightness').textContent = s.sled.brightness === 4 ? '4 (Máx)' : s.sled.brightness;
        document.getElementById('sliderSledSpeed').value = s.sled.speed;
        document.getElementById('labelSledSpeed').textContent = s.sled.speed;

        isSledRainbow = !!s.sled.rainbow;
        updateSledRainbowButtons();

        if (s.sled.rgb && s.sled.rgb.length === 3) {
          setSelectedSledColor(s.sled.rgb[0], s.sled.rgb[1], s.sled.rgb[2]);
        }
      }
    };

    function fetchKeyboardSettings() {
      sendToPython('get_settings');
    }

    // Tab 1: Screen & GIF logic
    const dropzone = document.getElementById('dropzone');
    const fileInput = document.getElementById('fileInput');
    const previewPanel = document.getElementById('previewPanel');
    const previewImg = document.getElementById('previewImg');
    const fileName = document.getElementById('fileName');
    const fileDims = document.getElementById('fileDims');
    const badgeFrames = document.getElementById('badgeFrames');
    const badgeDuration = document.getElementById('badgeDuration');
    const badgeSize = document.getElementById('badgeSize');
    const delaySlider = document.getElementById('delaySlider');
    const delayVal = document.getElementById('delayVal');
    const framesSlider = document.getElementById('framesSlider');
    const framesVal = document.getElementById('framesVal');
    const btnUpload = document.getElementById('btnUpload');
    const progressContainer = document.getElementById('progressContainer');
    const progressBar = document.getElementById('progressBar');
    const progressInfo = document.getElementById('progressInfo');
    const progressMsg = document.getElementById('progressMsg');
    const progressPct = document.getElementById('progressPct');

    dropzone.addEventListener('click', () => fileInput.click());
    dropzone.addEventListener('dragover', (e) => {
      e.preventDefault();
      dropzone.classList.add('dragover');
    });
    dropzone.addEventListener('dragleave', () => dropzone.classList.remove('dragover'));
    dropzone.addEventListener('drop', (e) => {
      e.preventDefault();
      dropzone.classList.remove('dragover');
      if (e.dataTransfer.files && e.dataTransfer.files[0]) loadFile(e.dataTransfer.files[0]);
    });
    fileInput.addEventListener('change', (e) => {
      if (e.target.files && e.target.files[0]) loadFile(e.target.files[0]);
    });

    document.querySelectorAll('.radio-btn[data-fit]').forEach(btn => {
      btn.addEventListener('click', () => {
        document.querySelectorAll('.radio-btn[data-fit]').forEach(b => b.classList.remove('active'));
        btn.classList.add('active');
        currentFitMode = btn.dataset.fit;
        previewImg.style.objectFit = currentFitMode === 'contain' ? 'contain' : (currentFitMode === 'stretch' ? 'fill' : 'cover');
      });
    });

    delaySlider.addEventListener('input', () => delayVal.textContent = delaySlider.value);
    framesSlider.addEventListener('input', () => framesVal.textContent = framesSlider.value);

    function loadFile(file) {
      fileName.textContent = file.name;
      badgeSize.textContent = (file.size / 1024).toFixed(1) + ' KB';
      hideAlert();

      const reader = new FileReader();
      reader.onload = (e) => {
        currentFileBase64 = e.target.result;
        previewImg.src = currentFileBase64;
        dropzone.classList.add('compact');
        const dzText = dropzone.querySelector('.dropzone-text');
        const dzSubtext = dropzone.querySelector('.dropzone-subtext');
        if (dzText) dzText.textContent = 'Substituir arquivo (.gif, .png, .jpg)';
        if (dzSubtext) dzSubtext.textContent = 'Clique ou solte outro arquivo para trocar a animação';
        previewPanel.style.display = 'flex';
        btnUpload.disabled = false;
        sendToPython('inspect', { image: currentFileBase64 });
      };
      reader.readAsDataURL(file);
    }

    window.onInspectResult = function(data) {
      if (data.ok) {
        fileDims.textContent = `${data.width}x${data.height} px`;
        badgeFrames.textContent = `${data.frames} quadro(s)`;
        badgeDuration.textContent = `~${data.duration} ms/quadro`;
        delaySlider.value = data.suggested_delay;
        delayVal.textContent = data.suggested_delay;
      }
    };

    window.onUploadProgress = function(msg) {
      if (msg.status === 'progress') {
        const pct = msg.pct.toFixed(1) + '%';
        progressBar.style.width = pct;
        progressPct.textContent = pct;
        progressMsg.textContent = msg.msg;
      } else if (msg.status === 'done') {
        progressBar.style.width = '100%';
        progressPct.textContent = '100%';
        progressMsg.textContent = 'Concluído!';
        showAlert('success', '✓ Sucesso! O GIF foi gravado na telinha do seu teclado.');
        isUploading = false;
        btnUpload.disabled = false;
      } else if (msg.status === 'error') {
        showAlert('error', '✗ Erro: ' + msg.msg);
        isUploading = false;
        btnUpload.disabled = false;
      }
    };

    btnUpload.addEventListener('click', () => {
      if (!currentFileBase64 || isUploading) return;
      isUploading = true;
      btnUpload.disabled = true;
      hideAlert();

      progressContainer.style.display = 'block';
      progressInfo.style.display = 'flex';
      progressBar.style.width = '0%';
      progressPct.textContent = '0%';
      progressMsg.textContent = 'Preparando quadros...';

      sendToPython('upload', {
        image: currentFileBase64,
        delay: parseInt(delaySlider.value, 10),
        max_frames: parseInt(framesSlider.value, 10),
        fit: currentFitMode
      });
    });

    // Tab 2: Device Settings listeners
    document.getElementById('btnSyncClock').addEventListener('click', () => {
      sendToPython('set_clock');
    });

    const debounceSlider = document.getElementById('debounceSlider');
    debounceSlider.addEventListener('input', () => {
      document.getElementById('debounceVal').textContent = debounceSlider.value + ' ms';
    });
    document.getElementById('btnSaveDebounce').addEventListener('click', () => {
      sendToPython('set_debounce', { value: parseInt(debounceSlider.value, 10) });
    });

    function applyHardwareOptions() {
      sendToPython('set_options', {
        win_lock: document.getElementById('switchWinLock').checked,
        wasd_swap: document.getElementById('switchWasdSwap').checked,
        led_off: document.getElementById('switchLedOff').checked,
        side_led_off: document.getElementById('switchSideLedOff').checked,
      });
    }

    document.getElementById('btnSaveOptions').addEventListener('click', applyHardwareOptions);

    ['switchWinLock', 'switchWasdSwap', 'switchLedOff', 'switchSideLedOff'].forEach(id => {
      document.getElementById(id).addEventListener('change', () => {
        applyHardwareOptions();
      });
    });

    document.getElementById('btnSaveSleep').addEventListener('click', () => {
      sendToPython('set_sleep', {
        rf_sleep: parseInt(document.getElementById('selSleepRf').value, 10),
        bt_sleep: parseInt(document.getElementById('selSleepBt').value, 10),
        rf_deep: parseInt(document.getElementById('selSleepDeep').value, 10),
        bt_deep: parseInt(document.getElementById('selSleepDeep').value, 10),
      });
    });

    // Tab 3: Lighting listeners & Tactical Unified Color Hubs

    const presetColors = [
      '#FF0000', '#FF3B00', '#FF8800', '#FFD000',
      '#00FF00', '#00FF88', '#00FFFF', '#0088FF',
      '#0022FF', '#7B00FF', '#CC00FF', '#FF0088',
      '#FFFFFF', '#FFE4CD', '#00FFAA', '#FF0055'
    ];

    function hsvToRgb(h, s, v) {
      const c = v * s;
      const x = c * (1 - Math.abs(((h / 60) % 2) - 1));
      const m = v - c;
      let r = 0, g = 0, b = 0;
      if (h < 60) [r, g, b] = [c, x, 0];
      else if (h < 120) [r, g, b] = [x, c, 0];
      else if (h < 180) [r, g, b] = [0, c, x];
      else if (h < 240) [r, g, b] = [0, x, c];
      else if (h < 300) [r, g, b] = [x, 0, c];
      else [r, g, b] = [c, 0, x];
      return [Math.round((r + m) * 255), Math.round((g + m) * 255), Math.round((b + m) * 255)];
    }

    function rgbToHsv(r, g, b) {
      r /= 255; g /= 255; b /= 255;
      const max = Math.max(r, g, b), min = Math.min(r, g, b);
      const d = max - min;
      let h = 0;
      const s = max === 0 ? 0 : d / max;
      const v = max;
      if (max !== min) {
        switch (max) {
          case r: h = (g - b) / d + (g < b ? 6 : 0); break;
          case g: h = (b - r) / d + 2; break;
          case b: h = (r - g) / d + 4; break;
        }
        h *= 60;
      }
      return [h, s, v];
    }

    // --- Keys Color Hub Controller ---
    const colorChip = document.getElementById('colorChip');
    const nativeColorMain = document.getElementById('nativeColorMain');
    const inputColorHex = document.getElementById('inputColorHex');
    const labelColorRgb = document.getElementById('labelColorRgb');
    const hueSliderMain = document.getElementById('hueSliderMain');
    const hueValMain = document.getElementById('hueValMain');
    const colorPresetsContainer = document.getElementById('colorPresets');

    function setSelectedColor(r, g, b, fromHue = false) {
      currentRgb = [r, g, b];
      const hex = '#' + [r, g, b].map(x => x.toString(16).padStart(2, '0')).join('').toUpperCase();
      colorChip.style.background = hex;
      nativeColorMain.value = hex;
      inputColorHex.value = hex;
      labelColorRgb.textContent = `RGB(${r}, ${g}, ${b})`;

      if (!fromHue) {
        const [h] = rgbToHsv(r, g, b);
        const roundedHue = Math.round(h);
        hueSliderMain.value = roundedHue;
        hueValMain.textContent = `${roundedHue}°`;
      }

      colorPresetsContainer.querySelectorAll('.preset-dot').forEach(dot => {
        dot.classList.toggle('active', dot.dataset.hex.toUpperCase() === hex);
      });
    }

    nativeColorMain.addEventListener('input', (e) => {
      const hex = e.target.value;
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      setSelectedColor(r, g, b);
    });

    inputColorHex.addEventListener('change', (e) => {
      let val = e.target.value.trim().toUpperCase();
      if (!val.startsWith('#')) val = '#' + val;
      if (/^#[0-9A-F]{6}$/i.test(val)) {
        const r = parseInt(val.slice(1, 3), 16);
        const g = parseInt(val.slice(3, 5), 16);
        const b = parseInt(val.slice(5, 7), 16);
        setSelectedColor(r, g, b);
      } else {
        const hex = '#' + currentRgb.map(x => x.toString(16).padStart(2, '0')).join('').toUpperCase();
        inputColorHex.value = hex;
      }
    });

    hueSliderMain.addEventListener('input', (e) => {
      const h = parseInt(e.target.value, 10);
      hueValMain.textContent = `${h}°`;
      const [r, g, b] = hsvToRgb(h, 1.0, 1.0);
      setSelectedColor(r, g, b, true);
    });

    presetColors.forEach(hex => {
      const dot = document.createElement('div');
      dot.className = 'preset-dot';
      dot.style.background = hex;
      dot.title = hex;
      dot.dataset.hex = hex;
      dot.addEventListener('click', () => {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        setSelectedColor(r, g, b);
      });
      colorPresetsContainer.appendChild(dot);
    });

    // --- Side LEDs Color Hub Controller ---
    const sledColorChip = document.getElementById('sledColorChip');
    const nativeColorSled = document.getElementById('nativeColorSled');
    const inputSledColorHex = document.getElementById('inputSledColorHex');
    const labelSledColorRgb = document.getElementById('labelSledColorRgb');
    const hueSliderSled = document.getElementById('hueSliderSled');
    const hueValSled = document.getElementById('hueValSled');
    const sledColorPresetsContainer = document.getElementById('sledColorPresets');

    function setSelectedSledColor(r, g, b, fromHue = false) {
      currentSledRgb = [r, g, b];
      const hex = '#' + [r, g, b].map(x => x.toString(16).padStart(2, '0')).join('').toUpperCase();
      sledColorChip.style.background = hex;
      nativeColorSled.value = hex;
      inputSledColorHex.value = hex;
      labelSledColorRgb.textContent = `RGB(${r}, ${g}, ${b})`;

      if (!fromHue) {
        const [h] = rgbToHsv(r, g, b);
        const roundedHue = Math.round(h);
        hueSliderSled.value = roundedHue;
        hueValSled.textContent = `${roundedHue}°`;
      }

      sledColorPresetsContainer.querySelectorAll('.preset-dot').forEach(dot => {
        dot.classList.toggle('active', dot.dataset.hex.toUpperCase() === hex);
      });
    }

    nativeColorSled.addEventListener('input', (e) => {
      const hex = e.target.value;
      const r = parseInt(hex.slice(1, 3), 16);
      const g = parseInt(hex.slice(3, 5), 16);
      const b = parseInt(hex.slice(5, 7), 16);
      setSelectedSledColor(r, g, b);
    });

    inputSledColorHex.addEventListener('change', (e) => {
      let val = e.target.value.trim().toUpperCase();
      if (!val.startsWith('#')) val = '#' + val;
      if (/^#[0-9A-F]{6}$/i.test(val)) {
        const r = parseInt(val.slice(1, 3), 16);
        const g = parseInt(val.slice(3, 5), 16);
        const b = parseInt(val.slice(5, 7), 16);
        setSelectedSledColor(r, g, b);
      } else {
        const hex = '#' + currentSledRgb.map(x => x.toString(16).padStart(2, '0')).join('').toUpperCase();
        inputSledColorHex.value = hex;
      }
    });

    hueSliderSled.addEventListener('input', (e) => {
      const h = parseInt(e.target.value, 10);
      hueValSled.textContent = `${h}°`;
      const [r, g, b] = hsvToRgb(h, 1.0, 1.0);
      setSelectedSledColor(r, g, b, true);
    });

    presetColors.forEach(hex => {
      const dot = document.createElement('div');
      dot.className = 'preset-dot';
      dot.style.background = hex;
      dot.title = hex;
      dot.dataset.hex = hex;
      dot.addEventListener('click', () => {
        const r = parseInt(hex.slice(1, 3), 16);
        const g = parseInt(hex.slice(3, 5), 16);
        const b = parseInt(hex.slice(5, 7), 16);
        setSelectedSledColor(r, g, b);
      });
      sledColorPresetsContainer.appendChild(dot);
    });

    document.getElementById('btnCopyMainColor').addEventListener('click', () => {
      setSelectedSledColor(currentRgb[0], currentRgb[1], currentRgb[2]);
    });

    // Rainbow Mode Controls
    function updateRainbowButtons() {
      if (isRainbow) {
        document.getElementById('btnColorRainbow').classList.add('active');
        document.getElementById('btnColorCustom').classList.remove('active');
        document.getElementById('groupCustomColor').style.opacity = '0.35';
        document.getElementById('groupCustomColor').style.pointerEvents = 'none';
      } else {
        document.getElementById('btnColorCustom').classList.add('active');
        document.getElementById('btnColorRainbow').classList.remove('active');
        document.getElementById('groupCustomColor').style.opacity = '1.0';
        document.getElementById('groupCustomColor').style.pointerEvents = 'auto';
      }
    }

    document.getElementById('btnColorCustom').addEventListener('click', () => {
      isRainbow = false;
      updateRainbowButtons();
    });
    document.getElementById('btnColorRainbow').addEventListener('click', () => {
      isRainbow = true;
      updateRainbowButtons();
    });

    function updateSledRainbowButtons() {
      if (isSledRainbow) {
        document.getElementById('btnSledColorRainbow').classList.add('active');
        document.getElementById('btnSledColorCustom').classList.remove('active');
        document.getElementById('groupSledCustomColor').style.opacity = '0.35';
        document.getElementById('groupSledCustomColor').style.pointerEvents = 'none';
      } else {
        document.getElementById('btnSledColorCustom').classList.add('active');
        document.getElementById('btnSledColorRainbow').classList.remove('active');
        document.getElementById('groupSledCustomColor').style.opacity = '1.0';
        document.getElementById('groupSledCustomColor').style.pointerEvents = 'auto';
      }
    }

    document.getElementById('btnSledColorCustom').addEventListener('click', () => {
      isSledRainbow = false;
      updateSledRainbowButtons();
    });
    document.getElementById('btnSledColorRainbow').addEventListener('click', () => {
      isSledRainbow = true;
      updateSledRainbowButtons();
    });

    // Sliders & Actions
    const sliderBrightness = document.getElementById('sliderBrightness');
    sliderBrightness.addEventListener('input', () => {
      const v = parseInt(sliderBrightness.value, 10);
      document.getElementById('labelBrightness').textContent = v === 4 ? '4 (Máx)' : v;
    });

    const sliderSpeed = document.getElementById('sliderSpeed');
    sliderSpeed.addEventListener('input', () => {
      document.getElementById('labelSpeed').textContent = sliderSpeed.value;
    });

    document.getElementById('btnApplyLed').addEventListener('click', () => {
      sendToPython('set_led', {
        mode: parseInt(document.getElementById('selLedMode').value, 10),
        speed: parseInt(sliderSpeed.value, 10),
        brightness: parseInt(sliderBrightness.value, 10),
        rainbow: isRainbow,
        rgb: currentRgb
      });
    });

    const sliderSledBrightness = document.getElementById('sliderSledBrightness');
    sliderSledBrightness.addEventListener('input', () => {
      const v = parseInt(sliderSledBrightness.value, 10);
      document.getElementById('labelSledBrightness').textContent = v === 4 ? '4 (Máx)' : v;
    });

    const sliderSledSpeed = document.getElementById('sliderSledSpeed');
    sliderSledSpeed.addEventListener('input', () => {
      document.getElementById('labelSledSpeed').textContent = sliderSledSpeed.value;
    });

    document.getElementById('btnApplySled').addEventListener('click', () => {
      sendToPython('set_side_led', {
        mode: parseInt(document.getElementById('selSledMode').value, 10),
        speed: parseInt(sliderSledSpeed.value, 10),
        brightness: parseInt(sliderSledBrightness.value, 10),
        rainbow: isSledRainbow,
        rgb: currentSledRgb
      });
    });

    // Initialize Default Colors
    setSelectedColor(0, 255, 255);
    setSelectedSledColor(0, 255, 255);


    // Auto-start preview if lighting tab is active on load
    if (document.getElementById('tab-lighting')?.classList.contains('active')) {
      startKeyboardPreview();
    }

    // Tab 4: Reset
    document.getElementById('btnFactoryReset').addEventListener('click', () => {
      if (confirm('Tem certeza de que deseja restaurar as configurações de fábrica do teclado? Todas as personalizações de sono e iluminação serão redefinidas.')) {
        sendToPython('factory_reset');
      }
    });

    // Device check interval
    function checkDevice() {
      sendToPython('status');
    }

    checkDevice();

    // Auto-activate tab from URL hash if provided
    if (window.location.hash) {
      const initialTab = document.querySelector(`.tab-btn[data-tab="${window.location.hash.slice(1)}"]`);
      if (initialTab) initialTab.click();
    }
    setInterval(checkDevice, 4000);
