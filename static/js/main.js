// Theme
(function () {
    const saved = localStorage.getItem("theme") || "dark";
    document.documentElement.setAttribute("data-theme", saved);
})();

function updateThemeButton() {
    const btn = document.getElementById("theme-btn");
    if (!btn) return;
    const theme = document.documentElement.getAttribute("data-theme") || "dark";
    btn.textContent = theme === "dark" ? "[ LIGHT ]" : "[ DARK ]";
}

function toggleTheme() {
    const curr = document.documentElement.getAttribute("data-theme");
    const next = curr === "dark" ? "light" : "dark";
    document.documentElement.setAttribute("data-theme", next);
    localStorage.setItem("theme", next);
    updateThemeButton();
}

// Matrix rain
let _matrixBooted = false;

function initMatrixRain() {
    const canvas = document.getElementById("matrix-canvas");
    if (!canvas || _matrixBooted) return;
    _matrixBooted = true;

    const ctx = canvas.getContext("2d");
    let width = 0;
    let height = 0;
    let drops = [];
    const fontSize = 18;
    const characters = "0101010011010010010101110010110";

    function resize() {
        width = canvas.width = window.innerWidth;
        height = canvas.height = window.innerHeight;
        const columns = Math.max(1, Math.floor(width / fontSize));
        drops = Array(columns).fill(1);
    }

    function draw() {
        ctx.fillStyle = document.documentElement.getAttribute("data-theme") === "light"
            ? "rgba(233, 237, 247, 0.12)"
            : "rgba(7, 9, 15, 0.18)";
        ctx.fillRect(0, 0, width, height);
        ctx.font = `${fontSize}px "Roboto Mono", monospace`;

        for (let i = 0; i < drops.length; i++) {
            const char = characters[Math.floor(Math.random() * characters.length)];
            if (Math.random() > 0.28) {
                ctx.fillStyle = "#00ff7f";
                ctx.shadowColor = "#00ff7f";
            } else {
                ctx.fillStyle = "#ff00ff";
                ctx.shadowColor = "#ff00ff";
            }
            ctx.shadowBlur = 10;
            ctx.fillText(char, i * fontSize, drops[i] * fontSize);
            ctx.shadowBlur = 0;

            if (drops[i] * fontSize > height && Math.random() > 0.975) {
                drops[i] = 0;
            }
            drops[i]++;
        }
    }

    resize();
    window.addEventListener("resize", resize);
    setInterval(draw, 55);
}

// Timer
let _timerInterval = null;

function startTimer(initialRemaining) {
    const el = document.getElementById("timer");
    if (!el) return;

    let remaining = initialRemaining;

    function tick() {
        if (remaining <= 0) {
            clearInterval(_timerInterval);
            el.textContent = "00:00:00";
            el.className = "timer-display danger";
            fetch("/api/time").then((r) => r.json()).then((d) => {
                if (d.over) window.location.href = "/timesup";
                else window.location.reload();
            });
            return;
        }

        const h = Math.floor(remaining / 3600);
        const m = Math.floor((remaining % 3600) / 60);
        const s = remaining % 60;
        el.textContent =
            String(h).padStart(2, "0") + ":" +
            String(m).padStart(2, "0") + ":" +
            String(s).padStart(2, "0");
        el.className =
            remaining <= 300 ? "timer-display danger" :
            remaining <= 600 ? "timer-display warn" :
            "timer-display";
        remaining--;
    }

    tick();
    _timerInterval = setInterval(tick, 1000);

    setInterval(() => {
        fetch("/api/time").then((r) => r.json()).then((d) => {
            if (d.over) {
                window.location.href = "/timesup";
                return;
            }
            remaining = d.remaining;
        });
    }, 30000);
}

// Password toggle
function togglePassword(inputId, btn) {
    const inp = document.getElementById(inputId);
    if (!inp) return;
    inp.type = inp.type === "password" ? "text" : "password";
    btn.textContent = inp.type === "password" ? "show" : "hide";
}

function togglePwd(inputId, btn) {
    const inp = document.getElementById(inputId);
    if (!inp) return;
    inp.type = inp.type === "password" ? "text" : "password";
    btn.textContent = inp.type === "password" ? "hide" : "show";
}

// Answer submission
async function submitAnswer(questionId, formEl) {
    const input = formEl.querySelector("input[name='answer']");
    const resultEl = formEl.parentElement.querySelector(".answer-result");
    const btn = formEl.querySelector("button[type='submit']");
    const questionCard = formEl.closest(".question-card");

    if (!input || !resultEl || !btn || !questionCard) return;
    if (formEl.dataset.submitting === "true") return;

    let answer = input.value.trim();
    if (!answer) {
        resultEl.textContent = "Please enter an answer.";
        resultEl.className = "answer-result incorrect";
        return;
    }

    if (answer.toLowerCase().startsWith("flag{") && answer.endsWith("}")) {
        answer = answer.slice(5, -1);
    }

    formEl.dataset.submitting = "true";
    btn.disabled = true;
    btn.textContent = "Checking...";
    resultEl.textContent = "";

    const body = new FormData();
    body.append("question_id", questionId);
    body.append("answer", answer);

    try {
        const response = await fetch("/submit", { method: "POST", body });
        const contentType = response.headers.get("content-type") || "";
        const payload = contentType.includes("application/json")
            ? await response.json()
            : { status: "error", message: await response.text() };

        if (!response.ok) {
            throw new Error(payload.message || `HTTP ${response.status}`);
        }

        switch (payload.status) {
            case "correct": {
                resultEl.textContent = "Correct: " + payload.message;
                resultEl.className = "answer-result correct";
                input.disabled = true;
                btn.disabled = true;
                btn.textContent = "Solved";
                questionCard.classList.add("solved");

                const scoreEl = document.getElementById("nav-score");
                if (scoreEl) scoreEl.textContent = payload.score;

                if (payload.round2_unlocked) {
                    const banner = document.getElementById("unlock-banner");
                    if (banner) banner.style.display = "flex";
                }
                break;
            }

            case "already_solved":
                resultEl.textContent = "Solved: " + payload.message;
                resultEl.className = "answer-result already";
                input.disabled = true;
                btn.disabled = true;
                btn.textContent = "Solved";
                questionCard.classList.add("solved");
                break;

            case "incorrect":
                resultEl.textContent = "Incorrect: " + payload.message;
                resultEl.className = "answer-result incorrect";
                input.value = "";
                input.focus();
                break;

            case "event_over":
                resultEl.textContent = "Time up: " + payload.message;
                resultEl.className = "answer-result incorrect";
                input.disabled = true;
                break;

            case "not_assigned":
                resultEl.textContent = "Warning: " + payload.message;
                resultEl.className = "answer-result incorrect";
                break;

            default:
                resultEl.textContent = "Warning: " + (payload.message || "Unknown error");
                resultEl.className = "answer-result incorrect";
                break;
        }
    } catch (error) {
        console.error("Submit failed:", error);
        resultEl.textContent = "Connection error: " + error.message;
        resultEl.className = "answer-result incorrect";
    } finally {
        formEl.dataset.submitting = "false";
        if (!input.disabled) {
            btn.disabled = false;
            btn.textContent = "Submit";
        }
    }
}

// Clue toggle
function toggleClues(btn, listId) {
    const list = document.getElementById(listId);
    if (!list) return;
    const open = list.classList.toggle("open");
    btn.textContent = open ? "[ hide clues ]" : "[ show clues ]";
}

// Leaderboard live
let _leaderboardStarted = false;

function startLeaderboardRefresh() {
    const tbody = document.getElementById("lb-body");
    if (!tbody || _leaderboardStarted) return;
    _leaderboardStarted = true;

    function refresh() {
        fetch("/api/leaderboard").then((r) => r.json()).then((teams) => {
            tbody.innerHTML = "";
            teams.forEach((t) => {
                const rankClass = t.rank === 1 ? "rank-1" : (t.rank === 2 ? "rank-2" : (t.rank === 3 ? "rank-3" : "rank"));
                const tr = document.createElement("tr");
                tr.innerHTML = `
                    <td class="${rankClass}">#${t.rank}</td>
                    <td><strong>${t.team_name}</strong><br><span style="font-size:0.7rem;color:var(--muted)">${t.team_id}</span></td>
                    <td style="color:var(--accent);font-weight:bold">${t.score}</td>
                    <td style="color:var(--muted);font-weight:bold">${t.last_solve_elapsed || "-"}</td>
                `;
                tbody.appendChild(tr);
            });
        }).catch((err) => console.error("Leaderboard refresh failed:", err));
    }

    refresh();
    setInterval(refresh, 10000);
}

// Init
document.addEventListener("DOMContentLoaded", () => {
    updateThemeButton();
    initMatrixRain();

    const themeBtn = document.getElementById("theme-btn");
    if (themeBtn) {
        themeBtn.addEventListener("click", toggleTheme);
    }

    document.querySelectorAll(".answer-form").forEach((form) => {
        form.addEventListener("submit", (e) => {
            e.preventDefault();
            submitAnswer(form.dataset.questionId, form);
        });
    });

    startLeaderboardRefresh();
});
