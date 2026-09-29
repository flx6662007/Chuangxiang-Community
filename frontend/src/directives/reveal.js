const observers = new WeakMap()

export default {
  mounted(element) {
    if (!('IntersectionObserver' in window) || window.matchMedia('(prefers-reduced-motion: reduce)').matches) return

    const observer = new IntersectionObserver(([entry]) => {
      if (!entry.isIntersecting) return
      element.classList.add('is-revealed')
      observer.unobserve(element)
      observers.delete(element)
    }, { threshold: 0.08, rootMargin: '0px 0px -24px 0px' })

    observers.set(element, observer)
    element.setAttribute('data-reveal-ready', '')
    observer.observe(element)
  },
  unmounted(element) {
    observers.get(element)?.disconnect()
    observers.delete(element)
  },
}
