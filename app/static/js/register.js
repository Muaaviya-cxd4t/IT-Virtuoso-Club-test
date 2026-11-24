document.addEventListener("DOMContentLoaded", () => {
    const form = document.getElementById("registrationForm");
    const rows = document.getElementById("memberRows");
    const add = document.getElementById("addMember");
    const hidden = document.getElementById("membersJson");
    const error = document.getElementById("formError");
    const submit = form.querySelector(".submit-button");
    const limits = window.EVENT_LIMITS || { min: 1, max: 1 };

    function template(index) {
        return `
        <div class="member-row">
            <div class="member-row-top">
                <span>MEMBER ${String(index).padStart(2, "0")}</span>
                <button type="button" class="remove" aria-label="Remove member">Remove</button>
            </div>
            <div class="member-fields">
                <label class="field-label">Name
                    <input class="member-name" maxlength="100" required placeholder="Full name" autocomplete="name">
                </label>
                <label class="field-label">USN
                    <input class="usn" placeholder="1GAXXXXXXX" maxlength="10" required autocomplete="off" autocapitalize="characters">
                </label>
                <label class="field-label">Phone
                    <input class="phone" placeholder="10-digit number" inputmode="numeric" maxlength="10" required autocomplete="tel">
                </label>
            </div>
        </div>`;
    }

    function refresh() {
        const count = rows.children.length;
        add.disabled = count >= limits.max;
        add.textContent = count >= limits.max ? "Maximum members reached" : "+ Add Member";
        [...rows.querySelectorAll(".member-row")].forEach((row, i) => {
            row.querySelector(".member-row-top span").textContent = `MEMBER ${String(i + 1).padStart(2, "0")}`;
            row.querySelector(".remove").style.visibility = count > limits.min ? "visible" : "hidden";
        });
    }

    function addRow() {
        if (rows.children.length >= limits.max) return;
        rows.insertAdjacentHTML("beforeend", template(rows.children.length + 1));
        refresh();
        rows.lastElementChild?.querySelector(".member-name")?.focus();
    }

    function setError(message) {
        error.textContent = message || "";
        error.classList.toggle("has-error", Boolean(message));
    }

    function collect() {
        const members = [];
        const seen = new Set();

        for (const row of rows.querySelectorAll(".member-row")) {
            const nameInput = row.querySelector(".member-name");
            const usnInput = row.querySelector(".usn");
            const phoneInput = row.querySelector(".phone");
            const name = nameInput.value.trim();
            const usn = usnInput.value.trim().toUpperCase();
            const phone = phoneInput.value.replace(/\D/g, "");

            nameInput.value = name;
            usnInput.value = usn;
            phoneInput.value = phone;

            if (!name) throw new Error("Enter the name of every team member.");
            if (!/^1GA\d{2}[A-Z]{2}\d{3}$/.test(usn)) {
                throw new Error(`Invalid USN: ${usn || "blank"}. Use the format 1GAXXXXXXX.`);
            }
            if (!/^\d{10}$/.test(phone)) {
                throw new Error(`Phone number for ${usn} must contain exactly 10 digits.`);
            }
            if (seen.has(usn)) throw new Error(`Duplicate USN detected: ${usn}`);

            seen.add(usn);
            members.push({ name, usn, phone });
        }

        if (members.length < limits.min || members.length > limits.max) {
            throw new Error(`This event requires ${limits.min}–${limits.max} members.`);
        }

        return members;
    }

    add.addEventListener("click", () => {
        setError("");
        addRow();
    });

    rows.addEventListener("input", (event) => {
        if (event.target.matches(".usn")) event.target.value = event.target.value.toUpperCase();
        if (event.target.matches(".phone")) event.target.value = event.target.value.replace(/\D/g, "").slice(0, 10);
    });

    rows.addEventListener("click", (event) => {
        if (!event.target.classList.contains("remove")) return;
        if (rows.children.length <= limits.min) {
            setError(`At least ${limits.min} members are required.`);
            return;
        }
        event.target.closest(".member-row").remove();
        setError("");
        refresh();
    });

    form.addEventListener("submit", async (event) => {
        event.preventDefault();
        setError("");

        const teamName = form.elements.team_name.value.trim();
        if (!teamName) {
            setError("Enter a team name before continuing.");
            form.elements.team_name.focus();
            return;
        }

        let members;
        try {
            members = collect();
            hidden.value = JSON.stringify(members);
        } catch (err) {
            setError(err.message);
            return;
        }

        submit.disabled = true;
        submit.classList.add("is-loading");
        submit.innerHTML = "Saving registration…";

        try {
            const response = await fetch(form.action || window.location.href, {
                method: "POST",
                headers: { "Content-Type": "application/x-www-form-urlencoded; charset=UTF-8" },
                body: new URLSearchParams(new FormData(form))
            });
            const data = await response.json();

            if (!response.ok || !data.ok) {
                throw new Error(data.error || "Unable to save registration.");
            }

            window.location.href = data.redirect_url;
        } catch (err) {
            submit.disabled = false;
            submit.classList.remove("is-loading");
            submit.innerHTML = 'Continue to payment <span>↗</span>';
            setError(err.message || "Something went wrong. Please try again.");
        }
    });

    for (let i = 0; i < limits.min; i++) addRow();
});
