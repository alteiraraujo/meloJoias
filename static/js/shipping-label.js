(() => {
  const button = document.getElementById('postal-print');
  if (!button) return;
  const fit = () => {
    document.body.classList.remove('postal-overflow');
    let fits = true;
    document.querySelectorAll('.postal-address').forEach(block => {
      let size = block.closest('.postal-sender') ? 10 : 11;
      block.style.fontSize = `${size}pt`;
      while (block.scrollHeight > block.clientHeight + 1 && size > 9) {
        size -= .25; block.style.fontSize = `${size}pt`;
      }
      if (block.scrollHeight > block.clientHeight + 1 || block.scrollWidth > block.clientWidth + 1) fits = false;
    });
    document.body.classList.toggle('postal-overflow', !fits);
    document.getElementById('postal-fit-error').hidden = fits;
    button.disabled = !fits;
    return fits;
  };
  button.addEventListener('click', () => { if (fit()) window.print(); });
  window.addEventListener('beforeprint', fit);
  window.addEventListener('resize', fit);
  document.fonts.ready.then(fit);
})();
