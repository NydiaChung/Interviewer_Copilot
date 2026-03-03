from server.intent import IntentReadinessDetector


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
    # Similar second partial should be deduped and not flood outline requests.
    assert detector.should_trigger_outline(p2, now=1.2) is False
