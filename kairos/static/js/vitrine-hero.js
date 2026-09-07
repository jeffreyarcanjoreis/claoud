/* Logo 3D do hero público da vitrine do Kairos.
 *
 * Versão "protagonista" do logo (nítido, brilhante, presente), diferente da
 * versão ambiente do painel (apagada/desfocada via CSS em painel-fundo.js).
 * Reaproveita a mesma geometria/paleta, com giro chronos e reação ao mouse
 * mais vivos, coerente com mockups/vitrine-hero.html.
 *
 * Salvaguardas:
 *  - respeita prefers-reduced-motion (quadro estático, sem loop);
 *  - se o WebGL falhar, esconde o canvas e a página segue funcionando;
 *  - trata resize.
 *
 * Three.js é servido localmente (/static/vendor), sem CDN (coerente com a CSP).
 */
import * as THREE from '/static/vendor/three.module.min.js';

// Sinaliza que o JS está ativo: só então o CSS esconde as seções para revelá-las
// no scroll. Sem JS, as seções ficam visíveis (progressive enhancement).
document.documentElement.classList.add('js');

const canvas = document.getElementById('vitrine-logo');

if (canvas) {
  init();
}

setupReveals();
setupCadastroModal();

/* Revelação suave das seções ao entrar na viewport (independe do WebGL). */
function setupReveals() {
  const els = document.querySelectorAll('.reveal');
  if (!els.length) return;

  const reduce = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
  if (reduce || !('IntersectionObserver' in window)) {
    els.forEach((el) => el.classList.add('in-view'));
    return;
  }

  const io = new IntersectionObserver(
    (entries) => {
      entries.forEach((entry) => {
        if (entry.isIntersecting) {
          entry.target.classList.add('in-view');
          io.unobserve(entry.target);
        }
      });
    },
    { threshold: 0.15 }
  );
  els.forEach((el) => io.observe(el));
}

function init() {
  const reduceMotion = window.matchMedia('(prefers-reduced-motion: reduce)').matches;

  let renderer;
  try {
    renderer = new THREE.WebGLRenderer({ canvas, antialias: true, alpha: true });
  } catch (_e) {
    // Sem WebGL: esconde o canvas; o hero (texto + botões) continua funcionando.
    canvas.style.display = 'none';
    return;
  }

  renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
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

  const outer = new THREE.Group(); // recebe o tilt do mouse
  const spin = new THREE.Group();  // gira sozinho — chronos
  outer.add(spin); scene.add(outer);

  spin.add(new THREE.Mesh(new THREE.TorusGeometry(4.6, 0.05, 16, 160), gold)); // anel externo (chronos)
  spin.add(new THREE.Mesh(new THREE.TorusGeometry(3.4, 0.16, 20, 160), clay)); // o momento
  spin.add(new THREE.Mesh(new THREE.BoxGeometry(0.08, 6.8, 0.08), bone));      // linha de equilibrio
  const curve = new THREE.QuadraticBezierCurve3(
    new THREE.Vector3(0, 0, 0), new THREE.Vector3(2.0, 1.2, 0.35), new THREE.Vector3(1.4, 2.8, 0)
  );
  spin.add(new THREE.Mesh(new THREE.TubeGeometry(curve, 64, 0.13, 14, false), gold)); // o instante (topete)
  spin.add(new THREE.Mesh(new THREE.SphereGeometry(0.35, 32, 32), clay));             // centro

  const BASE_TILT = -0.28;
  outer.rotation.x = BASE_TILT; // ja le como 3D em repouso

  let tx = 0;
  let ty = 0;
  window.addEventListener('pointermove', (e) => {
    tx = (e.clientX / window.innerWidth - 0.5);
    ty = (e.clientY / window.innerHeight - 0.5);
  });

  function renderFrame() {
    renderer.render(scene, camera);
  }

  window.addEventListener('resize', () => {
    camera.aspect = window.innerWidth / window.innerHeight;
    camera.updateProjectionMatrix();
    renderer.setSize(window.innerWidth, window.innerHeight);
    renderFrame(); // mantem o quadro nitido mesmo se o loop estiver parado
  });

  if (reduceMotion) {
    renderFrame(); // um quadro estatico, sem loop
    window.__kairosVitrineReady = true;
    return;
  }

  function tick() {
    spin.rotation.y += 0.004; // chronos — vivo, protagonista
    outer.rotation.y += (tx * 0.9 - outer.rotation.y) * 0.05;
    outer.rotation.x += ((BASE_TILT + ty * 0.7) - outer.rotation.x) * 0.05;
    renderFrame();
    requestAnimationFrame(tick);
  }

  tick();
  window.__kairosVitrineReady = true;
}

/* Modal da Avaliação Inicial: abre sobre a vitrine e envia por fetch, com
 * fallback pro envio normal do formulário (que leva pra /comecar) se a rede
 * falhar. Sem JS, os links [data-abre-cadastro] continuam navegando pra
 * /comecar normalmente (progressive enhancement). */
function setupCadastroModal() {
  const modal = document.getElementById('cadastro-modal');
  const form = document.getElementById('cadastro-form');
  if (!modal || !form) return;

  const card = modal.querySelector('.v-modal-card');
  const erro = document.getElementById('cadastro-erro');
  const sucesso = document.getElementById('cadastro-sucesso');
  const gatilhos = document.querySelectorAll('[data-abre-cadastro]');
  const fechadores = modal.querySelectorAll('[data-fecha-cadastro]');

  let elementoQueAbriu = null;

  function abrirModal(gatilho) {
    elementoQueAbriu = gatilho || null;
    modal.hidden = false;
    modal.setAttribute('aria-hidden', 'false');
    const primeiroCampo = form.querySelector('input, textarea, select');
    if (primeiroCampo) primeiroCampo.focus();
  }

  function fecharModal() {
    modal.hidden = true;
    modal.setAttribute('aria-hidden', 'true');
    if (elementoQueAbriu && typeof elementoQueAbriu.focus === 'function') {
      elementoQueAbriu.focus();
    }
    elementoQueAbriu = null;
  }

  function resetarForm() {
    form.hidden = false;
    form.reset();
    if (erro) erro.hidden = true;
    if (sucesso) sucesso.hidden = true;
  }

  gatilhos.forEach((gatilho) => {
    gatilho.addEventListener('click', (e) => {
      e.preventDefault();
      abrirModal(gatilho);
    });
  });

  fechadores.forEach((el) => {
    el.addEventListener('click', () => {
      fecharModal();
      resetarForm();
    });
  });

  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && !modal.hidden) {
      fecharModal();
      resetarForm();
    }
  });

  // impede que um clique dentro do card feche o modal (o backdrop já cuida disso)
  if (card) {
    card.addEventListener('click', (e) => e.stopPropagation());
  }

  form.addEventListener('submit', (e) => {
    e.preventDefault();
    if (erro) erro.hidden = true;

    const fd = new FormData(form);

    fetch('/comecar', {
      method: 'POST',
      body: fd,
      headers: {
        Accept: 'application/json',
        'X-Requested-With': 'fetch',
      },
    })
      .then((res) => res.json().then((json) => ({ ok: res.ok, json })))
      .then(({ ok, json }) => {
        if (ok && json && json.ok) {
          form.hidden = true;
          if (erro) erro.hidden = true;
          if (sucesso) sucesso.hidden = false;
        } else {
          const msg = (json && json.error) || 'Não foi possível enviar seu cadastro. Tente de novo.';
          if (erro) {
            erro.textContent = msg;
            erro.hidden = false;
          }
        }
      })
      .catch(() => {
        // falha de rede: cai pro envio normal do formulário (fallback /comecar)
        form.submit();
      });
  });
}
