# sandboxpy
- API : /jobs endpoints
- Tầng bảo mật: rlimits → ns/chroot → cgroups → seccomp
- DB nhúng: SQLite (Chạy code sẽ tự tạo ra sandbox.db)
- Đa ngôn ngữ: Python

## Dev quickstart
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
uvicorn sandbox.api:app --reload --port 8000 --app-dir src

## Test
# Tạo job
JOB=$(curl -s -X POST http://127.0.0.1:8000/jobs \
  -H 'content-type: application/json' \
  -d '{"entry":"main.py","code":"x=bytearray(100*1024*1024); print(\"allocated 100MB\")"}' \
  | jq -r '.job_id')
echo "JOB=$JOB"
# 1) Run job
curl -s -X POST "http://127.0.0.1:8000/jobs/$JOB/run" >/dev/null

# 2) Poll trạng thái cho tới khi xong
while true; do
  S=$(curl -s "http://127.0.0.1:8000/jobs/$JOB" \
      | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')
  echo "status=$S"
  [[ "$S" = "FINISHED" || "$S" = "FAILED" ]] && break
  sleep 0.4
done

# 3) In logs (định dạng đẹp)
curl -s "http://127.0.0.1:8000/jobs/$JOB/logs" | python3 -m json.tool



# 1) Tạo job
JOB=$(curl -s -X POST http://127.0.0.1:8000/jobs \
  -H 'content-type: application/json' \
  -d '{"entry":"main.py","code":"print(\"hello sandbox\")"}' \
  | python3 -c 'import sys,json;print(json.load(sys.stdin)["job_id"])')
echo "JOB=$JOB"

# 2) Chạy job
curl -s -X POST http://127.0.0.1:8000/jobs/$JOB/run >/dev/null

# 3) Poll (zsh an toàn, không dùng =~)
while true; do
  S=$(curl -s http://127.0.0.1:8000/jobs/$JOB \
      | python3 -c 'import sys,json;print(json.load(sys.stdin)["status"])')
  echo "status=$S"
  [[ "$S" = "FINISHED" || "$S" = "FAILED" ]] && break
  sleep 0.3
done

# 4) Lấy logs
curl -s http://127.0.0.1:8000/jobs/$JOB/logs


#Test Golang
package main

import (
	"fmt"
	"runtime"
	"runtime/debug"
)

func main() {
	fmt.Println("=== Go Runtime Info ===")
	fmt.Println("Go version:", runtime.Version())
	fmt.Println("OS:", runtime.GOOS)
	fmt.Println("Arch:", runtime.GOARCH)
	fmt.Println("CPUs:", runtime.NumCPU())
	fmt.Println("GOMAXPROCS:", runtime.GOMAXPROCS(0))
	fmt.Println("GOROOT:", runtime.GOROOT())

	// build info (nếu build bằng module)
	if info, ok := debug.ReadBuildInfo(); ok {
		fmt.Println("Module path:", info.Path)
		fmt.Println("Main module:", info.Main.Path, info.Main.Version)
	}
}


package main

import "fmt"

func main() {
	// fix cứng giá trị
	a := 10.0
	b := 3.0

	fmt.Println("=== Simple Calculator ===")
	fmt.Printf("a = %.2f, b = %.2f\n", a, b)

	fmt.Printf("a + b = %.2f\n", a+b)
	fmt.Printf("a - b = %.2f\n", a-b)
	fmt.Printf("a * b = %.2f\n", a*b)

	if b != 0 {
		fmt.Printf("a / b = %.2f\n", a/b)
	} else {
		fmt.Println("a / b = khong the chia cho 0")
	}
}

# Test Syscall an toan 
def test_syscall():
    try:
        # Mở một file và ghi một chuỗi vào đó
        with open('test_file.txt', 'w') as f:
            f.write('Đây là một ví dụ để test syscall an toàn!')
        
        with open('test_file.txt', 'r') as f:
            content = f.read()
            print(f"Đã đọc nội dung từ file: {content}")
    
    except Exception as e:
        print(f"Lỗi xảy ra: {e}")

test_syscall()


#Test Syscall nguy hiem 
import socket

def cause_socket_error():
    try:
        # Tạo một socket
        s = socket.socket(socket.AF_INET, socket.SOCK_STREAM)
        
        # Cố gắng kết nối đến một địa chỉ không hợp lệ (vi phạm syscall)
        s.connect(('256.256.256.256', 8080))  # Địa chỉ IP này không hợp lệ
        
    except socket.error as e:
        print(f"Lỗi socket: {e}")

cause_socket_error()



#Test Cap phat bo nho nguy hiem
def test_memory_allocation():
    try:
        # Cố gắng cấp phát một lượng lớn bộ nhớ
        large_array = bytearray(10**9)  # 1 GB
        print("Đã cấp phát thành công 1 GB bộ nhớ.")
    
    except MemoryError:
        print("Lỗi: Không thể cấp phát bộ nhớ - vượt quá giới hạn!")
    
    except Exception as e:
        print(f"Lỗi xảy ra: {e}")


#Test PID 
import multiprocessing

def worker():
    print(f"Process ID: {multiprocessing.current_process().pid}")

def create_processes():
    processes = []
    for i in range(10):  # Giới hạn tạo 10 tiến trình
        p = multiprocessing.Process(target=worker)
        processes.append(p)
        p.start()

    for p in processes:
        p.join()

if __name__ == "__main__":
    create_processes()

 sudo nano /etc/polkit-1/rules.d/49-sandbox-systemd-run.rules 


 thuc thi >20s
import time

def long_running_task():
    print("Bắt đầu công việc tốn thời gian...")
    time.sleep(25)  # Dừng 25 giây để mô phỏng công việc tốn thời gian
    print("Công việc đã hoàn thành!")

if __name__ == "__main__":
    long_running_task()
