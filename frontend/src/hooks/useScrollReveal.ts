import { useEffect } from 'react';

/**
 * Reveals `[data-reveal]` elements as they scroll into view, honouring an
 * optional `data-reveal-delay` (ms) for staggering siblings.
 *
 * Elements start hidden via the `.reveal` class in index.css, so nothing
 * flashes before the observer attaches. Users with `prefers-reduced-motion`
 * get the content immediately with no transform.
 */
export function useScrollReveal() {
  useEffect(() => {
    const els = Array.from(document.querySelectorAll<HTMLElement>('[data-reveal]'));
    if (els.length === 0) return;

    const reduced = window.matchMedia('(prefers-reduced-motion: reduce)').matches;
    const show = (el: HTMLElement) => el.classList.add('reveal-visible');

    if (reduced || typeof IntersectionObserver === 'undefined') {
      els.forEach(show);
      return;
    }

    const timers: number[] = [];
    const observer = new IntersectionObserver(
      (entries) => {
        entries.forEach((entry) => {
          if (!entry.isIntersecting) return;
          const el = entry.target as HTMLElement;
          const delay = Number(el.dataset.revealDelay ?? 0);
          timers.push(window.setTimeout(() => show(el), delay));
          observer.unobserve(el);
        });
      },
      { threshold: 0.12, rootMargin: '0px 0px -6% 0px' },
    );

    els.forEach((el) => observer.observe(el));

    // Safety net: content must never be left permanently invisible if the
    // observer somehow never fires.
    const fallback = window.setTimeout(() => els.forEach(show), 5000);

    return () => {
      observer.disconnect();
      timers.forEach(clearTimeout);
      clearTimeout(fallback);
    };
  }, []);
}
