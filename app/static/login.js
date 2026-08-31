const loginForm = document.querySelector('#login-form');
const errorNode = document.querySelector('#login-error');

loginForm.addEventListener('submit', async (event) => {
  event.preventDefault();
  errorNode.textContent = '';
  const form = new FormData(loginForm);
  const response = await fetch('/api/auth/login', {
    method: 'POST',
    headers: {'Content-Type': 'application/json'},
    body: JSON.stringify({username: form.get('username'), password: form.get('password'), mfa_code: form.get('mfa_code') || null}),
  });
  const payload = await response.json().catch(() => ({}));
  if (!response.ok) {
    errorNode.textContent = payload.detail || '登录失败，请稍后重试。';
    return;
  }
  if (payload.security_notice) window.sessionStorage.setItem('login-security-notice', payload.security_notice);
  window.location.assign('/');
});

window.addEventListener('load', () => window.lucide?.createIcons());
