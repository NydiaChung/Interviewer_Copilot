import pytest
import time
from server.conversation.turn_manager import TurnManager
from server.conversation.turn_state import TurnState


def test_turn_manager_initial_state():
    tm = TurnManager()
    assert tm.state == TurnState.CLOSED
    assert not tm.is_recording()
    assert not tm.is_drafting()
    assert tm.current_turn is None


def test_create_turn():
    tm = TurnManager()
    turn = tm.create_turn("hello", "hello", speaker_id=1, asr_baseline="prev")

    assert tm.state == TurnState.RECORDING
    assert tm.is_recording()
    assert not tm.is_drafting()

    assert turn["id"] == 1
    assert turn["text"] == "hello"
    assert turn["norm"] == "hello"
    assert turn["speaker_id"] == 1
    assert turn["asr_baseline"] == "prev"
    assert turn["closed"] is False
    assert turn["audio_last_ts"] <= time.monotonic()


def test_mark_drafting():
    tm = TurnManager()
    tm.create_turn("q", "q", speaker_id=1)

    assert tm.state == TurnState.RECORDING
    tm.mark_drafting()
    assert tm.state == TurnState.DRAFTING
    assert tm.is_drafting()
    # Drafting is still considered recording for incoming text
    assert tm.is_recording()


def test_mark_closed():
    tm = TurnManager()
    turn = tm.create_turn("q", "q", speaker_id=1)

    tm.mark_closed()
    assert tm.state == TurnState.CLOSED
    assert not tm.is_recording()
    assert turn["closed"] is True


def test_update_turn_text():
    tm = TurnManager()
    turn = tm.create_turn("start", "start", speaker_id=1)

    # 模拟经过一段时间
    time.sleep(0.01)
    original_audio_ts = turn["audio_last_ts"]

    tm.update_turn_text("start continuing", "start continuing")

    assert turn["text"] == "start continuing"
    assert turn["norm"] == "start continuing"
    assert turn["text_last_ts"] > original_audio_ts


def test_should_start_new_turn_no_turn():
    tm = TurnManager()
    # 没有任何 current_turn 时
    assert not tm.check_should_start_new_turn("hello", 1, "interviewer")
    assert tm.last_new_turn_eval["reason"] == "no_turn"


def test_should_start_new_turn_candidate_takeover():
    tm = TurnManager()
    tm.create_turn("interviewer talking", "interviewer talking", speaker_id=1)

    # 候选人抢话时，不切分出新的面试官回合
    should_start = tm.check_should_start_new_turn("yes", 2, "candidate")
    assert not should_start
    assert tm.last_new_turn_eval["reason"] == "candidate_source_active"


def test_should_start_new_turn_short_text():
    tm = TurnManager()
    tm.create_turn("short", "short", speaker_id=1)

    # 文本过短时不轻易切分
    should_start = tm.check_should_start_new_turn("a", 1, "interviewer")
    assert not should_start
    assert tm.last_new_turn_eval["reason"] == "short_text_not_ready"


def test_should_start_new_turn_speaker_switched_with_gap():
    tm = TurnManager()
    turn = tm.create_turn(
        "hello a bit longer here", "hello a bit longer here", speaker_id=1
    )

    # 强制产生一点人为语音间隔 (假设过去了0.5s)
    turn["audio_last_ts"] = time.monotonic() - 0.5

    # 另一个人说话，且文本不相似
    should_start = tm.check_should_start_new_turn(
        "what about completely different", 2, "interviewer"
    )
    assert should_start
    assert tm.last_new_turn_eval["reason"] == "speaker_switch_gap"


def test_should_start_new_turn_similar_text():
    tm = TurnManager()
    turn = tm.create_turn(
        "What is your experience?", "whatisyourexperience", speaker_id=1
    )

    # 同一人延续极其相似的话语时不切分（通常是自我纠正）
    should_start = tm.check_should_start_new_turn(
        "whatisyourexperiencee", 1, "interviewer"
    )
    assert not should_start
    assert tm.last_new_turn_eval["reason"] == "similar_text_continue"


def test_should_start_new_turn_got_final():
    tm = TurnManager()
    turn = tm.create_turn("Can you explain?", "canyouexplain", speaker_id=1)
    turn["text"] = "Can you explain?"

    # ASR 上报最终句尾，同时有明显的语隙时间
    turn["audio_last_ts"] = time.monotonic() - 0.6

    should_start = tm.check_should_start_new_turn(
        "next sentence", 1, "interviewer", asr_got_final=True
    )
    assert should_start
    assert tm.last_new_turn_eval["reason"] == "got_final_question_like_pause"


def test_should_start_new_turn_question_like_pause():
    tm = TurnManager()
    turn = tm.create_turn("What?", "what", speaker_id=1)
    turn["text"] = "What is this?"  # contains question mark / word

    turn["audio_last_ts"] = time.monotonic() - 0.7

    # 哪怕 asr 没给 final，但是有提问特征和长停顿
    should_start = tm.check_should_start_new_turn("next one", 1, "interviewer")
    assert should_start
    assert tm.last_new_turn_eval["reason"] in (
        "question_like_pause",
        "low_similarity_question_like",
    )
