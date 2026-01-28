# -*- coding: utf-8 -*-

from odoo import models, fields, api
import re

class TaskSentimentAnalyzer(models.AbstractModel):
    _name = 'task.sentiment.analyzer'
    _description = 'Task Sentiment Analyzer - Vietnamese'

    # Từ điển cảm xúc tiếng Việt
    POSITIVE_WORDS = {
        # Rất tích cực (2.0)
        'xuất sắc': 2.0, 'tuyệt vời': 2.0, 'hoàn hảo': 2.0, 'tuyệt đỉnh': 2.0,
        'kinh ngạc': 2.0, 'đỉnh cao': 2.0, 'xuất chúng': 2.0,
        
        # Tích cực cao (1.5)
        'tốt': 1.5, 'hay': 1.5, 'giỏi': 1.5, 'thành công': 1.5, 
        'hiệu quả': 1.5, 'ổn': 1.5, 'ok': 1.5, 'okay': 1.5,
        'hoàn thành': 1.5, 'đạt': 1.5, 'vượt': 1.5,
        
        # Tích cực trung bình (1.0)
        'được': 1.0, 'ổn định': 1.0, 'bình thường': 0.8, 
        'làm được': 1.0, 'xong': 1.0, 'done': 1.0,
        'clear': 1.0, 'rõ ràng': 1.0, 'sáng': 1.0,
        
        # Cải thiện (1.2)
        'tiến bộ': 1.2, 'cải thiện': 1.2, 'tăng': 1.2, 'nâng cao': 1.2,
        'phát triển': 1.2, 'mở rộng': 1.2,
        
        # Động lực (1.3)
        'nhiệt tình': 1.3, 'hào hứng': 1.3, 'sáng tạo': 1.3,
        'chủ động': 1.3, 'tích cực': 1.3, 'năng động': 1.3,
        
        # Chất lượng (1.4)
        'chất lượng': 1.4, 'tốc độ': 1.0, 'nhanh': 1.2, 
        'đúng': 1.2, 'chính xác': 1.4, 'chuẩn': 1.3,
        
        # Hợp tác (1.1)
        'hợp tác': 1.1, 'team work': 1.1, 'support': 1.1,
        'hỗ trợ': 1.1, 'giúp đỡ': 1.1, 'cùng nhau': 1.0,
    }

    NEGATIVE_WORDS = {
        # Rất tiêu cực (-2.0)
        'thảm họa': -2.0, 'tệ hại': -2.0, 'kinh khủng': -2.0,
        'nguy hiểm': -2.0, 'tai họa': -2.0, 'thất bại': -2.0,
        
        # Tiêu cực cao (-1.5)
        'tệ': -1.5, 'kém': -1.5, 'dở': -1.5, 'xấu': -1.5,
        'khó': -1.3, 'khó khăn': -1.3, 'vất vả': -1.3,
        'phức tạp': -1.0, 'rắc rối': -1.4,
        
        # Vấn đề kỹ thuật (-1.6)
        'bug': -1.6, 'lỗi': -1.6, 'crash': -1.8, 'die': -1.7,
        'fail': -1.6, 'error': -1.5, 'warning': -0.8,
        'issue': -1.0, 'problem': -1.2,
        
        # Chậm trễ (-1.4)
        'chậm': -1.4, 'trễ': -1.4, 'muộn': -1.3, 'delay': -1.4,
        'pending': -0.9, 'block': -1.5, 'blocked': -1.6,
        'stuck': -1.5, 'bế tắc': -1.6,
        
        # Thiếu sót (-1.3)
        'thiếu': -1.3, 'sót': -1.3, 'quên': -1.2, 'nhầm': -1.4,
        'sai': -1.5, 'missing': -1.3, 'incomplete': -1.2,
        
        # Khó khăn công việc (-1.2)
        'áp lực': -1.2, 'stress': -1.2, 'gấp': -1.0, 'urgent': -0.9,
        'deadline': -0.7, 'overtime': -1.1, 'tăng ca': -1.0,
        
        # Không đạt yêu cầu (-1.5)
        'không đạt': -1.5, 'chưa đạt': -1.2, 'chưa xong': -1.1,
        'chưa hoàn thành': -1.3, 'incomplete': -1.2,
        
        # Khó hiểu (-1.1)
        'khó hiểu': -1.1, 'không rõ': -1.0, 'mơ hồ': -1.0,
        'confuse': -1.1, 'unclear': -1.0,
        
        # Xung đột (-1.4)
        'xung đột': -1.4, 'mâu thuẫn': -1.4, 'conflict': -1.3,
        'disagree': -1.0,
    }

    NEUTRAL_WORDS = {
        'đang': 0.0, 'làm': 0.0, 'thực hiện': 0.0, 'tiến hành': 0.0,
        'working': 0.0, 'in progress': 0.0, 'wip': 0.0,
        'update': 0.0, 'cập nhật': 0.0, 'review': 0.0,
        'check': 0.0, 'kiểm tra': 0.0, 'test': 0.0,
    }

    # Các từ phủ định đảo ngược cảm xúc
    NEGATION_WORDS = [
        'không', 'chưa', 'chẳng', 'không có', 'không được',
        'no', 'not', 'never', 'none', 'neither',
    ]

    # Các từ nhấn mạnh tăng cường cảm xúc
    INTENSIFIERS = {
        'rất': 1.5, 'cực': 1.8, 'vô cùng': 1.8, 'quá': 1.6,
        'hết sức': 1.7, 'cực kỳ': 1.8, 'siêu': 1.7,
        'very': 1.5, 'extremely': 1.8, 'super': 1.7,
        'too': 1.4, 'really': 1.5, 'so': 1.4,
    }

    # Từ giảm nhẹ
    DIMINISHERS = {
        'hơi': 0.7, 'khá': 0.8, 'tương đối': 0.8, 'có vẻ': 0.7,
        'slightly': 0.7, 'somewhat': 0.75, 'fairly': 0.8,
        'a bit': 0.7, 'a little': 0.7,
    }

    def analyze_text(self, text):
        """
        Phân tích cảm xúc của văn bản tiếng Việt
        
        Returns:
            dict: {
                'score': float (-1.0 đến 1.0),
                'sentiment': str ('positive', 'negative', 'neutral'),
                'confidence': float (0.0 đến 1.0),
                'details': list[dict] - Các từ khóa tìm thấy
            }
        """
        if not text:
            return {
                'score': 0.0,
                'sentiment': 'neutral',
                'confidence': 0.0,
                'details': []
            }
        
        # Chuẩn hóa text
        text = text.lower().strip()
        words = re.findall(r'\w+', text, re.UNICODE)
        
        sentiment_scores = []
        found_keywords = []
        
        i = 0
        while i < len(words):
            word = words[i]
            score = 0.0
            modifier = 1.0
            is_negated = False
            
            # Kiểm tra từ phủ định trước đó
            if i > 0 and words[i-1] in self.NEGATION_WORDS:
                is_negated = True
            
            # Kiểm tra từ nhấn mạnh trước đó
            if i > 0 and words[i-1] in self.INTENSIFIERS:
                modifier = self.INTENSIFIERS[words[i-1]]
            
            # Kiểm tra từ giảm nhẹ trước đó
            if i > 0 and words[i-1] in self.DIMINISHERS:
                modifier = self.DIMINISHERS[words[i-1]]
            
            # Tìm trong từ điển tích cực
            if word in self.POSITIVE_WORDS:
                score = self.POSITIVE_WORDS[word] * modifier
                if is_negated:
                    score = -score * 0.8  # Đảo ngược nhưng giảm 20%
                found_keywords.append({
                    'word': word,
                    'base_score': self.POSITIVE_WORDS[word],
                    'final_score': score,
                    'negated': is_negated,
                    'modifier': modifier
                })
            
            # Tìm trong từ điển tiêu cực
            elif word in self.NEGATIVE_WORDS:
                score = self.NEGATIVE_WORDS[word] * modifier
                if is_negated:
                    score = -score * 0.8  # Đảo ngược thành tích cực
                found_keywords.append({
                    'word': word,
                    'base_score': self.NEGATIVE_WORDS[word],
                    'final_score': score,
                    'negated': is_negated,
                    'modifier': modifier
                })
            
            if score != 0.0:
                sentiment_scores.append(score)
            
            i += 1
        
        # Tính điểm trung bình
        if sentiment_scores:
            avg_score = sum(sentiment_scores) / len(sentiment_scores)
            # Normalize về khoảng -1.0 đến 1.0
            final_score = max(-1.0, min(1.0, avg_score / 2.0))
        else:
            final_score = 0.0
        
        # Xác định sentiment
        if final_score > 0.2:
            sentiment = 'positive'
        elif final_score < -0.2:
            sentiment = 'negative'
        else:
            sentiment = 'neutral'
        
        # Tính confidence dựa trên số lượng từ khóa tìm thấy
        total_words = len(words) if words else 1
        keyword_count = len(found_keywords)
        confidence = min(1.0, keyword_count / (total_words * 0.3))  # Max confidence khi 30% là keywords
        
        return {
            'score': round(final_score, 2),
            'sentiment': sentiment,
            'confidence': round(confidence, 2),
            'details': found_keywords,
            'keyword_count': keyword_count,
            'total_words': total_words
        }
    
    def analyze_report_content(self, progress_note, issues, achievements):
        """
        Phân tích tổng hợp từ nhiều nguồn
        
        Args:
            progress_note: str - Ghi chú tiến độ
            issues: str - Vấn đề gặp phải
            achievements: str - Thành tựu đạt được
            
        Returns:
            dict: Kết quả phân tích tổng hợp
        """
        # Phân tích từng phần
        progress_result = self.analyze_text(progress_note or '')
        issues_result = self.analyze_text(issues or '')
        achievements_result = self.analyze_text(achievements or '')
        
        # Trọng số cho từng phần
        weights = {
            'progress': 0.3,
            'issues': 0.4,     # Vấn đề có trọng số cao hơn
            'achievements': 0.3
        }
        
        # Tính điểm tổng hợp
        total_score = (
            progress_result['score'] * weights['progress'] +
            issues_result['score'] * weights['issues'] +
            achievements_result['score'] * weights['achievements']
        )
        
        # Xác định sentiment tổng thể
        if total_score > 0.2:
            overall_sentiment = 'positive'
        elif total_score < -0.2:
            overall_sentiment = 'negative'
        else:
            overall_sentiment = 'neutral'
        
        return {
            'overall_score': round(total_score, 2),
            'overall_sentiment': overall_sentiment,
            'progress_analysis': progress_result,
            'issues_analysis': issues_result,
            'achievements_analysis': achievements_result,
            'summary': self._generate_summary(total_score, overall_sentiment)
        }
    
    def _generate_summary(self, score, sentiment):
        """Tạo tóm tắt ngắn gọn"""
        if sentiment == 'positive':
            if score > 0.6:
                return "Tiến độ xuất sắc, công việc đạt hiệu quả cao"
            else:
                return "Tiến độ tốt, đang đi đúng hướng"
        elif sentiment == 'negative':
            if score < -0.6:
                return "Gặp nhiều khó khăn nghiêm trọng, cần hỗ trợ ngay"
            else:
                return "Có một số vấn đề cần chú ý"
        else:
            return "Tiến độ ổn định, bình thường"
