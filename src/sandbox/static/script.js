const Base_url = "http://127.0.0.1:8000";

const runbtn = document.getElementById("run-btn");
const code_input = document.getElementById("code-input");
const stdouttext = document.getElementById("stdout-text");
const stderrtext = document.getElementById("stderr-text");
const statustext = document.getElementById("status-text");
const stdouttab = document.getElementById("stdout");
const stderrtab = document.getElementById("stderr");
const statustab = document.getElementById("status");
const tabs = document.querySelectorAll(".tab");
const langselect = document.getElementById("language");
const prevlang = document.getElementById("lang-prev");
const nextlang = document.getElementById("lang-next");
const highlight = document.getElementById("tab-highlight");

// ------------------ Chuyển ngôn ngữ ------------------
prevlang.addEventListener("click", () => {
    let index = langselect.selectedIndex;
    if (index > 0) {
        langselect.selectedIndex = index - 1;
        onLanguageChange();
    }
});

nextlang.addEventListener("click", () => {
    let index = langselect.selectedIndex;
    if (index < langselect.options.length - 1) {
        langselect.selectedIndex = index + 1;
        onLanguageChange();
    }
});

// Khi chọn ngôn ngữ từ dropdown
langselect.addEventListener("change", onLanguageChange);

function onLanguageChange() {
    const lang = langselect.value;
    if (lang === "python") {
        code_input.placeholder = "Nhập code Python tại đây...";
    } else if (lang === "go") {
        code_input.placeholder = "Nhập code Go tại đây...";
    } else {
        code_input.placeholder = "Nhập code tại đây...";
    }
}

// ------------------ Tabs (stdout / stderr / status) ------------------
tabs.forEach(tab => {
    tab.addEventListener("click", () => {
        const tabname = tab.getAttribute("data-tab");
        ChangeTab(tabname);
        moveHighlight(tab);
    });
});

function moveHighlight(activeTab) {
    const rect = activeTab.getBoundingClientRect();
    const containerRect = activeTab.parentElement.getBoundingClientRect();

    highlight.style.width = rect.width + "px";
    highlight.style.left = (rect.left - containerRect.left) + "px";
}
moveHighlight(document.querySelector(".tab.active"));

// ------------------ API helpers ------------------
async function create_job(entry, code, lang) {
    const rest = await fetch(`${Base_url}/jobs`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ entry, code, lang }),
    });

    if (!rest.ok) {
        const errData = await rest.json().catch(() => ({}));
        const message = errData.detail || "Create job failed";
        throw new Error(message);
    }

    const data = await rest.json();
    return data.job_id;
}

async function runjob(jobid) {
    const rest = await fetch(`${Base_url}/jobs/${jobid}/run`, {
        method: "POST",
    });

    if (!rest.ok) {
        const errData = await rest.json().catch(() => ({}));
        const message = errData.detail || "Run job failed";
        throw new Error(message);
    }

    const data = await rest.json();
    return data.ok;
}

async function getjob(jobid) {
    const rest = await fetch(`${Base_url}/jobs/${jobid}`);
    if (!rest.ok) {
        throw new Error("Get job failed");
    }
    const data = await rest.json();
    return data;
}

async function getLog(jobid) {
    const rest = await fetch(`${Base_url}/jobs/${jobid}/logs`);
    if (!rest.ok) {
        throw new Error("Get log failed");
    }
    const data = await rest.json();
    return data;
}

function Displaylog(Logs, status) {
    const { stdout, stderr } = Logs;
    stdouttext.textContent = stdout || "No result";
    stderrtext.textContent = stderr || "No error";

    if (status === "FAILED" || status === "FINISHED") {
        statustext.textContent = `Status: ${status}`;
    } else {
        statustext.textContent = `Status: ${status} - Waiting`;
    }
}

function ChangeTab(tab) {
    const alltab = document.querySelectorAll(".tab-content");
    alltab.forEach(tabEl => {
        tabEl.classList.remove("active");
    });
    tabs.forEach(tabBtn => {
        tabBtn.classList.remove("active");
    });

    if (tab === "stdout") {
        stdouttab.classList.add("active");
        document.getElementById("result").innerHTML = "Kết quả";
    } else if (tab === "stderr") {
        stderrtab.classList.add("active");
        document.getElementById("result").innerHTML = "Lỗi";
    } else if (tab === "status") {
        statustab.classList.add("active");
        document.getElementById("result").innerHTML = "Trạng thái";
    }

    const activeTabButton = document.querySelector(`[data-tab="${tab}"]`);
    if (activeTabButton) {
        activeTabButton.classList.add("active");
        moveHighlight(activeTabButton);
    }
}

// ------------------ Sự kiện click nút "Run" ------------------
runbtn.addEventListener("click", async () => {
    const code = code_input.value.trim();
    const lang = langselect.value || "python";

    if (!code) {
        alert("Nhập code đi đừng ngại nữa!");
        return;
    }

    // Map lang -> entry (tên file gửi xuống backend)
    let entry;
    if (lang === "python") {
        entry = "main.py";
    } else if (lang === "go") {
        entry = "main.go";
    } else {
        // fallback nếu sau này thêm ngôn ngữ khác mà chưa map
        entry = "main.txt";
    }

    stdouttext.textContent = "";
    stderrtext.textContent = "";
    statustext.textContent = "Đang tạo job...";

    try {
        const jobid = await create_job(entry, code, lang);
        await runjob(jobid);
        pollJobStatus(jobid);
    } catch (error) {
        console.error(error);
        stderrtext.textContent = error.message || "Unknown error";
        ChangeTab("stderr");
    }
});

// ------------------ Poll trạng thái job ------------------
async function pollJobStatus(jobid) {
    const interval = setInterval(async () => {
        try {
            const jobStatus = await getjob(jobid);
            const { status } = jobStatus;

            const logs = await getLog(jobid);
            Displaylog(logs, status);

            if (status === "FINISHED" || status === "FAILED") {
                clearInterval(interval);
            }
        } catch (error) {
            console.error(error);
        }
    }, 600);
}

// ------------------ Hỗ trợ Tab trong textarea ------------------
code_input.addEventListener("keydown", (event) => {
    if (event.key === "Tab") {
        event.preventDefault();
        const start = code_input.selectionStart;
        const end = code_input.selectionEnd;
        const value = code_input.value;
        code_input.value = value.substring(0, start) + "\t" + value.substring(end);
        code_input.selectionStart = code_input.selectionEnd = start + 1;
    }
});

// ------------------ Tô màu từ khóa (simple) ------------------
// Note: cái này vẫn hơi "Python-centric", nhưng không ảnh hưởng chạy code.
function highlightKeywords(text) {
    const keywords = ['print', 'import', 'def', 'return', 'for', 'if', 'else', 'class'];
    keywords.forEach(keyword => {
        const regex = new RegExp(`\\b${keyword}\\b`, 'g');
        text = text.replace(regex, `<span class="keyword">${keyword}</span>`);
    });
    return text;
}

code_input.addEventListener("input", function () {
    // Nếu bạn dùng <textarea>, phần này thực ra không hoạt động như contenteditable.
    // Giữ nguyên logic cũ, hoặc sau này chuyển sang <div contenteditable>.
    let content = code_input.value;
    content = highlightKeywords(content);
    // Không gán innerHTML cho textarea, nên mình chỉ giữ value.
    // Nếu bạn muốn highlight thật sự, cần đổi sang một editor khác.
});
