# Module Quản lý Công việc Thông minh

## Giới thiệu
Module **Smart Task Execution** cho Odoo 15 - Hệ thống quản lý công việc tích hợp AI để báo cáo thông minh và chấm điểm tự động.

## Tính năng chính

### 1. 🎯 Mở rộng Project Task
- **Skill Requirements**: Định nghĩa kỹ năng yêu cầu cho từng công việc
- **Risk Management**: Tự động phát hiện và đánh dấu công việc có rủi ro
- **Smart Dependencies**: Quản lý phụ thuộc giữa các task
- **Time Tracking**: Theo dõi thời gian ước tính vs thực tế

### 2. 📝 Smart Report (Báo cáo Thông minh)
- **Natural Language Input**: Nhân viên viết báo cáo bằng ngôn ngữ tự nhiên
- **AI Analysis**: 
  - Phân tích cảm xúc (Sentiment Analysis)
  - Phát hiện vướng mắc tự động (Blocker Detection)
  - Trích xuất từ khóa rủi ro
  - Tự động tóm tắt
- **Auto Notification**: Tự động thông báo PM khi phát hiện vấn đề
- **Chatter Integration**: Đăng báo cáo lên timeline của task

### 3. 🏆 Score Card (Phiếu điểm)
- **Auto Scoring**: Tự động chấm điểm khi task hoàn thành
- **4 Tiêu chí**:
  - ⏰ Timeliness (40%): Đúng hạn hay trễ
  - ⚡ Efficiency (30%): So sánh thời gian ước tính vs thực tế
  - ✨ Quality (30%): Số lần re-open, bug reports
- **Grading**: S, A, B, C, D
- **AI Feedback**: Lời khuyên cải thiện cho lần sau

### 4. 🔗 Tích hợp HR
- **Skill Gap Warning**: Cảnh báo khi giao việc cho người thiếu kỹ năng
- **Workload Balancing**: Kiểm tra khối lượng công việc hiện tại
- **XP Rewards**: Cộng điểm kinh nghiệm vào hồ sơ nhân viên

### 5. 📊 Analytics & Reporting
- **Kanban View**: Hiển thị trực quan phiếu điểm
- **Graph View**: Phân tích theo nhân viên/dự án
- **Pivot Table**: Báo cáo đa chiều

## Cài đặt

### Bước 1: Copy module vào addons path
```bash
cp -r quan_ly_cong_viec /odoo/addons/
```

### Bước 2: Cập nhật danh sách module
```bash
# Trong Odoo
Apps > Update Apps List
```

### Bước 3: Cài đặt module
```bash
# Tìm kiếm "Quản lý Công việc Thông minh"
# Click "Install"
```

### Bước 4: Cấu hình quyền
```bash
# Settings > Users & Companies > Users
# Gán nhóm "Project / User" hoặc "Project / Manager"
```

## Sử dụng

### Dành cho Nhân viên

#### 1. Bắt đầu công việc
```
Project > Tasks > Chọn task > Nút "BẮT ĐẦU"
```
Hệ thống sẽ kiểm tra:
- Dependencies (Task phụ thuộc đã xong chưa?)
- Skills (Bạn có kỹ năng cần thiết không?)
- Workload (Đang làm bao nhiêu task?)

#### 2. Báo cáo tiến độ
```
Trong Task > Tab "🚀 Smart Execution" > Nút "Báo cáo"
```
**Viết tự nhiên**, ví dụ:
```
"Hôm nay tôi đã code xong chức năng Login, test ok. 
Nhưng đang vướng phần bảo mật, chưa biết dùng thư viện nào."
```

AI sẽ tự động:
- Phát hiện từ "vướng" → Đánh dấu **Blocker**
- Sentiment = **Negative**
- Gửi thông báo cho PM

#### 3. Xem điểm số
```
Task hoàn thành > Tab "Smart Execution" > Xem Score Card
```

### Dành cho Project Manager

#### 1. Theo dõi báo cáo
```
Menu: 🚀 Smart Task > Báo cáo Tiến độ
```
- Lọc theo "Có Vướng mắc"
- Nhóm theo Task/Nhân viên/Ngày

#### 2. Phân tích hiệu suất
```
Menu: 🚀 Smart Task > Phiếu Điểm
```
Views:
- **Kanban**: Xem achievement board
- **Graph**: Phân tích theo nhân viên
- **Pivot**: Báo cáo đa chiều

#### 3. Quản lý rủi ro
```
Project > Tasks (Tree View)
```
- Dòng **đỏ** = Task bị Blocked
- Dòng **vàng** = Risk Level cao

## Cấu trúc Code

```
quan_ly_cong_viec/
├── __init__.py
├── __manifest__.py
├── models/
│   ├── __init__.py
│   ├── project_task.py          # Mở rộng project.task
│   ├── task_smart_report.py     # Model báo cáo thông minh
│   └── task_score_card.py       # Model phiếu điểm
├── views/
│   ├── project_task_views.xml
│   ├── task_smart_report_views.xml
│   ├── task_score_card_views.xml
│   └── menu_views.xml
└── security/
    └── ir.model.access.csv
```

## Tùy biến

### 1. Thay đổi công thức chấm điểm
Sửa file: `models/project_task.py`
```python
def _auto_generate_score_card(self):
    # Thay đổi trọng số tại đây
    final_score = (
        timeliness_score * 0.5 +    # Tăng trọng số đúng hạn
        efficiency_score * 0.3 +
        quality_score * 0.2
    )
```

### 2. Tùy chỉnh AI Keywords
Sửa file: `models/task_smart_report.py`
```python
blocker_keywords = [
    'vướng', 'khó khăn', 'không biết',
    # Thêm từ khóa của bạn...
]
```

### 3. Tích hợp AI thật (OpenAI, GPT)
```python
def _ai_analyze_report(self, content):
    import openai
    
    response = openai.Completion.create(
        model="gpt-3.5-turbo",
        prompt=f"Phân tích báo cáo công việc sau: {content}"
    )
    
    return {
        'ai_summary': response.choices[0].text,
        # ...
    }
```

## Roadmap

- [ ] Dashboard thực tế cho PM
- [ ] Tích hợp Voice Input (Speech to Text)
- [ ] Real AI Integration (OpenAI API)
- [ ] Mobile App
- [ ] Gamification Profile (Level, Badges)
- [ ] Anomaly Detection (Phát hiện bất thường)

## Hỗ trợ

Liên hệ: your-email@company.com

## License
LGPL-3
