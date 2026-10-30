const API_PATH = "/door-opener/api";

async function request(url, method = "GET"){
    const token = localStorage.getItem("door_session_token");
    const result = await fetch(url, {
        method: method,
        headers:{
            "X-Session-Token": token,
            "Content-Type": "application/json"
        }
    });
    if (result.status == 401){
        showLoginDialog();
        throw new Error("未登录")
    }

    const text = await result.text();
    console.log("原始响应：", text);
    return JSON.parse(text);
}

function showLoginDialog(){
    const dialog = document.getElementById("dialog-login");
    dialog.showModal();
}

async function login(password){
    try{
        const res = await fetch(`${API_PATH}/login`, {
            method: "POST",
            headers: { "Content-Type": "application/json" },
            body: JSON.stringify({ password })
        });

        const data = await res.json();

        if (res.ok) {
            // 登录成功，保存 Session 3天，并刷新页面
            localStorage.setItem("door_session_token", data.token);
            window.location.reload();
            closeLoginDialog();
        } else {
            alert(data.detail || "密码错误！");
        }
    }catch(err){
        alert("登录失败：" + err);
    }
}

function closeLoginDialog(){
    const dialog = document.getElementById("dialog-login");
    dialog.close();
}

async function getDoors(){
    document.getElementById("form-login").addEventListener("submit", (e)=>{
        e.preventDefault();
        login(e.target["password"].value);
    });
    try{
        const data = await request(`${API_PATH}/doors`, "GET");
        console.log("门锁列表：", data);
        renderDoors(data);
        document.getElementById("door-list").addEventListener("click", async (e)=>{
            const target = e.target.closest(".unlock-btn");
            if(target){
                const door = target.closest(".door");
                await openDoor(door.dataset.id);
            }
        });
        const status = await getDoorStatus();
        if(status){
            updateDoorsStatus(status);
        }
    }catch(err){
        alert("获取门禁列表失败");
        console.error("获取门禁列表失败：", err);
    }
    
    
}

async function getDoorStatus(){

    try{
        const data = await request(`${API_PATH}/doors/status`, "GET");
        return data;
    }catch(err){
        showStatus("获取状态失败：" + err, "error");
        return null;
    }
}

getDoors();

async function openDoor(doorId) {
    showStatus("发送开锁指令");

    try {
        // 发送 POST 请求到 FastAPI 后台
        const data = await request(`${API_PATH}/unlock/${doorId}`, "POST");
        if (data.ok && data.status === "success") {
            showStatus(data.message, "success");
        } else {
            showStatus(data.detail || data.message || "开锁失败", "warning");
        }
    } catch (err) {
        showStatus("❌ 无法连接服务器，请检查网络！", "error");
    }
}

const THEMES = ['theme-blue', 'theme-purple', 'theme-amber', 'theme-emerald'];

function renderDoors(doors) {
    const container = document.getElementById("door-list");
    container.innerHTML = ""; 

    doors.forEach((door, index) => {
        const box = document.createElement("div");
        
        const themeClass = door.theme || THEMES[index % THEMES.length];
        box.className = `door ${themeClass}`;
        box.dataset.id = door.id;

        // 头部区域
        const header = document.createElement("div");
        header.className = "door-header";

        const icon = document.createElement("div");
        icon.className = "door-icon";
        icon.textContent = door.icon || "🚪";

        const hName = document.createElement("h2");
        hName.textContent = door.name;

        // 💡 纯 CSS 状态徽章：包含指示灯圆点和文本
        const badge = document.createElement("div");
        badge.className = "status-badge checking";
        
        const dot = document.createElement("span");
        dot.className = "status-dot";
        
        const text = document.createElement("span");
        text.className = "status-text";
        text.textContent = "检测中";

        badge.appendChild(dot);
        badge.appendChild(text);

        header.appendChild(icon);
        header.appendChild(hName);
        header.appendChild(badge);

        // IP 与 SN 区域
        const pIp = document.createElement("p");
        pIp.textContent = door.ip;

        const divSn = document.createElement("div");
        divSn.className = "sn";
        divSn.textContent = `SN: ${door.sn}`;

        // 开锁按钮
        const btnUnlock = document.createElement("button");
        btnUnlock.className = "unlock-btn";
        btnUnlock.innerHTML = "远程开锁";

        box.appendChild(header);
        box.appendChild(pIp);
        box.appendChild(divSn);
        box.appendChild(btnUnlock);
        
        container.appendChild(box);
    });
}

// 💡 对应的状态更新函数（同步更新小圆点和文字）
function updateDoorsStatus(statusMap) {
    Object.keys(statusMap).forEach(doorId => {
        const card = document.querySelector(`.door[data-id="${doorId}"]`);
        if (card) {
            const badge = card.querySelector(".status-badge");
            const text = card.querySelector(".status-text");
            const isOnline = statusMap[doorId] === "online";
            
            if (badge && text) {
                badge.className = `status-badge ${isOnline ? 'online' : 'offline'}`;
                text.textContent = isOnline ? "在线" : "离线";
            }
        }
    });
}


// 展示状态框
function showStatus(message, type = "success") {
    const statusBox = document.getElementById("status-box");
    statusBox.textContent = message;
    statusBox.className = `show ${type}`;
    
    // 3 秒后自动隐去
    setTimeout(() => {
        statusBox.className = "";
    }, 3000);
}