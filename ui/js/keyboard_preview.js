    // ==============================================================================
    // REAL-TIME KEYBOARD & SIDE LED PREVIEW ENGINE (Attack Shark K86)
    // ==============================================================================
    const kbCanvas = document.getElementById('keyboardCanvas');
    const kbCtx = kbCanvas.getContext('2d');
    let kbAnimId = null;
    let lastAnimTime = performance.now();
    const userRipples = [];

    // 75% Compact Layout of Attack Shark K86
    const K86_KEYMAP = [
      // Row 0: F-Row (y = 18, h = 22)
      [
        { name: 'ESC', x: 26, w: 26 },
        { name: 'F1', x: 62, w: 26 }, { name: 'F2', x: 92, w: 26 }, { name: 'F3', x: 122, w: 26 }, { name: 'F4', x: 152, w: 26 },
        { name: 'F5', x: 190, w: 26 }, { name: 'F6', x: 220, w: 26 }, { name: 'F7', x: 250, w: 26 }, { name: 'F8', x: 280, w: 26 },
        { name: 'F9', x: 318, w: 26 }, { name: 'F10', x: 348, w: 26 }, { name: 'F11', x: 378, w: 26 }, { name: 'F12', x: 408, w: 26 },
        { name: 'DEL', x: 444, w: 26 }, { name: 'HOME', x: 474, w: 26 }, { name: 'END', x: 504, w: 26 }
      ],
      // Row 1: Numbers (y = 48, h = 26)
      [
        { name: '~', x: 26, w: 26 },
        { name: '1', x: 56, w: 26 }, { name: '2', x: 86, w: 26 }, { name: '3', x: 116, w: 26 }, { name: '4', x: 146, w: 26 },
        { name: '5', x: 176, w: 26 }, { name: '6', x: 206, w: 26 }, { name: '7', x: 236, w: 26 }, { name: '8', x: 266, w: 26 },
        { name: '9', x: 296, w: 26 }, { name: '0', x: 326, w: 26 }, { name: '-', x: 356, w: 26 }, { name: '=', x: 386, w: 26 },
        { name: 'BACK', x: 416, w: 54 },
        { name: 'PGUP', x: 504, w: 26 }
      ],
      // Row 2: QWERTY (y = 80, h = 26)
      [
        { name: 'TAB', x: 26, w: 40 },
        { name: 'Q', x: 70, w: 26 }, { name: 'W', x: 100, w: 26 }, { name: 'E', x: 130, w: 26 }, { name: 'R', x: 160, w: 26 },
        { name: 'T', x: 190, w: 26 }, { name: 'Y', x: 220, w: 26 }, { name: 'U', x: 250, w: 26 }, { name: 'I', x: 280, w: 26 },
        { name: 'O', x: 310, w: 26 }, { name: 'P', x: 340, w: 26 }, { name: '[', x: 370, w: 26 }, { name: ']', x: 400, w: 26 },
        { name: '\\', x: 430, w: 40 },
        { name: 'PGDN', x: 504, w: 26 }
      ],
      // Row 3: ASDF (y = 112, h = 26)
      [
        { name: 'CAPS', x: 26, w: 48 },
        { name: 'A', x: 78, w: 26 }, { name: 'S', x: 108, w: 26 }, { name: 'D', x: 138, w: 26 }, { name: 'F', x: 168, w: 26 },
        { name: 'G', x: 198, w: 26 }, { name: 'H', x: 228, w: 26 }, { name: 'J', x: 258, w: 26 }, { name: 'K', x: 288, w: 26 },
        { name: 'L', x: 318, w: 26 }, { name: ';', x: 348, w: 26 }, { name: '\'', x: 378, w: 26 },
        { name: 'ENTER', x: 408, w: 62 },
        { name: 'INS', x: 504, w: 26 }
      ],
      // Row 4: ZXCV (y = 144, h = 26)
      [
        { name: 'SHIFT', x: 26, w: 60 },
        { name: 'Z', x: 90, w: 26 }, { name: 'X', x: 120, w: 26 }, { name: 'C', x: 150, w: 26 }, { name: 'V', x: 180, w: 26 },
        { name: 'B', x: 210, w: 26 }, { name: 'N', x: 240, w: 26 }, { name: 'M', x: 270, w: 26 }, { name: ',', x: 300, w: 26 },
        { name: '.', x: 330, w: 26 }, { name: '/', x: 360, w: 26 },
        { name: 'SHIFT', x: 390, w: 52 },
        { name: '▲', x: 474, w: 26 }
      ],
      // Row 5: Modifiers (y = 176, h = 26)
      [
        { name: 'CTRL', x: 26, w: 34 },
        { name: 'WIN', x: 64, w: 30 },
        { name: 'ALT', x: 98, w: 30 },
        { name: 'SPACE', x: 132, w: 170 },
        { name: 'ALT', x: 306, w: 30 },
        { name: 'FN', x: 340, w: 30 },
        { name: 'CTRL', x: 374, w: 34 },
        { name: '◄', x: 444, w: 26 },
        { name: '▼', x: 474, w: 26 },
        { name: '►', x: 504, w: 26 }
      ]
    ];

    // Flatten keys with absolute row geometries
    const FLAT_KEYS = [];
    const ROW_GEOMS = [
      { y: 18, h: 22 },
      { y: 48, h: 26 },
      { y: 80, h: 26 },
      { y: 112, h: 26 },
      { y: 144, h: 26 },
      { y: 176, h: 26 }
    ];
    K86_KEYMAP.forEach((row, rIdx) => {
      const rg = ROW_GEOMS[rIdx];
      row.forEach((k, cIdx) => {
        const cx = k.x + k.w / 2;
        const cy = rg.y + rg.h / 2;
        const minDim = Math.min(k.w, rg.h);
        FLAT_KEYS.push({
          ...k,
          y: rg.y,
          h: rg.h,
          row: rIdx,
          col: cIdx,
          cx,
          cy,
          nx: (cx - 26) / 500,
          ny: (cy - 18) / 184,
          underR: minDim * 0.36,
          capR: minDim * 0.32,
          innerR: minDim * 0.28,
          isShortLegend: k.name.length <= 3
        });
      });
    });
    function roundRect(ctx, x, y, w, h, r) {
      ctx.beginPath();
      ctx.moveTo(x + r, y);
      ctx.lineTo(x + w - r, y);
      ctx.quadraticCurveTo(x + w, y, x + w, y + r);
      ctx.lineTo(x + w, y + h - r);
      ctx.quadraticCurveTo(x + w, y + h, x + w - r, y + h);
      ctx.lineTo(x + r, y + h);
      ctx.quadraticCurveTo(x, y + h, x, y + h - r);
      ctx.lineTo(x, y + r);
      ctx.quadraticCurveTo(x, y, x + r, y);
      ctx.closePath();
    }

    // Cached DOM references for preview loop
    const elSelLedMode = document.getElementById('selLedMode');
    const elSliderSpeed = document.getElementById('sliderSpeed');
    const elSliderBrightness = document.getElementById('sliderBrightness');
    const elSwitchLedOff = document.getElementById('switchLedOff');
    const elSelSledMode = document.getElementById('selSledMode');
    const elSliderSledSpeed = document.getElementById('sliderSledSpeed');
    const elSliderSledBrightness = document.getElementById('sliderSledBrightness');
    const elSwitchSideLedOff = document.getElementById('switchSideLedOff');
    const elPreviewKeyModeLabel = document.getElementById('previewKeyModeLabel');
    const elPreviewSideModeLabel = document.getElementById('previewSideModeLabel');
    const elPreviewSpeedLabel = document.getElementById('previewSpeedLabel');
    const elPreviewStatusText = document.getElementById('previewStatusText');

    const lastLabels = { key: '', side: '', speed: '', status: '' };

    // Pre-rendered static layer (Chassis, TFT Bezel & Glass Glare, Rotary Knob Base)
    const staticCanvas = document.createElement('canvas');
    staticCanvas.width = 680;
    staticCanvas.height = 232;
    const staticCtx = staticCanvas.getContext('2d');

    (function initStaticKeyboardLayer() {
      const chassisX = 10, chassisY = 8, chassisW = 660, chassisH = 214, chassisR = 14;
      roundRect(staticCtx, chassisX, chassisY, chassisW, chassisH, chassisR);
      staticCtx.fillStyle = '#0a0d13';
      staticCtx.fill();
      staticCtx.lineWidth = 1.5;
      staticCtx.strokeStyle = '#1e2638';
      staticCtx.stroke();

      // Inner Plate Bevel
      roundRect(staticCtx, chassisX + 8, chassisY + 6, chassisW - 16, chassisH - 12, 8);
      staticCtx.fillStyle = '#0f131c';
      staticCtx.fill();

      // TFT Bezel & Screen Background
      const tftX = 552, tftY = 16, tftW = 56, tftH = 32;
      roundRect(staticCtx, tftX, tftY, tftW, tftH, 4);
      staticCtx.fillStyle = '#05070a';
      staticCtx.fill();
      staticCtx.lineWidth = 1;
      staticCtx.strokeStyle = '#232b3d';
      staticCtx.stroke();

      roundRect(staticCtx, tftX + 3, tftY + 3, tftW - 6, tftH - 6, 2);
      staticCtx.fillStyle = '#030814';
      staticCtx.fill();

      // Static Screen Glass Glare
      staticCtx.beginPath();
      staticCtx.moveTo(tftX + 3, tftY + 3);
      staticCtx.lineTo(tftX + 28, tftY + 3);
      staticCtx.lineTo(tftX + 3, tftY + 24);
      staticCtx.closePath();
      staticCtx.fillStyle = 'rgba(255, 255, 255, 0.08)';
      staticCtx.fill();

      // Rotary Knob Base & Inner Knurled Surface
      const knobX = 636, knobY = 32, knobR = 14;
      staticCtx.beginPath();
      staticCtx.arc(knobX, knobY, knobR, 0, Math.PI * 2);
      staticCtx.fillStyle = '#161c28';
      staticCtx.fill();
      staticCtx.lineWidth = 1.5;
      staticCtx.strokeStyle = '#2e394e';
      staticCtx.stroke();

      staticCtx.beginPath();
      staticCtx.arc(knobX, knobY, knobR - 3, 0, Math.PI * 2);
      staticCtx.fillStyle = '#0d1117';
      staticCtx.fill();
    })();

    function drawKeyboardFrame(now) {
      lastAnimTime = now;
      const t = now / 1000;

      const mode = parseInt(elSelLedMode.value, 10);
      const speedVal = parseInt(elSliderSpeed.value, 10);
      const speedMult = [0.4, 0.7, 1.0, 1.5, 2.2][speedVal] || 1.0;
      const rawBrt = parseInt(elSliderBrightness.value, 10);
      const isLedOff = elSwitchLedOff?.checked;
      const brt = isLedOff ? 0 : rawBrt / 4.0;

      const smode = parseInt(elSelSledMode.value, 10);
      const sspeedVal = parseInt(elSliderSledSpeed.value, 10);
      const sspeedMult = [0.4, 0.7, 1.0, 1.5, 2.2][sspeedVal] || 1.0;
      const rawSbrt = parseInt(elSliderSledBrightness.value, 10);
      const isSledOff = elSwitchSideLedOff?.checked;
      const sbrt = (isSledOff || smode === 0) ? 0 : rawSbrt / 4.0;

      // Dirty-checked indicator labels
      const selModeText = (elSelLedMode.options[elSelLedMode.selectedIndex]?.text || '').split('(')[0].trim();
      const selSledText = (elSelSledMode.options[elSelSledMode.selectedIndex]?.text || '').split('(')[0].trim();
      const speedText = `${speedVal}`;
      const statusText = brt === 0 ? 'Backlight Desligado' : (isRainbow ? 'Modo Arco-íris' : 'Cor Customizada');

      if (selModeText !== lastLabels.key) {
        elPreviewKeyModeLabel.textContent = selModeText;
        lastLabels.key = selModeText;
      }
      if (selSledText !== lastLabels.side) {
        elPreviewSideModeLabel.textContent = selSledText;
        lastLabels.side = selSledText;
      }
      if (speedText !== lastLabels.speed) {
        elPreviewSpeedLabel.textContent = speedText;
        lastLabels.speed = speedText;
      }
      if (statusText !== lastLabels.status) {
        elPreviewStatusText.textContent = statusText;
        lastLabels.status = statusText;
      }

      // 1. Blit pre-rendered static chassis, TFT bezel & knob base
      kbCtx.clearRect(0, 0, kbCanvas.width, kbCanvas.height);
      kbCtx.drawImage(staticCanvas, 0, 0);

      // 2. Draw Side LED Strips (Left & Right Chassis Borders) without shadowBlur
      const drawSideStrip = (x) => {
        const stripH = 176;
        const stripY = 24;
        const stripW = 4;

        if (sbrt > 0) {
          const segs = 12;
          const segH = stripH / segs;
          for (let i = 0; i < segs; i++) {
            const sy = stripY + i * segH;
            const ny = i / segs;
            let sr = currentSledRgb[0], sg = currentSledRgb[1], sb = currentSledRgb[2];
            let sAlpha = sbrt;

            if (smode === 1) { // Static
              if (isSledRainbow) {
                [sr, sg, sb] = hsvToRgb((ny * 360) % 360, 1.0, 1.0);
              }
            } else if (smode === 2) { // Breathing
              const breath = 0.3 + 0.7 * (0.5 + 0.5 * Math.sin(t * sspeedMult * 2.8));
              sAlpha *= breath;
            } else if (smode === 3) { // Neon Rainbow
              const hue = (ny * 360 + t * sspeedMult * 140) % 360;
              [sr, sg, sb] = hsvToRgb(hue, 1.0, 1.0);
            } else if (smode === 4) { // Wave
              const wave = 0.3 + 0.7 * (0.5 + 0.5 * Math.sin(ny * 6 - t * sspeedMult * 5));
              sAlpha *= wave;
            } else if (smode === 5) { // Snake
              const phase = (t * sspeedMult * 1.5) % 2;
              const snakePos = phase < 1 ? phase : (2 - phase);
              const dist = Math.abs(ny - snakePos);
              const head = Math.max(0, 1 - dist * 3.5);
              sAlpha *= Math.max(0.15, head);
            }

            // Fast geometric halo + core segment
            roundRect(kbCtx, x - 2, sy - 0.5, stripW + 4, segH, 3);
            kbCtx.fillStyle = `rgba(${sr}, ${sg}, ${sb}, ${sAlpha * 0.25})`;
            kbCtx.fill();

            roundRect(kbCtx, x, sy, stripW, segH - 1, 2);
            kbCtx.fillStyle = `rgba(${sr}, ${sg}, ${sb}, ${sAlpha * 0.9})`;
            kbCtx.fill();
          }
        } else {
          roundRect(kbCtx, x, stripY, stripW, stripH, 2);
          kbCtx.fillStyle = '#141822';
          kbCtx.fill();
        }
      };

      drawSideStrip(13);
      drawSideStrip(663);

      // 3. Dynamic TFT wave & Rotary Knob indicator
      const tftX = 552, tftY = 16, tftW = 56;
      kbCtx.beginPath();
      for (let px = 0; px < tftW - 6; px += 2) {
        const py = tftY + 16 + Math.sin(px * 0.3 + t * 4) * 4;
        if (px === 0) kbCtx.moveTo(tftX + 3 + px, py);
        else kbCtx.lineTo(tftX + 3 + px, py);
      }
      kbCtx.strokeStyle = '#00d2ff';
      kbCtx.lineWidth = 1.2;
      kbCtx.stroke();

      const knobX = 636, knobY = 32;
      const dotAngle = (t * 0.8) % (Math.PI * 2);
      kbCtx.beginPath();
      kbCtx.arc(knobX + Math.cos(dotAngle) * 7, knobY + Math.sin(dotAngle) * 7, 1.5, 0, Math.PI * 2);
      kbCtx.fillStyle = '#f59e0b';
      kbCtx.fill();

      // Clean expired user ripples
      while (userRipples.length > 0 && now - userRipples[0].time > 900) {
        userRipples.shift();
      }

      // 4. Draw All Keys & Dynamic Backlight without shadowBlur
      kbCtx.textAlign = 'center';
      kbCtx.textBaseline = 'middle';
      let currentFontShort = null;

      FLAT_KEYS.forEach((k, idx) => {
        const nx = k.nx;
        const ny = k.ny;

        let kr = currentRgb[0], kg = currentRgb[1], kb = currentRgb[2];
        let kAlpha = brt;

        // Compute effect lighting algorithms
        if (brt > 0) {
          switch (mode) {
            case 1: // Estático (Static)
              if (isRainbow) {
                [kr, kg, kb] = hsvToRgb((nx * 360) % 360, 1.0, 1.0);
              }
              break;
            case 2: // Respiração (Breathing)
              const breath = 0.15 + 0.85 * (0.5 + 0.5 * Math.sin(t * speedMult * 2.5));
              if (isRainbow) {
                [kr, kg, kb] = hsvToRgb((t * speedMult * 50) % 360, 1.0, 1.0);
              }
              kAlpha *= breath;
              break;
            case 3: // Ciclo de Espectro (Spectrum Cycle)
              [kr, kg, kb] = hsvToRgb((t * speedMult * 70) % 360, 1.0, 1.0);
              break;
            case 4: // Onda (Wave)
              const waveHue = (nx * 360 - t * speedMult * 160 + 360) % 360;
              if (isRainbow) {
                [kr, kg, kb] = hsvToRgb(waveHue, 1.0, 1.0);
              } else {
                const intens = 0.3 + 0.7 * (0.5 + 0.5 * Math.sin(nx * 8 - t * speedMult * 4.5));
                kAlpha *= intens;
              }
              break;
            case 5: // Ondulação ao Digitar (Ripple)
              const distCenter = Math.hypot(k.cx - 260, k.cy - 100);
              const rip = Math.sin(distCenter * 0.05 - t * speedMult * 6);
              kAlpha *= Math.max(0.2, (0.5 + 0.5 * rip));
              break;
            case 6: // Pontos Estelares (Star Dots)
              const star = Math.sin(idx * 23.7 + t * speedMult * 5.2);
              kAlpha *= Math.max(0.18, (0.5 + 0.5 * star));
              break;
            case 7: // Fluxo (Flow)
              const flowHue = ((nx + ny * 0.5) * 260 + t * speedMult * 100) % 360;
              [kr, kg, kb] = hsvToRgb(flowHue, 1.0, 1.0);
              break;
            case 8: // Sombra de Tecla (Key Shadow)
              const shadowVal = 0.2 + 0.8 * Math.abs(Math.sin(k.col * 0.5 - t * speedMult * 3));
              kAlpha *= shadowVal;
              break;
            case 9: // Camadas (Layers)
              const layerPhase = (k.row * 0.4 + t * speedMult * 2) % 3;
              const layerInt = 0.2 + 0.8 * (layerPhase < 1 ? layerPhase : (2 - layerPhase));
              kAlpha *= Math.min(1.0, layerInt);
              break;
            case 10: // Onda Senoidal (Sine Wave)
              const sineW = Math.sin(nx * 9 + t * speedMult * 4);
              kAlpha *= (0.25 + 0.75 * Math.max(0, sineW));
              break;
            case 11: // Mola (Spring)
              const springHue = (Math.sin(nx * 4 + t * speedMult * 3) * 180 + 180) % 360;
              [kr, kg, kb] = hsvToRgb(springHue, 1.0, 1.0);
              break;
            case 12: // Neon
              const neonCol = [ [0, 255, 255], [255, 0, 255], [255, 220, 0] ][(k.row + Math.floor(t * speedMult * 2)) % 3];
              [kr, kg, kb] = neonCol;
              break;
            case 14: // Radiante (Radiant)
              const radDist = Math.hypot(nx - 0.5, ny - 0.5);
              kAlpha *= Math.max(0.2, (0.5 + 0.5 * Math.sin(radDist * 10 - t * speedMult * 5)));
              break;
            case 15: // Loop
              const loopH = ((nx - ny + 1) * 180 + t * speedMult * 120) % 360;
              [kr, kg, kb] = hsvToRgb(loopH, 1.0, 1.0);
              break;
            case 16: // Grade de Cores (Color Grid)
              const gridHue = ((k.row * 60 + k.col * 35) + t * speedMult * 80) % 360;
              [kr, kg, kb] = hsvToRgb(gridHue, 1.0, 1.0);
              break;
            case 17: case 18: case 19: // Queda de Neve / Meteoro
              const dropPhase = (ny * 4 - t * speedMult * 3.5 + (k.col * 0.3)) % 1;
              const dropVal = dropPhase > 0 ? (1 - dropPhase) : 0;
              kAlpha *= Math.max(0.18, Math.pow(dropVal, 2.5));
              break;
            default:
              break;
          }

          // Apply Interactive Click Waves on Keys
          for (let r = 0; r < userRipples.length; r++) {
            const rip = userRipples[r];
            const elapsed = (now - rip.time) / 1000;
            const ripRadius = elapsed * 320;
            const d = Math.hypot(k.cx - rip.x, k.cy - rip.y);
            const waveDist = Math.abs(d - ripRadius);
            if (waveDist < 35) {
              const ripStrength = (1 - elapsed / 0.9) * (1 - waveDist / 35);
              kr = Math.min(255, kr + 180 * ripStrength);
              kg = Math.min(255, kg + 180 * ripStrength);
              kb = Math.min(255, kb + 255 * ripStrength);
              kAlpha = Math.min(1.0, kAlpha + ripStrength * 0.6);
            }
          }
        }

        // Fast geometric switch socket underglow halo
        if (kAlpha > 0.05) {
          roundRect(kbCtx, k.x - 1.5, k.y - 1.5, k.w + 3, k.h + 3, k.underR + 1.5);
          kbCtx.fillStyle = `rgba(${kr}, ${kg}, ${kb}, ${kAlpha * 0.32})`;
          kbCtx.fill();
        }

        // Keycap Body
        roundRect(kbCtx, k.x + 1.5, k.y + 1.5, k.w - 3, k.h - 3, k.capR);
        kbCtx.fillStyle = '#0f131c';
        kbCtx.fill();
        kbCtx.lineWidth = 1;
        kbCtx.strokeStyle = kAlpha > 0.05 ? `rgba(${kr}, ${kg}, ${kb}, ${kAlpha * 0.35})` : '#18202d';
        kbCtx.stroke();

        // Keycap Top Surface Bevel
        roundRect(kbCtx, k.x + 3, k.y + 3, k.w - 6, k.h - 6, k.innerR);
        kbCtx.fillStyle = kAlpha > 0.05 ? `rgba(${kr}, ${kg}, ${kb}, ${kAlpha * 0.18})` : '#131822';
        kbCtx.fill();

        // Keycap Legend Text
        if (k.isShortLegend !== currentFontShort) {
          currentFontShort = k.isShortLegend;
          kbCtx.font = currentFontShort ? '8.5px "JetBrains Mono", sans-serif' : '7.5px "JetBrains Mono", sans-serif';
        }
        kbCtx.fillStyle = kAlpha > 0.05 ? `rgba(${Math.min(255, kr + 100)}, ${Math.min(255, kg + 100)}, ${Math.min(255, kb + 100)}, ${Math.max(0.5, kAlpha)})` : '#5a677f';
        kbCtx.fillText(k.name, k.cx, k.cy);
      });
    }

    function renderKeyboardPreview() {
      drawKeyboardFrame(performance.now());
      if (kbAnimId !== null) {
        kbAnimId = setTimeout(renderKeyboardPreview, 33);
      }
    }

    function startKeyboardPreview() {
      if (kbAnimId === null) {
        kbAnimId = setTimeout(renderKeyboardPreview, 16);
      }
    }

    function stopKeyboardPreview() {
      if (kbAnimId !== null) {
        clearTimeout(kbAnimId);
        kbAnimId = null;
      }
    }
    // Interactive Key Click
    kbCanvas.addEventListener('click', (e) => {
      const rect = kbCanvas.getBoundingClientRect();
      const scaleX = kbCanvas.width / rect.width;
      const scaleY = kbCanvas.height / rect.height;
      const clickX = (e.clientX - rect.left) * scaleX;
      const clickY = (e.clientY - rect.top) * scaleY;
      userRipples.push({ x: clickX, y: clickY, time: performance.now() });
    });
