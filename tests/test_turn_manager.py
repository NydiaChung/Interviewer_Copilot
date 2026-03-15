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
    turn = tm.create_turn("hello", "hello", speaker_id=1, source_role="interviewer")

    assert tm.state == TurnState.RECORDING
    assert tm.is_recording()
    assert not tm.is_drafting()

    assert turn["id"] == 1
    assert turn["text"] == "hello"
    assert turn["norm"] == "hello"
    assert turn["speaker_id"] == 1
    assert turn["source_role"] == "interviewer"
    assert turn["closed"] is False
    assert turn["audio_last_ts"] <= time.monotonic()


def test_create_turn_default_source_role():
    tm = TurnManager()
    turn = tm.create_turn("q", "q", speaker_id=1)
    assert turn["source_role"] == "interviewer"


def test_mark_drafting():
    tm = TurnManager()
    tm.create_turn("q", "q", speaker_id=1)

    assert tm.state == TurnState.RECORDING
    tm.mark_drafting()
    assert tm.state == TurnState.DRAFTING
    assert tm.is_drafting()
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

    time.sleep(0.01)
    original_audio_ts = turn["audio_last_ts"]

    tm.update_turn_text("start continuing", "start continuing")

    assert turn["text"] == "start continuing"
    assert turn["norm"] == "start continuing"
    assert turn["text_last_ts"] > original_audio_ts


def test_no_turn_returns_false():
    tm = TurnManager()
    assert not tm.check_should_start_new_turn("interviewer")
    assert tm.last_new_turn_eval["reason"] == "no_turn"


def test_same_source_no_switch():
    tm = TurnManager()
    tm.create_turn("hello", "hello", speaker_id=1, source_role="interviewer")

    # 同一音源不开新气泡
    assert not tm.check_should_start_new_turn("interviewer")
    assert tm.last_new_turn_eval["reason"] == "same_source"


def test_source_switch_triggers_new_turn():
    tm = TurnManager()
    tm.create_turn("面试官说话", "面试官说话", speaker_id=1, source_role="interviewer")

    # 音源切换：面试官 → 候选人
    assert tm.check_should_start_new_turn("candidate")
    assert tm.last_new_turn_eval["reason"] == "source_switch"
    assert tm.last_new_turn_eval["from"] == "interviewer"
    assert tm.last_new_turn_eval["to"] == "candidate"


def test_source_switch_candidate_to_interviewer():
    tm = TurnManager()
    tm.create_turn("候选人说话", "候选人说话", speaker_id=2, source_role="candidate")

    # 音源切换：候选人 → 面试官
    assert tm.check_should_start_new_turn("interviewer")
    assert tm.last_new_turn_eval["reason"] == "source_switch"


def test_closed_turn_returns_false():
    tm = TurnManager()
    tm.create_turn("q", "q", speaker_id=1, source_role="interviewer")
    tm.mark_closed()

    assert not tm.check_should_start_new_turn("candidate")
    assert tm.last_new_turn_eval["reason"] == "no_turn"
