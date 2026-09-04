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

/* ── Copy referral link ── */
function copyReferralLink() {
  const link = document.getElementById('referralLink').textContent;
  navigator.clipboard.writeText(link).then(() => {
    const copyText = document.getElementById('copyText');
    copyText.textContent = 'Copied!';
    setTimeout(() => { copyText.textContent = 'Copy'; }, 2000);
  });
}
