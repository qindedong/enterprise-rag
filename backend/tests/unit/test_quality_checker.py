"""质量检查器单元测试"""
import pytest
from app.rag.quality_checker import check_answer


class TestQualityChecker:
    def test_normal_answer_no_warnings(self):
        """正常回答：有引用标记，无幻觉"""
        answer = "根据公司规定，年假为 5 天 [1]。每增加 1 年加 1 天 [2]。"
        citations = [
            {"index": 1, "content_snippet": "年假为5天入职满1年享", "document_title": "考勤制度"},
            {"index": 2, "content_snippet": "每增加1年加1天上限15天", "document_title": "考勤制度"},
        ]
        warnings = check_answer(answer, citations)
        assert warnings == []

    def test_hallucinated_indices(self):
        """幻觉检测：引用编号越界"""
        answer = "年假为 5 天 [1]。加班费 3 倍 [5]。"
        citations = [
            {"index": 1, "content_snippet": "年假为5天", "document_title": "考勤制度"},
        ]
        warnings = check_answer(answer, citations)
        assert any("超出有效范围" in w["message"] for w in warnings)

    def test_no_citations_with_assertions(self):
        """幻觉检测：有事实断言但无引用标记"""
        answer = "根据公司规定，年假为 5 天。员工加班费为 3 倍工资。婚假为 3 天。"
        citations = [{"index": 1, "content_snippet": "年假为5天时长很充足", "document_title": "考勤制度"}]
        warnings = check_answer(answer, citations)
        assert any("无引用标记" in w["message"] for w in warnings), (
            f"应检测到无引用标记警告，实际: {[w['message'][:80] for w in warnings]}"
        )

    def test_content_match_warning(self):
        """内容不匹配：引用内容在回答中找不到"""
        answer = "根据公司规定 [1]，年假为 5 天。"
        citations = [
            {"index": 1, "content_snippet": "XYZ不相关文本内容在这里但是绝对找不到匹配的", "document_title": "考勤制度"},
        ]
        warnings = check_answer(answer, citations)
        assert any("未找到精确匹配" in w["message"] for w in warnings), (
            f"应检测到内容不匹配警告，实际: {[w['message'][:80] for w in warnings]}"
        )

    def test_empty_answer(self):
        """空回答"""
        warnings = check_answer("", [])
        assert warnings == []

    def test_cannot_answer_text(self):
        """明确说'无法回答'"""
        answer = "根据现有资料，无法回答这个问题。建议换个方式提问。"
        citations = []
        warnings = check_answer(answer, citations)
        assert not any(
            "无引用标记" in w["message"] for w in warnings
        ), "说'无法回答'时不应报幻觉"
