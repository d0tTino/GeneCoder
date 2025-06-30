import glossary from '@docs/glossary.json';

function escapeRegex(str) {
  return str.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
}

export function applyGlossary(container = document.body) {
  const terms = Object.keys(glossary);
  if (!terms.length) return;
  const pattern = new RegExp(terms.sort((a,b) => b.length - a.length).map(escapeRegex).join('|'), 'g');

  const walker = document.createTreeWalker(container, NodeFilter.SHOW_TEXT);
  const nodes = [];
  while (walker.nextNode()) {
    const node = walker.currentNode;
    if (node.parentNode && node.nodeValue.trim()) nodes.push(node);
  }

  for (const node of nodes) {
    const html = node.nodeValue.replace(pattern, (m) => `<span class="glossary-term" data-term="${m}">${m}</span>`);
    if (html !== node.nodeValue) {
      const span = document.createElement('span');
      span.innerHTML = html;
      node.parentNode.replaceChild(span, node);
    }
  }

  for (const el of container.querySelectorAll('.glossary-term')) {
    const term = el.dataset.term;
    const def = glossary[term];
    el.title = def;
    el.style.textDecoration = 'underline dotted';
    el.style.cursor = 'help';
    el.addEventListener('click', () => showOverlay(term, def));
  }
}

function showOverlay(term, definition) {
  let overlay = document.getElementById('glossary-overlay');
  if (!overlay) {
    overlay = document.createElement('div');
    overlay.id = 'glossary-overlay';
    Object.assign(overlay.style, {
      position: 'fixed',
      top: 0,
      left: 0,
      right: 0,
      bottom: 0,
      background: 'rgba(0,0,0,0.5)',
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      zIndex: 1000,
    });
    overlay.addEventListener('click', () => overlay.remove());
    document.body.appendChild(overlay);
  } else {
    overlay.innerHTML = '';
    overlay.style.display = 'flex';
  }
  const box = document.createElement('div');
  Object.assign(box.style, {
    background: '#fff',
    padding: '1em',
    borderRadius: '8px',
    maxWidth: '600px',
  });
  box.addEventListener('click', (e) => e.stopPropagation());
  box.innerHTML = `<h3>${term}</h3><p>${definition}</p>`;
  overlay.appendChild(box);
}

export default applyGlossary;
