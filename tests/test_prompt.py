from server.prompt import INTERVIEW_PROMPT, OUTLINE_PROMPT, ANALYSIS_PROMPT


def test_interview_prompt_format():
    jd = "Python Dev"
    resume = "John Doe"
    question = "What is GIL?"
    formatted = INTERVIEW_PROMPT.format(jd=jd, resume=resume, question=question)
    assert jd in formatted
    assert resume in formatted
    assert question in formatted
    assert "求职者简历" in formatted


def test_outline_prompt_format():
    jd = "Java Dev"
    resume = "Jane Smith"
    question = "Explain JVM"
    formatted = OUTLINE_PROMPT.format(jd=jd, resume=resume, question=question)
    assert jd in formatted
    assert "回答提纲" in formatted
    assert question in formatted


def test_analysis_prompt_format():
    jd = "Data Scientist"
    resume = "Bob"
    history = "Q1: Hi\nA1: Hello"
    formatted = ANALYSIS_PROMPT.format(jd=jd, resume=resume, history=history)
    assert jd in formatted
    assert "复盘分析报告" in formatted
    assert history in formatted
