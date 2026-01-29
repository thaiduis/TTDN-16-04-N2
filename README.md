<h2 align="center">
    <a href="https://dainam.edu.vn/vi/khoa-cong-nghe-thong-tin">
    🎓 Faculty of Information Technology (DaiNam University)
    </a>
</h2>
<h2 align="center">
TRIỂN KHAI PHẦN MỀM QUẢN LÝ DỰ ÁN VÀ CÔNG VIỆC TRÊN ODOO</h2>
<div align="center">
    <p align="center">
        <img src="docs/aiotlab_logo.png" alt="AIoTLab Logo" width="170"/>
        <img src="docs/fitdnu_logo.png" alt="AIoTLab Logo" width="180"/>
        <img src="docs/dnu_logo.png" alt="DaiNam University Logo" width="200"/>
    </p>

[![AIoTLab](https://img.shields.io/badge/AIoTLab-green?style=for-the-badge)](https://www.facebook.com/DNUAIoTLab)
[![Faculty of Information Technology](https://img.shields.io/badge/Faculty%20of%20Information%20Technology-blue?style=for-the-badge)](https://dainam.edu.vn/vi/khoa-cong-nghe-thong-tin)
[![DaiNam University](https://img.shields.io/badge/DaiNam%20University-orange?style=for-the-badge)](https://dainam.edu.vn)

</div>

## 📖 1. Giới thiệu

Ứng dụng quản lý dự án và công việc là hệ thống quản lý công việc và dự án nhằm hỗ trợ lập kế hoạch, phân công, theo dõi tiến độ và báo cáo kết quả. Hệ thống thích hợp cho nhóm nhỏ, đội phát triển phần mềm, hoặc quản lý nội bộ tổ chức, giúp tăng hiệu suất và minh bạch trong công việc.

Các mục tiêu chính:
- Tổ chức và quản lý dự án, sprint, milestone
- Tạo, gán và theo dõi công việc (tasks) với trạng thái, ưu tiên và deadline
- Quản lý thành viên, vai trò và quyền truy cập
- Ghi nhận lịch sử hoạt động, thông báo và báo cáo tiến độ
- Hỗ trợ xuất dữ liệu (CSV/JSON) và tích hợp cơ bản với hệ thống khác

---

## 🧩 2. Tính năng chính

### 2.1 Quản lý Dự án (Project Management)

- **Tạo & cấu trúc dự án**: tên dự án, mô tả, start/end date, stakeholders.
- **Milestone / Sprint**: định nghĩa milestone, quản lý sprint, target và trạng thái.
- **Phân bổ nguồn lực**: gán thành viên vào dự án, theo dõi công suất và vai trò.
- **Quản lý rủi ro & tài liệu**: ghi chú, tài liệu liên quan, issue tracking liên kết.
- **Báo cáo dự án**: báo cáo tiến độ, burn-down chart, deliverables theo milestone.

### 2.2 Quản lý Công việc (Task Management)

- **Tạo task chi tiết**: tiêu đề, mô tả, checklist, phụ thuộc (dependency), tag.
- **Phân công & quyền hạn**: assignee, watchers, thời hạn (deadline), ưu tiên (priority).
- **Board & Workflow**: Kanban board (To Do → In Progress → Done), kéo-thả chuyển trạng thái.
- **Thời gian & báo cáo**: ước lượng thời gian, log time, báo cáo thời gian thực hiện.
- **Tương tác**: bình luận, đính kèm file, mentions và thông báo (notifications).
- **Quy tắc & automation**: rule tự động chuyển trạng thái, reminder, recurring tasks.


---

## 🛠️ 3. Công nghệ sử dụng

- Backend: `Python 3.10+` (Flask / FastAPI) hoặc `Node.js` (Express) — tuỳ cấu hình dự án
- Frontend: `React` / `Vue` hoặc giao diện web đơn giản (HTML/CSS/JS)
- Database: `PostgreSQL` / `MySQL` / `SQLite` (tùy trường hợp)
- Authentication: JWT / Session-based
- DevOps: Docker, docker-compose cho môi trường phát triển

---

## 🧭 4. Cài đặt & Chạy nhanh (Quickstart)

*LƯU Ý*: các hướng dẫn dưới đây là mẫu; điều chỉnh theo stack thực tế trong repo.

### 4.1. Yêu cầu
- Python 3.10+ / Node.js 16+
- Docker & docker-compose (khuyến nghị)
- PostgreSQL / MySQL (nếu không dùng Docker)

### 4.2. Chạy bằng Docker (gợi ý)
```bash
docker-compose up --build -d
```
Truy cập ứng dụng tại `http://localhost:8000` hoặc theo cấu hình.

### 4.3. Cài đặt thủ công (ví dụ Python)
```bash
python -m venv .venv
source .venv/bin/activate
pip install -r requirements.txt
cp .env.example .env
# cấu hình DATABASE_URL, SECRET_KEY, ...
alembic upgrade head   # nếu dùng alembic cho migration
uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

---

## 5. Cấu hình cơ sở dữ liệu

- Tạo database và user theo hướng dẫn DB engine đang sử dụng.
- File mẫu schema/migration có thể nằm tại `database/schema.sql` hoặc thư mục `migrations/`.
- Thiết lập biến môi trường `DATABASE_URL` hoặc chỉnh `src/config` tương ứng.

---

## 6. Kiến trúc & Cấu trúc mã nguồn

Ví dụ cấu trúc:
```
quan_ly_cong_viec/
├── app/               # backend source
├── web/               # frontend source
├── database/          # schema, seeders, migrations
├── docs/              # hình ảnh, hướng dẫn
├── docker-compose.yml
└── README.md
```

Các module chính:
- `projects`: quản lý dự án, milestone
- `tasks`: CRUD tasks, checklist, trạng thái
- `users`: quản lý user, authentication, role
- `reports`: sinh báo cáo tiến độ, export

---

## 7. Một số hình ảnh hệ thống

![Server GUI](docs/Server-Update.png)

---

![Server GUI](docs/LichsuUpdate.png)

---

![Server GUI](docs/Form-update.png) 

---



## 📫 11. Liên hệ
- Họ và tên: Vũ Duy Thái
- Khoa: Công nghệ thông tin - Trường Đại học Đại Nam
- Liên hệ email: thaiitkk2004@gmail.com

<p align="center">© 2026 AIoTLab, Faculty of Information Technology, DaiNam University. All rights reserved.</p>





