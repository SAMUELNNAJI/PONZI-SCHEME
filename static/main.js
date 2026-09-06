/* ============================================================
   Premium Wallet — Main JavaScript
   ============================================================ */

document.addEventListener('DOMContentLoaded', () => {

  /* ── Invest now buttons → signup ── */
  document.querySelectorAll('.btn-invest').forEach(btn => {
    btn.addEventListener('click', () => {
      window.location.href = 'signup.html';
    });
  });

  /* ── Scroll-in animation for plan cards ── */
  const observer = new IntersectionObserver((entries) => {
    entries.forEach(entry => {
      if (entry.isIntersecting) {
        entry.target.style.opacity   = '1';
        entry.target.style.transform = 'translateY(0)';
        observer.unobserve(entry.target);
      }
    });
  }, { threshold: 0.12 });

  document.querySelectorAll('.plan-card').forEach((card, i) => {
    card.style.opacity    = '0';
    card.style.transform  = 'translateY(24px)';
    card.style.transition = `opacity 0.45s ease ${i * 0.08}s, transform 0.45s ease ${i * 0.08}s`;
    observer.observe(card);
  });

  /* ── Smooth scroll for internal anchor links ── */
  document.querySelectorAll('a[href^="#"]').forEach(anchor => {
    anchor.addEventListener('click', e => {
      const target = document.querySelector(anchor.getAttribute('href'));
      if (target) {
        e.preventDefault();
        target.scrollIntoView({ behavior: 'smooth' });
      }
    });
  });

});

/* ── Toggle password visibility ── */
function togglePassword(btn) {
  const wrapper = btn.parentElement;
  const input = wrapper.querySelector('input');
  if (input.type === 'password') {
    input.type = 'text';
    btn.textContent = '🙈';
  } else {
    input.type = 'password';
    btn.textContent = '👁';
  }
}

/* ── Eye-icon password toggle (login / signup / settings) ── */
function togglePw(btn) {
  const wrapper = btn.closest('.password-wrapper');
  const input = wrapper.querySelector('input');
  const isHidden = input.type === 'password';
  input.type = isHidden ? 'text' : 'password';
  btn.classList.toggle('active', isHidden);
  // Swap between eye and eye-off path
  const svg = btn.querySelector('svg');
  if (isHidden) {
    // Showing — strikethrough eye
    svg.innerHTML = '<path d="M17.94 17.94A10.07 10.07 0 0 1 12 20c-7 0-11-8-11-8a18.45 18.45 0 0 1 5.06-5.94M9.9 4.24A9.12 9.12 0 0 1 12 4c7 0 11 8 11 8a18.5 18.5 0 0 1-2.16 3.19"/><line x1="1" y1="1" x2="23" y2="23"/>';
  } else {
    // Hidden — open eye
    svg.innerHTML = '<path d="M1 12s4-8 11-8 11 8 11 8-4 8-11 8-11-8-11-8z"/><circle cx="12" cy="12" r="3"/>';
  }
}

/* ── Copy referral link (legacy) ── */
function copyReferralLink() {
  const link = document.getElementById('referralLink').textContent;
  navigator.clipboard.writeText(link).then(() => {
    const copyText = document.getElementById('copyText');
    copyText.textContent = 'Copied!';
    setTimeout(() => { copyText.textContent = 'Copy'; }, 2000);
  });
}

/* ── Generic clipboard copy (used by referral card) ── */
function copyToClipboard(text, btn) {
  navigator.clipboard.writeText(text.trim()).then(() => {
    const original = btn.textContent;
    btn.textContent = 'Copied!';
    setTimeout(() => { btn.textContent = original; }, 2000);
  });
}

/* ── Copy text from a span by ID ── */
function copySpan(spanId, btn) {
  const el = document.getElementById(spanId);
  if (!el) return;
  const text = el.textContent.trim();

  // Update button text immediately — don't wait for async clipboard
  btn.textContent = 'Copied!';
  setTimeout(() => { btn.textContent = 'Copy'; }, 2000);

  // Attempt clipboard write (best-effort)
  if (navigator.clipboard && navigator.clipboard.writeText) {
    navigator.clipboard.writeText(text).catch(() => fallbackCopy(text));
  } else {
    fallbackCopy(text);
  }
}

function fallbackCopy(text) {
  const ta = document.createElement('textarea');
  ta.value = text;
  ta.style.position = 'fixed';
  ta.style.top = '0';
  ta.style.left = '0';
  ta.style.opacity = '0';
  document.body.appendChild(ta);
  ta.focus();
  ta.select();
  try { document.execCommand('copy'); } catch (e) {}
  document.body.removeChild(ta);
}
