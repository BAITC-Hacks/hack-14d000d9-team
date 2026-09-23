(() => {
  const script = document.currentScript;
  if (!script || document.getElementById('ekt-assistant-frame')) return;
  const source = new URL(script.dataset.url || './?widget=1', script.src);
  source.searchParams.set('widget', '1');
  const frame = document.createElement('iframe');
  frame.id = 'ekt-assistant-frame';
  frame.title = 'EKT Assistant';
  frame.src = source.href;
  frame.style.cssText = 'position:fixed;bottom:8px;right:8px;width:84px;height:84px;border:0;background:transparent;z-index:2147483000;color-scheme:normal;';
  window.addEventListener('message', (event) => {
    if (event.origin !== source.origin || event.source !== frame.contentWindow || event.data?.type !== 'ekt-widget-size' || typeof event.data.open !== 'boolean') return;
    frame.style.width = event.data.open ? 'min(440px, calc(100vw - 16px))' : '84px';
    frame.style.height = event.data.open ? 'min(760px, calc(100dvh - 16px))' : '84px';
  });
  document.body.appendChild(frame);
})();
