/* Painel — modal das Tarefas (Início).
 *
 * Progressive enhancement: o modal já abre/fecha sem JS (checkbox nativo
 * #tarefas-toggle, ver painel/inicio.html). Este script só adiciona:
 *  - Esc fecha o modal;
 *  - os forms (adicionar / concluir / remover) passam a usar fetch, trocando
 *    apenas a lista de tarefas e a contagem do tile, sem recarregar a página.
 *
 * Falha de rede em qualquer fetch cai para o submit normal do form
 * (fallback), que leva pro redirect/render de sempre.
 */

const toggle = document.getElementById('tarefas-toggle');
const addForm = document.getElementById('tarefa-add-form');
const listaContainer = document.getElementById('tarefas-lista-container');
const erro = document.getElementById('tarefa-erro');
const tile = document.querySelector('label.stat-toggle[for="tarefas-toggle"] .n');

if (toggle) {
  document.addEventListener('keydown', (e) => {
    if (e.key === 'Escape' && toggle.checked) {
      toggle.checked = false;
    }
  });
}

if (addForm && listaContainer) {
  setupAjax();
}

function setupAjax() {
  addForm.addEventListener('submit', (e) => {
    e.preventDefault();
    enviar(addForm, () => {
      addForm.reset();
    });
  });

  // delegação de evento: a lista é re-renderizada a cada atualização, então
  // os forms de concluir/remover dentro dela mudam de referência.
  listaContainer.addEventListener('submit', (e) => {
    const form = e.target.closest('form');
    if (!form) return;
    e.preventDefault();
    enviar(form);
  });
}

function enviar(form, aoOk) {
  if (erro) erro.hidden = true;

  const fd = new FormData(form);

  fetch(form.action, {
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
        if (aoOk) aoOk();
        return atualizarLista();
      }
      const msg = (json && json.error) || 'Não foi possível concluir a ação. Tente de novo.';
      mostrarErro(msg);
    })
    .catch(() => {
      // falha de rede: cai pro envio normal do form (fallback)
      form.submit();
    });
}

function atualizarLista() {
  return fetch('/tarefas/fragmento', {
    headers: { Accept: 'text/html' },
  })
    .then((res) => res.text())
    .then((html) => {
      listaContainer.innerHTML = html;
      atualizarContagem();
    })
    .catch(() => {
      // não conseguiu atualizar a lista via AJAX: recarrega a página inteira
      window.location.reload();
    });
}

function atualizarContagem() {
  if (!tile) return;
  const total = listaContainer.querySelectorAll('.tarefa-card').length;
  tile.textContent = String(total);
}

function mostrarErro(msg) {
  if (!erro) return;
  erro.textContent = msg;
  erro.hidden = false;
}
