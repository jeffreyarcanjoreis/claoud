/* Fundo 3D ambiente do painel do Kairos.
 *
 * Traz o logo do Kairos em 3D (o mesmo do hero da vitrine) para o fundo do
 * painel, na versão "ambiente" definida no doc 07: apagado e desfocado (via
 * CSS), lento, atrás do conteúdo legível. Salvaguardas de ferramenta diária:
 *  - botão "pausar fundo" (estado lembrado no localStorage);
 *  - pausa sozinho quando a aba está oculta (bateria);
 *  - respeita prefers-reduced-motion (fica estático);
 *  - se o WebGL falhar, some sem quebrar o app.
 *
 * Three.js é servido localmente (/static/vendor), sem CDN (coerente com a CSP).
 */
import * as THREE from '/static/vendor/three.module.min.js';

const STORAGE_KEY = 'kairos-fundo-3d';

const canvas = document.getElementById('fundo3d');
const toggle = document.getElementById('fundo-toggle');
if (canvas) {
  init();
}

function readStored() {
  try {
    return localStorage.getItem(STORAGE_KEY);
  } catch (_e) {
    return null;
  }
}

function writeStored(value) {
  try {
    localStorage.setItem(STORAGE_KEY, value);
  } catch (_e) {
    /* modo privado / storage bloqueado: segue sem lembrar */
  }
}

function init() {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  } catch (_e) {
    // Sem WebGL: esconde o fundo e o botão; o app continua igual.
    canvas.style.display = 'none';
    if (toggle) toggle.style.display = 'none';
    return;
  }

  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 1.75));
  renderer.setSize(window.innerWidth, window.innerHeight);

  const scene = new THREE.Scene();
  const camera = new THREE.PerspectiveCamera(45, window.innerWidth / window.innerHeight, 0.1, 100);
  camera.position.set(0, 0, 13);

  // luzes quentes para o ouro brilhar
  scene.add(new THREE.AmbientLight(0xf0ebe0, 0.55));
  const key = new THREE.PointLight(0xc89b4a, 90, 100); key.position.set(6, 7, 9); scene.add(key);
  const fill = new THREE.PointLight(0xc2613f, 45, 100); fill.position.set(-7, -4, 5); scene.add(fill);
  const rim = new THREE.DirectionalLight(0xf0ebe0, 0.6); rim.position.set(0, 2, -6); scene.add(rim);

  const gold = new THREE.MeshStandardMaterial({ color: 0xc89b4a, metalness: 0.9, roughness: 0.32 });
  const clay = new THREE.MeshStandardMaterial({ color: 0xc2613f, metalness: 0.35, roughness: 0.55 });
  const bone = new THREE.MeshStandardMaterial({ color: 0xf0ebe0, metalness: 0.1, roughness: 0.85, transparent: true, opacity: 0.55 });

  const outer = new THREE.Group();  // recebe o tilt do mouse
  const spin = new THREE.Group();   // gira sozinho — chronos
  outer.add(spin); scene.add(outer);

  spin.add(new THREE.Mesh(new THREE.TorusGeometry(4.6, 0.05, 16, 160), gold));   // anel externo (chronos)
  spin.add(new THREE.Mesh(new THREE.TorusGeometry(3.4, 0.16, 20, 160), clay));   // o momento
  spin.add(new THREE.Mesh(new THREE.BoxGeometry(0.08, 6.8, 0.08), bone));        // linha de equilíbrio
  const curve = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(0, 0, 0), new THREE.Vector3(2.0, 1.2, 0.35), new THREE.Vector3(1.4, 2.8, 0)
  );
  spin.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 64, 0.13, 14, false), gold)); // o instante (topete)
  spin.add(new THREE.Mesh(new THREE.SphereGeometry(0.35, 32, 32), clay));             // centro

  const BASE_TILT = -0.28;
  outer.rotation.x = BASE_TILT; // já lê como 3D em repouso

  let tx = 0, ty = 0;
  window.addEventListener('pointermove', (e) => {
    tx = (e.clientX / window.innerWidth - 0.5);
    ty = (e.clientY / window.innerHeight - 0.5);
  });

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    if (!animating) renderer.render(scene, camera); // mantém o quadro estático nítido
  });

  // Estado: animando ou pausado. Reduced-motion => pausado por padrão.
  // Caso contrário, respeita o que ficou guardado (padrão: animando).
  let animating = reduceMotion ? false : readStored() !== 'paused';
  let rafId = null;

  function renderStatic() {
    renderer.render(scene, camera);
  }

  function tick() {
    spin.rotation.y += 0.0015; // lento — chronos
    outer.rotation.y += (tx * 0.6 - outer.rotation.y) * 0.04;
    outer.rotation.x += ((BASE_TILT + ty * 0.4) - outer.rotation.x) * 0.04;
    renderer.render(scene, camera);
    rafId = requestAnimationFrame(tick);
  }

  function startLoop() {
    if (rafId === null && animating && !document.hidden) {
      rafId = requestAnimationFrame(tick);
    }
  }

  function stopLoop() {
    if (rafId !== null) {
      cancelAnimationFrame(rafId);
      rafId = null;
    }
  }

  document.addEventListener('visibilitychange', () => {
    if (document.hidden) {
      stopLoop();
    } else if (animating) {
      startLoop();
    }
  });

  function syncToggle() {
    if (!toggle) return;
    toggle.textContent = animating ? 'pausar fundo' : 'retomar fundo';
    toggle.setAttribute('aria-pressed', String(!animating));
  }

  if (toggle) {
    toggle.hidden = false;
    toggle.addEventListener('click', () => {
      animating = !animating;
      writeStored(animating ? 'playing' : 'paused');
      syncToggle();
      if (animating) startLoop();
      else { stopLoop(); renderStatic(); }
    });
  }

  syncToggle();
  renderStatic();     // primeiro quadro (visível mesmo pausado)
  if (animating) startLoop();

  window.__kairosFundoReady = true;
}
