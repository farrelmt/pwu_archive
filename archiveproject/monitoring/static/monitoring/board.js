(() => {
  let dragged = null;
  document.querySelectorAll('.assignment-card[draggable="true"]').forEach((card) => {
    card.addEventListener('dragstart', (event) => {
      dragged = card;
      event.dataTransfer.effectAllowed = 'move';
      event.dataTransfer.setData('text/plain', card.querySelector('h3')?.textContent || 'Tugas');
      card.classList.add('dragging');
    });
    card.addEventListener('dragend', () => {
      card.classList.remove('dragging');
      dragged = null;
      document.querySelectorAll('.board-column').forEach((column) => column.classList.remove('drop-target'));
    });
  });
  document.querySelectorAll('.board-column').forEach((column) => {
    column.addEventListener('dragover', (event) => {
      if (!dragged) return;
      event.preventDefault();
      column.classList.add('drop-target');
    });
    column.addEventListener('dragleave', () => column.classList.remove('drop-target'));
    column.addEventListener('drop', async (event) => {
      if (!dragged) return;
      event.preventDefault();
      column.classList.remove('drop-target');
      const form = dragged.querySelector('.status-form');
      const status = column.dataset.status;
      if (!form || !status || form.querySelector('select').value === status) return;
      const data = new FormData(form);
      data.set('status', status);
      try {
        const response = await fetch(form.action, {method: 'POST', body: data, credentials: 'same-origin'});
        if (!response.ok) throw new Error('Gagal memindahkan tugas');
        window.location.reload();
      } catch {
        form.querySelector('select').value = status;
        form.submit();
      }
    });
  });
})();
