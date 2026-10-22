// Trang làm bài: đếm ngược, tự lưu từng câu, đánh dấu câu đã làm, tự nộp khi hết giờ.
(function () {
  const form = document.getElementById('exam-form');
  const timer = document.getElementById('timer');
  const state = document.getElementById('save-state');
  const end = Date.now() + Number(timer.dataset.remaining) * 1000;   // máy chủ quyết định giờ nộp; đây chỉ để hiển thị
  let submitting = false;

  const pad = n => String(n).padStart(2, '0');
  const chosen = pos => [...form.querySelectorAll(`input[name="q${pos}"]:checked`)].map(i => Number(i.value));

  function submit(auto) {
    if (submitting) return;
    submitting = true;
    document.getElementById('auto').value = auto ? '1' : '0';
    form.submit();
  }

  function tick() {
    const left = Math.max(0, Math.round((end - Date.now()) / 1000));
    const h = Math.floor(left / 3600), m = Math.floor(left % 3600 / 60), s = left % 60;
    timer.textContent = (h ? h + ':' + pad(m) : pad(m)) + ':' + pad(s);
    timer.classList.toggle('warn', left <= 300 && left > 60);
    timer.classList.toggle('danger', left <= 60);
    if (left === 0) submit(true);
  }

  function refreshNav() {
    let n = 0;
    form.querySelectorAll('.nav-grid a').forEach(a => {
      const done = chosen(a.dataset.pos).length > 0;
      a.classList.toggle('done', done);
      n += done;
    });
    document.getElementById('answered').textContent = n;
    return n;
  }

  async function save(pos) {
    state.textContent = 'Đang lưu…';
    try {
      const r = await fetch(form.dataset.saveUrl, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json', 'X-CSRF-Token': form.dataset.csrf },
        body: JSON.stringify({ pos: Number(pos), selected: chosen(pos) }),
      });
      const d = await r.json();
      if (d.finished) { submitting = true; location.href = d.redirect; return; }
      state.textContent = d.ok ? 'Đã lưu lúc ' + new Date().toLocaleTimeString('vi-VN') : (d.error || 'Chưa lưu được');
    } catch (e) {
      state.textContent = 'Mất kết nối. Đáp án vẫn được gửi khi bấm Nộp bài.';
    }
  }

  form.addEventListener('change', e => {
    const q = e.target.closest('.question');
    if (!q) return;
    refreshNav();
    save(q.dataset.pos);
  });

  document.getElementById('submit-btn').addEventListener('click', () => {
    const left = form.querySelectorAll('.question').length - refreshNav();
    const msg = left ? `Bạn còn ${left} câu chưa trả lời. Vẫn nộp bài?` : 'Nộp bài? Sau khi nộp sẽ không sửa được nữa.';
    if (confirm(msg)) submit(false);
  });

  window.addEventListener('beforeunload', e => {
    if (!submitting) { e.preventDefault(); e.returnValue = ''; }
  });

  refreshNav();
  tick();
  setInterval(tick, 500);
})();
