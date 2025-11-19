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

// Điều chỉnh chuyển đổi ngôn ngữ
prevlang.addEventListener("click", () => {
    let index = langselect.selectedIndex;
    if (index > 0) {
        langselect.selectedIndex = index - 1;
    }
});
nextlang.addEventListener("click", () => {
    let index = langselect.selectedIndex;
    if (index < langselect.options.length - 1) {
        langselect.selectedIndex = index + 1;
    }
});

// Chuyển tab khi nhấn vào các tab
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

async function create_job(entry, code) {
    const rest = await fetch(`${Base_url}/jobs`, {
        method: "POST",
        headers: {
            "Content-Type": "application/json",
        },
        body: JSON.stringify({ entry, code }),
    });

    if (!rest.ok) {
        throw new Error("Create job failed");
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
    alltab.forEach(tab => {
        tab.classList.remove("active");
    });
    tabs.forEach(tab => {
        tab.classList.remove("active");
    });

    if (tab === "stdout") {
        stdouttab.classList.add("active");
        document.getElementById("stdout").classList.add("active");
        document.getElementById("result").innerHTML = "Kết quả";
    } else if (tab === "stderr") {
        stderrtab.classList.add("active");
        document.getElementById("result").innerHTML = "Lỗi";
        document.getElementById("stderr").classList.add("active");
    } else if (tab === "status") {
        statustab.classList.add("active");
        document.getElementById("result").innerHTML = "Trạng thái";
        document.getElementById("status").classList.add("active");
    }
    const activeTabButton = document.querySelector(`[data-tab="${tab}"]`);
    if (activeTabButton) {
        activeTabButton.classList.add("active");
    }
}

// Sự kiện click nút "Run"
runbtn.addEventListener("click", async () => {
    const code = code_input.value.trim();
    const entry = langselect.value || "python"; // Đảm bảo chọn ngôn ngữ từ select box

    if (!code) {
        alert("Nhập code đi đừng ngại nữa!");
        return;
    }
    stdouttext.textContent = "";
    stderrtext.textContent = "";
    statustext.textContent = "Đang tạo job...";

    try {
        const jobid = await create_job(entry, code);
        await runjob(jobid);
        pollJobStatus(jobid);
    } catch (error) {
        console.error(error);
        stderrtext.textContent = error.message || "Unknown error";
    }
});

// Poll trạng thái job
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

// Hàm tô màu từ khóa trong code
function highlightKeywords(text) {
    const keywords = ['print', 'import', 'def', 'return', 'for', 'if', 'else', 'class'];
    keywords.forEach(keyword => {
        const regex = new RegExp(`\\b${keyword}\\b`, 'g');
        text = text.replace(regex, `<span class="keyword">${keyword}</span>`);
    });
    return text;
}

code_input.addEventListener("input", function () {
    let content = code_input.value;
    content = highlightKeywords(content);
    code_input.innerHTML = content;
});
