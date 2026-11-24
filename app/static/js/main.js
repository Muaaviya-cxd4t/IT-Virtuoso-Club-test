document.addEventListener("DOMContentLoaded", () => {
    const slides = [...document.querySelectorAll(".slide")];
    const dots = [...document.querySelectorAll(".dot")];
    const next = document.querySelector(".slider-arrow.next");
    const prev = document.querySelector(".slider-arrow.prev");

    if (slides.length) {
        let current = 0;
        let timer;

        function show(index) {
            current = (index + slides.length) % slides.length;
            slides.forEach((slide, i) => slide.classList.toggle("active", i === current));
            dots.forEach((dot, i) => dot.classList.toggle("active", i === current));
        }

        function start() {
            clearInterval(timer);
            timer = setInterval(() => show(current + 1), 5000);
        }

        next?.addEventListener("click", () => { show(current + 1); start(); });
        prev?.addEventListener("click", () => { show(current - 1); start(); });
        dots.forEach(dot => dot.addEventListener("click", () => { show(Number(dot.dataset.slide)); start(); }));
        start();
    }

    document.querySelectorAll(".countdown").forEach(el => {
        const target = new Date(el.dataset.countdown).getTime();

        function update() {
            const diff = target - Date.now();
            if (diff <= 0) {
                el.textContent = "Registration closed";
                el.classList.add("urgent");
                return;
            }

            const days = Math.floor(diff / 86400000);
            const hours = Math.floor((diff % 86400000) / 3600000);
            const minutes = Math.floor((diff % 3600000) / 60000);
            const seconds = Math.floor((diff % 60000) / 1000);

            el.textContent = `Closes in ${days}d ${hours}h ${minutes}m ${seconds}s`;
            if (diff < 172800000) el.classList.add("urgent");
        }

        update();
        setInterval(update, 1000);
    });
});
