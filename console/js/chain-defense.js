/**
 * chain-defense.js -- Hidden arcade easter egg activated by the Konami code.
 *
 * The player controls a "verifier" ship that fires SHA-256 verification
 * pulses upward to destroy descending "corruption agents" before they
 * reach the hash chain blocks at the bottom of the screen.
 *
 * Five waves (one per bank: BANK_A through BANK_E), increasing speed
 * and agent count. Educational tooltips appear when blocks are hit.
 *
 * Controls: Left/Right arrows to move, Space to fire, Escape to exit.
 * Activated by: Up Up Down Down Left Right Left Right B A (Konami code).
 *
 * Pure Canvas 2D — no external dependencies, no API calls.
 */

const ChainDefense = (() => {

  const KONAMI = [
    'ArrowUp','ArrowUp','ArrowDown','ArrowDown',
    'ArrowLeft','ArrowRight','ArrowLeft','ArrowRight',
    'KeyB','KeyA'
  ];

  let _konamiPos = 0;
  let _game = null;

  // Bank colors (from variables.css palette)
  const BANK_COLORS = ['#22c55e','#3b82f6','#f59e0b','#ef4444','#8b5cf6'];
  const BANK_NAMES = ['BANK_A','BANK_B','BANK_C','BANK_D','BANK_E'];

  /* ── Konami Code Detector ──────────────────────────────────── */

  function handleKeyDown(e) {
    // Don't activate if an overlay is visible
    if (document.querySelector('.popup-overlay[style*="display: none"]') === null &&
        document.querySelector('.popup-overlay:not(#chainDefenseOverlay)')) {
      // Check if any visible overlay exists
      const overlays = document.querySelectorAll('.popup-overlay');
      for (const o of overlays) {
        if (o.id === 'chainDefenseOverlay') continue;
        if (o.style.display !== 'none') { _konamiPos = 0; return; }
      }
    }

    if (e.code === KONAMI[_konamiPos]) {
      _konamiPos++;
      if (_konamiPos === KONAMI.length) {
        _konamiPos = 0;
        startGame();
      }
    } else {
      _konamiPos = 0;
    }
  }

  /* ── Game Engine ───────────────────────────────────────────── */

  function startGame() {
    if (_game) return;

    const overlay = document.createElement('div');
    overlay.id = 'chainDefenseOverlay';
    overlay.style.cssText = 'position:fixed;top:0;left:0;width:100vw;height:100vh;z-index:9999;background:rgba(0,0,0,0.92);';

    const canvas = document.createElement('canvas');
    canvas.style.cssText = 'width:100%;height:100%;display:block;';
    overlay.appendChild(canvas);
    document.body.appendChild(overlay);

    const ctx = canvas.getContext('2d');

    function resize() {
      canvas.width = window.innerWidth;
      canvas.height = window.innerHeight;
    }
    resize();
    window.addEventListener('resize', resize);

    _game = {
      overlay, canvas, ctx, resize,
      running: true,
      showHelp: true,
      wave: 0,
      score: 0,
      player: { x: canvas.width / 2, y: canvas.height - 60, w: 40, h: 20, speed: 6 },
      bullets: [],
      agents: [],
      blocks: [],
      particles: [],
      stars: [],
      keys: {},
      cooldown: 0,
      spawnTimer: 0,
      waveAgents: 0,
      waveSpawned: 0,
      message: null,
      messageTimer: 0,
      victory: false,
      defeat: false,
      raf: null,
    };

    // Generate starfield
    for (let i = 0; i < 60; i++) {
      _game.stars.push({
        x: Math.random() * canvas.width,
        y: Math.random() * canvas.height,
        s: Math.random() * 1.5 + 0.5,
        a: Math.random() * 0.5 + 0.3,
      });
    }

    // Generate hash chain blocks (10 blocks across the bottom)
    const blockW = Math.min(60, (canvas.width - 100) / 10);
    const blockGap = 8;
    const totalBlockW = 10 * blockW + 9 * blockGap;
    const startX = (canvas.width - totalBlockW) / 2;

    for (let i = 0; i < 10; i++) {
      _game.blocks.push({
        x: startX + i * (blockW + blockGap),
        y: canvas.height - 30,
        w: blockW,
        h: 16,
        alive: true,
        color: BANK_COLORS[Math.floor(i / 2)],
        flash: 0,
      });
    }

    // Key handlers
    const keyDown = (e) => { _game.keys[e.code] = true; if (e.code === 'Escape') endGame(); if (_game.showHelp) { _game.showHelp = false; startWave(1); } e.preventDefault(); };
    const keyUp = (e) => { _game.keys[e.code] = false; };
    document.addEventListener('keydown', keyDown);
    document.addEventListener('keyup', keyUp);
    _game._keyDown = keyDown;
    _game._keyUp = keyUp;

    if (typeof Utils !== 'undefined') {
      Utils.showToast('EASTER EGG UNLOCKED: Chain Defense', 'success');
    }

    _game.raf = requestAnimationFrame(gameLoop);
  }

  function startWave(n) {
    if (!_game) return;
    _game.wave = n;
    _game.waveAgents = 6 + n * 4; // 10, 14, 18, 22, 26
    _game.waveSpawned = 0;
    _game.spawnTimer = 0;
    _game.agents = [];
    _game.message = `WAVE ${n}: ${BANK_NAMES[n - 1]}`;
    _game.messageTimer = 90;
  }

  function gameLoop() {
    if (!_game || !_game.running) return;
    update();
    draw();
    _game.raf = requestAnimationFrame(gameLoop);
  }

  function update() {
    const g = _game;
    const W = g.canvas.width;
    const H = g.canvas.height;

    if (g.showHelp || g.victory || g.defeat) return;

    // Message timer
    if (g.messageTimer > 0) g.messageTimer--;

    // Player movement
    if (g.keys['ArrowLeft']) g.player.x = Math.max(g.player.w / 2, g.player.x - g.player.speed);
    if (g.keys['ArrowRight']) g.player.x = Math.min(W - g.player.w / 2, g.player.x + g.player.speed);

    // Fire
    g.cooldown = Math.max(0, g.cooldown - 1);
    if (g.keys['Space'] && g.cooldown === 0) {
      g.bullets.push({ x: g.player.x, y: g.player.y - g.player.h / 2, speed: 8 });
      g.cooldown = 10;
    }

    // Spawn agents
    if (g.waveSpawned < g.waveAgents) {
      g.spawnTimer++;
      const spawnRate = Math.max(8, 30 - g.wave * 4);
      if (g.spawnTimer >= spawnRate) {
        g.spawnTimer = 0;
        g.agents.push({
          x: 40 + Math.random() * (W - 80),
          y: -20,
          w: 20, h: 16,
          speed: 0.8 + g.wave * 0.3 + Math.random() * 0.3,
          wobble: Math.random() * Math.PI * 2,
        });
        g.waveSpawned++;
      }
    }

    // Move bullets
    g.bullets.forEach(b => b.y -= b.speed);
    g.bullets = g.bullets.filter(b => b.y > -10);

    // Move agents
    g.agents.forEach(a => {
      a.y += a.speed;
      a.wobble += 0.05;
      a.x += Math.sin(a.wobble) * 0.5;
    });

    // Bullet-agent collision
    g.bullets = g.bullets.filter(b => {
      for (let i = g.agents.length - 1; i >= 0; i--) {
        const a = g.agents[i];
        if (b.x > a.x - a.w / 2 && b.x < a.x + a.w / 2 &&
            b.y > a.y - a.h / 2 && b.y < a.y + a.h / 2) {
          // Hit!
          g.agents.splice(i, 1);
          g.score += 10 * g.wave;
          // Particles
          for (let p = 0; p < 5; p++) {
            g.particles.push({
              x: a.x, y: a.y,
              vx: (Math.random() - 0.5) * 4,
              vy: (Math.random() - 0.5) * 4,
              life: 20 + Math.random() * 10,
              color: '#ef4444',
            });
          }
          return false;
        }
      }
      return true;
    });

    // Agent-block collision
    g.agents = g.agents.filter(a => {
      for (const block of g.blocks) {
        if (!block.alive) continue;
        if (a.x > block.x && a.x < block.x + block.w &&
            a.y + a.h / 2 > block.y) {
          block.alive = false;
          block.flash = 30;
          g.message = 'Block corrupted! In a real hash chain, this invalidates all subsequent blocks.';
          g.messageTimer = 120;
          return false;
        }
      }
      // Agent reached bottom without hitting block
      if (a.y > H + 20) return false;
      return true;
    });

    // Particles
    g.particles.forEach(p => { p.x += p.vx; p.y += p.vy; p.life--; });
    g.particles = g.particles.filter(p => p.life > 0);

    // Block flash decay
    g.blocks.forEach(b => { if (b.flash > 0) b.flash--; });

    // Check defeat
    const aliveBlocks = g.blocks.filter(b => b.alive).length;
    if (aliveBlocks === 0) {
      g.defeat = true;
      return;
    }

    // Check wave complete
    if (g.waveSpawned >= g.waveAgents && g.agents.length === 0) {
      if (g.wave >= 5) {
        g.victory = true;
      } else {
        startWave(g.wave + 1);
      }
    }
  }

  function draw() {
    const g = _game;
    const ctx = g.ctx;
    const W = g.canvas.width;
    const H = g.canvas.height;

    ctx.clearRect(0, 0, W, H);

    // Starfield
    g.stars.forEach(s => {
      ctx.fillStyle = `rgba(255, 255, 255, ${s.a})`;
      ctx.fillRect(s.x, s.y, s.s, s.s);
    });

    // Help screen
    if (g.showHelp) {
      ctx.fillStyle = '#e2e8f0';
      ctx.font = 'bold 28px "Inter", sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('CHAIN DEFENSE', W / 2, H / 2 - 80);
      ctx.font = '16px "Inter", sans-serif';
      ctx.fillStyle = '#94a3b8';
      ctx.fillText('Defend the hash chain from corruption agents', W / 2, H / 2 - 40);
      ctx.fillText('\u2190 \u2192  Move    Space  Fire    Esc  Exit', W / 2, H / 2 + 10);
      ctx.fillText('5 waves \u2014 one per bank. Don\'t let them reach the chain.', W / 2, H / 2 + 40);
      ctx.fillStyle = '#22c55e';
      ctx.fillText('Press any key to start', W / 2, H / 2 + 90);
      return;
    }

    // Hash chain blocks
    g.blocks.forEach(b => {
      if (b.alive) {
        ctx.fillStyle = b.color;
        ctx.globalAlpha = 0.8;
        ctx.fillRect(b.x, b.y, b.w, b.h);
        ctx.globalAlpha = 1;
        ctx.strokeStyle = b.color;
        ctx.strokeRect(b.x, b.y, b.w, b.h);
      } else {
        ctx.fillStyle = 'rgba(100, 116, 139, 0.3)';
        ctx.fillRect(b.x, b.y, b.w, b.h);
        if (b.flash > 0) {
          ctx.fillStyle = `rgba(239, 68, 68, ${b.flash / 30 * 0.5})`;
          ctx.fillRect(b.x - 2, b.y - 2, b.w + 4, b.h + 4);
        }
        // Crack lines
        ctx.strokeStyle = '#64748b';
        ctx.lineWidth = 1;
        ctx.beginPath();
        ctx.moveTo(b.x + b.w * 0.3, b.y);
        ctx.lineTo(b.x + b.w * 0.5, b.y + b.h * 0.6);
        ctx.lineTo(b.x + b.w * 0.7, b.y + b.h);
        ctx.stroke();
      }
    });

    // Chain links between blocks
    ctx.strokeStyle = 'rgba(255, 255, 255, 0.1)';
    ctx.lineWidth = 1;
    for (let i = 0; i < g.blocks.length - 1; i++) {
      const a = g.blocks[i], b = g.blocks[i + 1];
      ctx.beginPath();
      ctx.moveTo(a.x + a.w, a.y + a.h / 2);
      ctx.lineTo(b.x, b.y + b.h / 2);
      ctx.stroke();
    }

    // Player (verifier ship — triangle)
    const p = g.player;
    ctx.fillStyle = '#22c55e';
    ctx.beginPath();
    ctx.moveTo(p.x, p.y - p.h / 2);
    ctx.lineTo(p.x - p.w / 2, p.y + p.h / 2);
    ctx.lineTo(p.x + p.w / 2, p.y + p.h / 2);
    ctx.closePath();
    ctx.fill();

    // Bullets (SHA-256 pulses — small bright rectangles)
    ctx.fillStyle = '#22c55e';
    g.bullets.forEach(b => {
      ctx.fillRect(b.x - 1.5, b.y - 6, 3, 12);
    });

    // Agents (corruption — red diamonds)
    g.agents.forEach(a => {
      ctx.fillStyle = '#ef4444';
      ctx.beginPath();
      ctx.moveTo(a.x, a.y - a.h / 2);
      ctx.lineTo(a.x + a.w / 2, a.y);
      ctx.lineTo(a.x, a.y + a.h / 2);
      ctx.lineTo(a.x - a.w / 2, a.y);
      ctx.closePath();
      ctx.fill();
    });

    // Particles
    g.particles.forEach(p => {
      ctx.fillStyle = p.color;
      ctx.globalAlpha = p.life / 30;
      ctx.fillRect(p.x - 1, p.y - 1, 3, 3);
    });
    ctx.globalAlpha = 1;

    // HUD
    const aliveBlocks = g.blocks.filter(b => b.alive).length;
    const integrity = Math.round(aliveBlocks / g.blocks.length * 100);

    ctx.fillStyle = '#e2e8f0';
    ctx.font = '14px "JetBrains Mono", monospace';
    ctx.textAlign = 'left';
    ctx.fillText(`SCORE: ${g.score}`, 20, 30);
    ctx.fillText(`WAVE: ${g.wave}/5  ${BANK_NAMES[g.wave - 1] || ''}`, 20, 50);

    ctx.textAlign = 'right';
    ctx.fillStyle = integrity > 60 ? '#22c55e' : integrity > 30 ? '#f59e0b' : '#ef4444';
    ctx.fillText(`INTEGRITY: ${integrity}%`, W - 20, 30);

    // Wave message
    if (g.messageTimer > 0 && g.message) {
      ctx.textAlign = 'center';
      ctx.font = '14px "Inter", sans-serif';
      ctx.fillStyle = `rgba(226, 232, 240, ${Math.min(1, g.messageTimer / 30)})`;
      ctx.fillText(g.message, W / 2, 80);
    }

    // Victory screen
    if (g.victory) {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#22c55e';
      ctx.font = 'bold 32px "Inter", sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('ALL CHAINS VERIFIED', W / 2, H / 2 - 40);
      ctx.font = '18px "Inter", sans-serif';
      ctx.fillStyle = '#e2e8f0';
      ctx.fillText(`Integrity preserved across all 5 banks. Score: ${g.score}`, W / 2, H / 2 + 10);
      ctx.fillStyle = '#94a3b8';
      ctx.font = '14px "Inter", sans-serif';
      ctx.fillText('Press Escape to exit', W / 2, H / 2 + 50);
    }

    // Defeat screen
    if (g.defeat) {
      ctx.fillStyle = 'rgba(0, 0, 0, 0.6)';
      ctx.fillRect(0, 0, W, H);
      ctx.fillStyle = '#ef4444';
      ctx.font = 'bold 32px "Inter", sans-serif';
      ctx.textAlign = 'center';
      ctx.fillText('CHAIN COMPROMISED', W / 2, H / 2 - 40);
      ctx.font = '18px "Inter", sans-serif';
      ctx.fillStyle = '#e2e8f0';
      ctx.fillText(`All blocks corrupted. Score: ${g.score}`, W / 2, H / 2 + 10);
      ctx.fillStyle = '#94a3b8';
      ctx.font = '14px "Inter", sans-serif';
      ctx.fillText('Press Escape to exit', W / 2, H / 2 + 50);
    }
  }

  function endGame() {
    if (!_game) return;

    _game.running = false;
    cancelAnimationFrame(_game.raf);
    document.removeEventListener('keydown', _game._keyDown);
    document.removeEventListener('keyup', _game._keyUp);
    window.removeEventListener('resize', _game.resize);
    _game.overlay.remove();
    _game = null;
    _konamiPos = 0;
  }

  /* ── Init ──────────────────────────────────────────────────── */

  function init() {
    document.addEventListener('keydown', handleKeyDown);
  }

  return { init };

})();
