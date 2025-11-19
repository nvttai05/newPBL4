import os
import mmap

# Đường dẫn tệp
file_path = "/tmp/test_seccomp_file"

# Tạo tệp nếu chưa tồn tại
if not os.path.exists(file_path):
    with open(file_path, "w") as f:
        f.write("seccomp test data")

# Mở tệp và thực hiện mmap
os.open(file_path, os.O_RDONLY)
mmap.mmap(0, 10)

# Thực thi lệnh execve
os.execve("/bin/echo", ["/bin/echo", "seccomp test"])
print("Executed execve successfully")
