import { useEffect } from "react";

/**
 * Observes every element with `class="reveal"` inside the document and
 * adds `reveal-in` the first time it enters the viewport. This is the
 * scroll-triggered fade-up effect used across the landing page — done
 * with the native IntersectionObserver API so we don't pull in any
 * animation library.
 */
export function useScrollReveal(): void {
  useEffect(() => {
    const targets = Array.from(document.querySelectorAll<HTMLElement>(".reveal"));
    if (targets.length === 0) return;

    // If the user has asked the OS for reduced motion, reveal everything
    // immediately so the page isn't a blank blob of content.
    const prefersReducedMotion = window.matchMedia(
      "(prefers-reduced-motion: reduce)",
    ).matches;
    if (prefersReducedMotion) {
      for (const t of targets) t.classList.add("reveal-in");
      return;
    }

    const observer = new IntersectionObserver(
      (entries) => {
        for (const entry of entries) {
          if (entry.isIntersecting) {
            entry.target.classList.add("reveal-in");
            observer.unobserve(entry.target);
          }
        }
      },
      { threshold: 0.15, rootMargin: "0px 0px -40px 0px" },
    );

    for (const t of targets) observer.observe(t);
    return () => observer.disconnect();
  }, []);
}
