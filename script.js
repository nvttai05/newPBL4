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

tabs.forEach(tab => {
    tab.addEventListener("click", () => {
        const tabname = tab.getAttribute("data-tab");
        ChangeTab(tabname);
    });
});

async function create_job(entry, code) {
    const rest = await fetch("http://127.0.0.1:8000/jobs", {
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

function showinfo(tab, status) {
    // stdouttext.textContent = 
}

function Displaylog(Logs, status) {
    const { stdout, stderr } = Logs;
    stdouttext.textContent = stdout || "No result";
    stderrtext.textContent = stderr || "No error";

    if (status === 'FAILED' || status === 'FINISHED') { // So sánh đúng với '==='
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

    if (tab === "stdout") { // So sánh đúng với '==='
        stdouttab.classList.add("active");
        document.getElementById("stdout").classList.add("active");
        document.getElementById("result").innerHTML = "Kết quả"; 
    } else if (tab === 'stderr') { // So sánh đúng với '==='
        stderrtab.classList.add("active");
        document.getElementById("result").innerHTML = "Lỗi"; 
        document.getElementById("stderr").classList.add("active");
    } else if (tab === "status") { // So sánh đúng với '==='
        statustab.classList.add("active");
        document.getElementById("result").innerHTML = "Trạng thái"; 
        document.getElementById("status").classList.add("active");
    }
}

runbtn.addEventListener("click", async () => {
    const code = code_input.value.trim(); // 'ariaValueText' thành 'value'
    const entry = "main.py";
    if (!code) {
        alert("Nhập code đi đừng ngại nữa!");
        return;
    }
    stdouttext.textContent = "";
    stderrtext.textContent = "";
    statustext.textContent = "Đang tạo job...";

    try {
        const jobid = await create_job(entry, code); // Thêm await để đợi kết quả
        await runjob(jobid); // Thêm await để đợi kết quả
        pollJobStatus(jobid); // Poll trạng thái job
    } catch (error) {
        console.error(error);
        stderrtext.textContent = error.message || "Unknown error";
    }
});

async function pollJobStatus(jobid) {
    const interval = setInterval(async () => {
        try {
            const jobStatus = await getjob(jobid);
            const { status } = jobStatus;

            // Hiển thị logs
            const logs = await getLog(jobid);
            Displaylog(logs, status);

            if (status === 'FINISHED' || status === 'FAILED') {
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


code_input.addEventListener("input", function() {
    // Lấy nội dung văn bản từ code_input (dạng plain text)
    let content = code_input.innerText;
    
    // Tô màu các từ khóa trong nội dung
    content = highlightKeywords(content);

    // Tạo một tạm thời div với nội dung đã tô màu
    const tempDiv = document.createElement('div');
    tempDiv.innerHTML = content;

    // Chèn lại nội dung đã tô màu vào contenteditable
    code_input.innerHTML = tempDiv.innerHTML;
});

// Hàm tô màu các từ khóa
function highlightKeywords(text) {
    const keywords = ['print', 'import', 'def', 'return', 'for', 'if', 'else', 'class'];

    keywords.forEach(keyword => {
        const regex = new RegExp(`\\b${keyword}\\b`, 'g');  // Tìm các từ chính xác
        text = text.replace(regex, `<span class="keyword">${keyword}</span>`); // Thay thế từ khóa bằng thẻ HTML
    });

    return text;
}