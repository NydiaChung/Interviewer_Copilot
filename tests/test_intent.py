from server.conversation.intent_detector import IntentReadinessDetector
from server.conversation.turn_rules import is_question_like


def test_intent_trigger_on_clear_question():
    detector = IntentReadinessDetector(min_score=4)
    text = "你能介绍一下你在支付项目里的职责吗"
    assert detector.should_trigger_outline(text, now=1.0) is True


def test_intent_dedup_blocks_duplicate_trigger():
    detector = IntentReadinessDetector(min_score=4, debounce_seconds=0.1)
    text = "你在这个项目里主要做了什么，遇到过哪些挑战？"
    assert detector.should_trigger_outline(text, now=1.0) is True
    assert detector.should_trigger_outline(text, now=2.0) is False


def test_intent_reset_allows_next_question():
    detector = IntentReadinessDetector(min_score=4)
    text = "为什么这次性能优化会有效？"
    assert detector.should_trigger_outline(text, now=1.0) is True
    detector.reset()
    assert detector.should_trigger_outline(text, now=2.0) is True


def test_intent_stability_can_trigger_without_question_mark():
    detector = IntentReadinessDetector(min_score=4)
    p1 = "你在项目里做了哪些性能优化"
    p2 = "你在项目里做了哪些性能优化 具体怎么做"
    assert detector.should_trigger_outline(p1, now=1.0) is True
    # 相似的第二个中间结果应被去重过滤
    assert detector.should_trigger_outline(p2, now=1.2) is False


# Fix 5: 陆述式问题词汇覆盖测试
def test_is_question_like_declarative_patterns():
    """陆述式问题（不含问号）应被判定为问题。"""
    assert is_question_like("说说你在这个项目中的责任") is True
    assert is_question_like("具体介绍一下你的项目背景") is True
    assert is_question_like("你有哪些相关经验") is True
    assert is_question_like("遇到了什么挑战") is True
    assert is_question_like("构建了什么技术方案") is True


def test_is_question_like_interrogative_patterns():
    """疆问句应被判定为问题。"""
    assert is_question_like("你怎么处理这个问题？") is True
    assert is_question_like("为什么恋选这个方案") is True
    assert is_question_like("你是否了解 tradeoff") is True


def test_is_question_like_plain_statement_returns_false():
    """纯陈述的句子不应被识别为问题。"""
    assert is_question_like("我在阶段主要负责后端架构") is False
    assert is_question_like("项目于 2023 年上线") is False
    assert is_question_like("") is False


def test_intent_should_trigger_outline_short_text():
    detector = IntentReadinessDetector(min_chars=6)
    # 刚好小于6个字符的纯文本
    assert detector.should_trigger_outline("短文本", now=1.0) is False
    assert detector._last_text == "短文本"

    # 空文本
    assert detector.should_trigger_outline("", now=2.0) is False
    assert detector._last_text == ""


def test_similarity_empty():
    from server.utils.text import text_similarity

    assert text_similarity("", "abc") == 0.0
    assert text_similarity("abc", "") == 0.0
    assert text_similarity(None, "abc") == 0.0
