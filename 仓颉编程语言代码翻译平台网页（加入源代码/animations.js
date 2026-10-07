// animations.js — 卡片进入视口时交错淡入（配合 animations.css）
// IntersectionObserver 只触发一次；prefers-reduced-motion 时整体跳过。
(function () {
  if (!("IntersectionObserver" in window)) {
    return;
  }
  if (window.matchMedia("(prefers-reduced-motion: reduce)").matches) {
    return;
  }

  const CARD_SELECTOR = ".panel, .home-product-card, .home-support-card, .history-stat";
  const cards = Array.from(document.querySelectorAll(CARD_SELECTOR));
  if (!cards.length) {
    return;
  }

  document.documentElement.classList.add("anim-ready");

  const observer = new IntersectionObserver((entries) => {
    // 同一批进入视口的卡片按 DOM 顺序依次延迟 60ms，最多 420ms
    const entering = entries.filter((entry) => entry.isIntersecting);
    entering.forEach((entry, index) => {
      const card = entry.target;
      card.style.setProperty("--stagger", `${Math.min(index * 60, 420)}ms`);
      card.classList.add("card-in");
      observer.unobserve(card);
    });
  }, { threshold: 0.12, rootMargin: "0px 0px -24px 0px" });

  cards.forEach((card) => {
    card.setAttribute("data-card", "");
    observer.observe(card);
  });
})();
