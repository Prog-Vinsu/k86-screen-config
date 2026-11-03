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
        FLAT_KEYS.push({
          ...k,
          y: rg.y,
          h: rg.h,
          row: rIdx,
          col: cIdx,
          cx: k.x + k.w / 2,
          cy: rg.y + rg.h / 2
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

    function renderKeyboardPreview(now) {
      const dt = (now - lastAnimTime) / 1000;
      lastAnimTime = now;
      const t = now / 1000;

      const mode = parseInt(document.getElementById('selLedMode').value, 10);
      const speedVal = parseInt(document.getElementById('sliderSpeed').value, 10);
      const speedMult = [0.4, 0.7, 1.0, 1.5, 2.2][speedVal] || 1.0;
      const rawBrt = parseInt(document.getElementById('sliderBrightness').value, 10);
      const isLedOff = document.getElementById('switchLedOff')?.checked;
      const brt = isLedOff ? 0 : rawBrt / 4.0;

      const smode = parseInt(document.getElementById('selSledMode').value, 10);
      const sspeedVal = parseInt(document.getElementById('sliderSledSpeed').value, 10);
      const sspeedMult = [0.4, 0.7, 1.0, 1.5, 2.2][sspeedVal] || 1.0;
      const rawSbrt = parseInt(document.getElementById('sliderSledBrightness').value, 10);
      const isSledOff = document.getElementById('switchSideLedOff')?.checked;
      const sbrt = (isSledOff || smode === 0) ? 0 : rawSbrt / 4.0;

      // Update indicator labels
      const selModeText = document.getElementById('selLedMode').options[document.getElementById('selLedMode').selectedIndex]?.text || '';
      const selSledText = document.getElementById('selSledMode').options[document.getElementById('selSledMode').selectedIndex]?.text || '';
      document.getElementById('previewKeyModeLabel').textContent = selModeText.split('(')[0].trim();
      document.getElementById('previewSideModeLabel').textContent = selSledText.split('(')[0].trim();
      document.getElementById('previewSpeedLabel').textContent = `${speedVal}`;
      document.getElementById('previewStatusText').textContent = brt === 0 ? 'Backlight Desligado' : (isRainbow ? 'Modo Arco-íris' : 'Cor Customizada');

      // Clear canvas
      kbCtx.clearRect(0, 0, kbCanvas.width, kbCanvas.height);

      // 1. Draw Keyboard Chassis
      const chassisX = 10, chassisY = 8, chassisW = 660, chassisH = 214, chassisR = 14;
      roundRect(kbCtx, chassisX, chassisY, chassisW, chassisH, chassisR);
      kbCtx.fillStyle = '#0a0d13';
      kbCtx.fill();
      kbCtx.lineWidth = 1.5;
      kbCtx.strokeStyle = '#1e2638';
      kbCtx.stroke();

      // Inner Plate Bevel
      roundRect(kbCtx, chassisX + 8, chassisY + 6, chassisW - 16, chassisH - 12, 8);
      kbCtx.fillStyle = '#0f131c';
      kbCtx.fill();

      // 2. Draw Side LED Strips (Left & Right Chassis Borders)
      const drawSideStrip = (x, isRight) => {
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

            // Diffuse Edge Glow
            kbCtx.save();
            kbCtx.shadowColor = `rgba(${sr}, ${sg}, ${sb}, ${sAlpha * 0.7})`;
            kbCtx.shadowBlur = 8;
            roundRect(kbCtx, x, sy, stripW, segH - 1, 2);
            kbCtx.fillStyle = `rgba(${sr}, ${sg}, ${sb}, ${sAlpha * 0.9})`;
            kbCtx.fill();
            kbCtx.restore();
          }
        } else {
          // Unlit Side Strip Groove
          roundRect(kbCtx, x, stripY, stripW, stripH, 2);
          kbCtx.fillStyle = '#141822';
          kbCtx.fill();
        }
      };

      drawSideStrip(13, false);
      drawSideStrip(663, true);

      // 3. Draw Signature K86 Hardware Cluster (TFT Screen + Volume Knob)
      // A. TFT Bezel & Screen
      const tftX = 552, tftY = 16, tftW = 56, tftH = 32;
      roundRect(kbCtx, tftX, tftY, tftW, tftH, 4);
      kbCtx.fillStyle = '#05070a';
      kbCtx.fill();
      kbCtx.lineWidth = 1;
      kbCtx.strokeStyle = '#232b3d';
      kbCtx.stroke();

      // TFT Screen Content simulation
      roundRect(kbCtx, tftX + 3, tftY + 3, tftW - 6, tftH - 6, 2);
      kbCtx.fillStyle = '#030814';
      kbCtx.fill();

      // Tiny animated pixel wave on the TFT
      kbCtx.save();
      kbCtx.beginPath();
      for (let px = 0; px < tftW - 6; px += 2) {
        const py = tftY + 16 + Math.sin(px * 0.3 + t * 4) * 4;
        if (px === 0) kbCtx.moveTo(tftX + 3 + px, py);
        else kbCtx.lineTo(tftX + 3 + px, py);
      }
      kbCtx.strokeStyle = '#00d2ff';
      kbCtx.lineWidth = 1.2;
      kbCtx.stroke();
      kbCtx.restore();

      // Screen Glass Glare
      kbCtx.save();
      kbCtx.beginPath();
      kbCtx.moveTo(tftX + 3, tftY + 3);
      kbCtx.lineTo(tftX + 28, tftY + 3);
      kbCtx.lineTo(tftX + 3, tftY + 24);
      kbCtx.closePath();
      kbCtx.fillStyle = 'rgba(255, 255, 255, 0.08)';
      kbCtx.fill();
      kbCtx.restore();

      // B. Rotary Knob
      const knobX = 636, knobY = 32, knobR = 14;
      kbCtx.save();
      kbCtx.beginPath();
      kbCtx.arc(knobX, knobY, knobR, 0, Math.PI * 2);
      kbCtx.fillStyle = '#161c28';
      kbCtx.fill();
      kbCtx.lineWidth = 1.5;
      kbCtx.strokeStyle = '#2e394e';
      kbCtx.stroke();

      // Inner knurled surface
      kbCtx.beginPath();
      kbCtx.arc(knobX, knobY, knobR - 3, 0, Math.PI * 2);
      kbCtx.fillStyle = '#0d1117';
      kbCtx.fill();

      // Rotary dot indicator
      const dotAngle = (t * 0.8) % (Math.PI * 2);
      const dotX = knobX + Math.cos(dotAngle) * 7;
      const dotY = knobY + Math.sin(dotAngle) * 7;
      kbCtx.beginPath();
      kbCtx.arc(dotX, dotY, 1.5, 0, Math.PI * 2);
      kbCtx.fillStyle = '#f59e0b';
      kbCtx.fill();
      kbCtx.restore();

      // Clean expired user ripples
      while (userRipples.length > 0 && now - userRipples[0].time > 900) {
        userRipples.shift();
      }

      // 4. Draw All Keys & Dynamic Backlight
      const totalKeys = FLAT_KEYS.length;
      FLAT_KEYS.forEach((k, idx) => {
        const nx = (k.cx - 26) / 500;
        const ny = (k.cy - 18) / 184;

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

        // Switch socket underglow halo (organic RGB bloom)
        if (kAlpha > 0.05) {
          kbCtx.save();
          kbCtx.shadowColor = `rgba(${kr}, ${kg}, ${kb}, ${kAlpha * 0.75})`;
          kbCtx.shadowBlur = 10;
          const underR = Math.min(k.w, k.h) * 0.36;
          roundRect(kbCtx, k.x, k.y, k.w, k.h, underR);
          kbCtx.fillStyle = `rgba(${kr}, ${kg}, ${kb}, ${kAlpha * 0.45})`;
          kbCtx.fill();
          kbCtx.restore();
        }

        // Keycap Body
        const capR = Math.min(k.w, k.h) * 0.32;
        roundRect(kbCtx, k.x + 1.5, k.y + 1.5, k.w - 3, k.h - 3, capR);
        kbCtx.fillStyle = '#0f131c';
        kbCtx.fill();
        kbCtx.lineWidth = 1;
        kbCtx.strokeStyle = kAlpha > 0.05 ? `rgba(${kr}, ${kg}, ${kb}, ${kAlpha * 0.35})` : '#18202d';
        kbCtx.stroke();

        // Keycap Top Surface Bevel
        const innerR = Math.min(k.w, k.h) * 0.28;
        roundRect(kbCtx, k.x + 3, k.y + 3, k.w - 6, k.h - 6, innerR);
        kbCtx.fillStyle = kAlpha > 0.05 ? `rgba(${kr}, ${kg}, ${kb}, ${kAlpha * 0.18})` : '#131822';
        kbCtx.fill();

        // Keycap Legend Text
        kbCtx.font = k.name.length > 3 ? '7.5px "JetBrains Mono", sans-serif' : '8.5px "JetBrains Mono", sans-serif';
        kbCtx.textAlign = 'center';
        kbCtx.textBaseline = 'middle';
        kbCtx.fillStyle = kAlpha > 0.05 ? `rgba(${Math.min(255, kr + 100)}, ${Math.min(255, kg + 100)}, ${Math.min(255, kb + 100)}, ${Math.max(0.5, kAlpha)})` : '#5a677f';
        kbCtx.fillText(k.name, k.cx, k.cy);
      });

      kbAnimId = requestAnimationFrame(renderKeyboardPreview);
    }

    function startKeyboardPreview() {
      if (!kbAnimId) {
        lastAnimTime = performance.now();
        kbAnimId = requestAnimationFrame(renderKeyboardPreview);
      }
    }

    function stopKeyboardPreview() {
      if (kbAnimId) {
        cancelAnimationFrame(kbAnimId);
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
