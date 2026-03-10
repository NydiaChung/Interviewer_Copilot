e": "mic", "mic_rms": 472, "system_rms": 0, "changed": false}
[ASR-Tingwu] ResultChanged: 咋没那么好，我 (speaker=None, name=None)
[Callback-Main] Received: 咋没那么好，我 (is_end=False)
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 629, "event": "asr_text_update", "mono_ts": 38437.666, "current_turn_id": 26, "is_sentence_end": false, "speaker_id": null, "source_role": "interviewer", "text_preview": "咋没那么好，我", "text_len": 7}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 630, "event": "new_turn_not_detected", "mono_ts": 38437.666, "prev_turn_id": 26, "trigger": false, "reason": "candidate_source_active", "sim": null, "speech_gap": 0.088, "speaker_switched": false, "source_role": "candidate"}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 631, "event": "ws_incremental_sent", "mono_ts": 38437.666, "stream": "main", "speaker_role": "interviewer", "question_id": 26, "text_preview": "我"}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 632, "event": "source_activity", "mono_ts": 38437.834, "dominant_source": "mic", "mic_rms": 312, "system_rms": 0, "changed": false}
[LLM] Answer(seq=23): 我刚在众唯安做电商决策Agent时也遇到过类似问题——SOP子图执行成功率一开始才72%，后来通过加OutputFixingParser自动修复、优化Pydantic Schema校验，两周内提到了95%。您这问题具体卡在哪？我帮您一起调。
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 23, "event": "answer_generation_done", "mono_ts": 38437.982, "source": "asr", "question_id": 24, "answer_len": 120}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 634, "event": "turn_close_poll", "mono_ts": 38438.169, "turn_id": 26, "reason": "silence", "force": false, "silence": 0.165, "got_final": false, "is_question_like": false, "voiceprint_close": false, "source_takeover_close": false, "source_role": "candidate", "speaker_switched": false, "dominant_speaker": 1}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 635, "event": "source_activity", "mono_ts": 38438.178, "dominant_source": "none", "mic_rms": 219, "system_rms": 0, "changed": true}
[ASR-Tingwu] ResultChanged: 咋没那么好？是 (speaker=None, name=None)
[Callback-Main] Received: 咋没那么好？是 (is_end=False)
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 636, "event": "asr_text_update", "mono_ts": 38438.265, "current_turn_id": 26, "is_sentence_end": false, "speaker_id": null, "source_role": "interviewer", "text_preview": "咋没那么好？是", "text_len": 7}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 637, "event": "new_turn_not_detected", "mono_ts": 38438.265, "prev_turn_id": 26, "trigger": false, "reason": "short_text_not_ready", "sim": null, "speech_gap": 0.262, "speaker_switched": false, "source_role": "unknown"}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 638, "event": "ws_incremental_sent", "mono_ts": 38438.266, "stream": "main", "speaker_role": "interviewer", "question_id": 26, "text_preview": "是"}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 639, "event": "source_activity", "mono_ts": 38438.433, "dominant_source": "none", "mic_rms": 107, "system_rms": 0, "changed": false}
[ASR-Tingwu] ResultChanged: 咋没那么好是吧？ (speaker=None, name=None)
[Callback-Main] Received: 咋没那么好是吧？ (is_end=False)
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 640, "event": "asr_text_update", "mono_ts": 38438.524, "current_turn_id": 26, "is_sentence_end": false, "speaker_id": null, "source_role": "interviewer", "text_preview": "咋没那么好是吧？", "text_len": 8}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 641, "event": "new_turn_not_detected", "mono_ts": 38438.524, "prev_turn_id": 26, "trigger": false, "reason": "short_text_not_ready", "sim": null, "speech_gap": 0.521, "speaker_switched": false, "source_role": "unknown"}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 642, "event": "ws_incremental_sent", "mono_ts": 38438.525, "stream": "main", "speaker_role": "interviewer", "question_id": 26, "text_preview": "咋没那么好是吧？"}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 643, "event": "source_activity", "mono_ts": 38438.771, "dominant_source": "mic", "mic_rms": 318, "system_rms": 0, "changed": true}
[Turn] 关闭 turn=26  reason=silence  silence=0.00s  got_final=False  voiceprint_close=False  source_takeover_close=True  speaker_switched=False  dominant_speaker=1
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 644, "event": "turn_closed", "mono_ts": 38438.776, "turn_id": 26, "reason": "silence", "force": false, "silence": 0.005, "got_final": false, "is_question_like": true, "voiceprint_close": false, "source_takeover_close": true, "source_role": "candidate", "speaker_switched": false, "dominant_speaker": 1}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 25, "event": "answer_scheduled", "mono_ts": 38438.776, "source": "asr", "question_id": 26, "question_preview": "咋没那么好是吧？"}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 25, "event": "answer_generation_start", "mono_ts": 38438.776, "source": "asr", "question_id": 26}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 647, "event": "source_activity", "mono_ts": 38439.031, "dominant_source": "none", "mic_rms": 164, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 648, "event": "source_activity", "mono_ts": 38439.456, "dominant_source": "none", "mic_rms": 79, "system_rms": 0, "changed": false}
[ASR-Tingwu] ResultChanged: 咋没那么好，竹子 (speaker=None, name=None)
[Callback-Main] Received: 咋没那么好，竹子 (is_end=False)
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 649, "event": "asr_text_update", "mono_ts": 38439.739, "current_turn_id": null, "is_sentence_end": false, "speaker_id": null, "source_role": "interviewer", "text_preview": "咋没那么好，竹子", "text_len": 8}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 650, "event": "turn_created", "mono_ts": 38439.739, "turn_id": 27, "speaker_id": null, "text_preview": "咋没那么好，竹子"}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 651, "event": "ws_incremental_sent", "mono_ts": 38439.74, "stream": "main", "speaker_role": "interviewer", "question_id": 27, "text_preview": "咋没那么好，竹子"}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 652, "event": "source_activity", "mono_ts": 38439.797, "dominant_source": "none", "mic_rms": 91, "system_rms": 0, "changed": false}
[LLM] Answer(seq=24): 哎呀，您可能没看到我最近在众唯安做的电商决策Agent系统——用LangGraph搭的Supervisor+Workers架构，6大场景意图识别准确率92%+，SOP任务成功率95%，报告生成10分钟搞定，比人工快60%多！
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 24, "event": "answer_generation_done", "mono_ts": 38439.842, "source": "asr", "question_id": 25, "answer_len": 112}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 654, "event": "turn_close_poll", "mono_ts": 38439.991, "turn_id": 27, "reason": "silence", "force": false, "silence": 0.252, "got_final": false, "is_question_like": true, "voiceprint_close": false, "source_takeover_close": false, "source_role": "unknown", "speaker_switched": false, "dominant_speaker": 1}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 655, "event": "source_activity", "mono_ts": 38440.052, "dominant_source": "none", "mic_rms": 92, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 656, "event": "source_activity", "mono_ts": 38440.396, "dominant_source": "none", "mic_rms": 108, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 657, "event": "source_activity", "mono_ts": 38440.651, "dominant_source": "none", "mic_rms": 120, "system_rms": 0, "changed": false}
[Turn] 关闭 turn=27  reason=silence  silence=1.00s  got_final=False  voiceprint_close=False  source_takeover_close=False  speaker_switched=False  dominant_speaker=1
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 658, "event": "turn_closed", "mono_ts": 38440.743, "turn_id": 27, "reason": "silence", "force": false, "silence": 1.004, "got_final": false, "is_question_like": true, "voiceprint_close": false, "source_takeover_close": false, "source_role": "unknown", "speaker_switched": false, "dominant_speaker": 1}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 26, "event": "answer_scheduled", "mono_ts": 38440.744, "source": "asr", "question_id": 27, "question_preview": "咋没那么好，竹子"}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 26, "event": "answer_generation_start", "mono_ts": 38440.744, "source": "asr", "question_id": 27}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 661, "event": "source_activity", "mono_ts": 38440.992, "dominant_source": "none", "mic_rms": 95, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 662, "event": "source_activity", "mono_ts": 38441.248, "dominant_source": "none", "mic_rms": 98, "system_rms": 0, "changed": false}
[LLM] Answer(seq=25): 其实挺好的！刚在众唯安用LangGraph搭的电商Agent系统，意图识别准确率92%+，SOP任务成功率95%，运营效率直接提了60%——这数据是实打实跑出来的。
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 25, "event": "answer_generation_done", "mono_ts": 38441.512, "source": "asr", "question_id": 26, "answer_len": 82}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 664, "event": "source_activity", "mono_ts": 38441.588, "dominant_source": "none", "mic_rms": 85, "system_rms": 0, "changed": false}
[ASR-Tingwu] SentenceEnd: speaker=None name=None text=咋没那么好，竹子。 stash=
DEBUG: Tingwu Final Text: 咋没那么好，竹子。
[Callback-Main] Received: 咋没那么好，竹子。 (is_end=True)
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 665, "event": "asr_text_update", "mono_ts": 38441.646, "current_turn_id": null, "is_sentence_end": true, "speaker_id": null, "source_role": "interviewer", "text_preview": "咋没那么好，竹子。", "text_len": 9}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 666, "event": "turn_created", "mono_ts": 38441.646, "turn_id": 28, "speaker_id": null, "text_preview": "咋没那么好，竹子。"}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 667, "event": "ws_incremental_sent", "mono_ts": 38441.646, "stream": "main", "speaker_role": "interviewer", "question_id": 28, "text_preview": "咋没那么好，竹子。"}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 668, "event": "asr_sentence_end", "mono_ts": 38441.646, "turn_id": 28, "text_preview": "咋没那么好，竹子。"}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 669, "event": "turn_close_skipped", "mono_ts": 38441.646, "turn_id": 28, "reason": "asr_final", "force": false, "silence": 0.0, "got_final": true, "is_question_like": true, "voiceprint_close": false, "source_takeover_close": false, "source_role": "unknown", "speaker_switched": false, "dominant_speaker": 1}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 670, "event": "source_activity", "mono_ts": 38441.847, "dominant_source": "none", "mic_rms": 80, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 671, "event": "source_activity", "mono_ts": 38442.185, "dominant_source": "none", "mic_rms": 89, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 672, "event": "source_activity", "mono_ts": 38442.441, "dominant_source": "none", "mic_rms": 88, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 673, "event": "source_activity", "mono_ts": 38442.782, "dominant_source": "none", "mic_rms": 88, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 674, "event": "source_activity", "mono_ts": 38443.038, "dominant_source": "none", "mic_rms": 94, "system_rms": 0, "changed": false}
[LLM] Answer(seq=26): 哎呀，您这么一说我想起来了——上次在微软做AI_Search时，LangGraph状态图里有个路由节点老是漏判“small talk”，后来我加了Safety Override双重验证才搞定，可能这会儿又冒出来啦！
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 26, "event": "answer_generation_done", "mono_ts": 38443.266, "source": "asr", "question_id": 27, "answer_len": 107}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 676, "event": "source_activity", "mono_ts": 38443.381, "dominant_source": "none", "mic_rms": 82, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 677, "event": "source_activity", "mono_ts": 38443.635, "dominant_source": "none", "mic_rms": 85, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 678, "event": "source_activity", "mono_ts": 38443.978, "dominant_source": "none", "mic_rms": 79, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 679, "event": "source_activity", "mono_ts": 38444.233, "dominant_source": "none", "mic_rms": 96, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 680, "event": "source_activity", "mono_ts": 38444.577, "dominant_source": "none", "mic_rms": 90, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 681, "event": "source_activity", "mono_ts": 38444.83, "dominant_source": "none", "mic_rms": 87, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 682, "event": "source_activity", "mono_ts": 38445.171, "dominant_source": "none", "mic_rms": 79, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 683, "event": "source_activity", "mono_ts": 38445.427, "dominant_source": "none", "mic_rms": 75, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 684, "event": "source_activity", "mono_ts": 38445.854, "dominant_source": "none", "mic_rms": 83, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 685, "event": "source_activity", "mono_ts": 38446.197, "dominant_source": "none", "mic_rms": 88, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 686, "event": "source_activity", "mono_ts": 38446.454, "dominant_source": "none", "mic_rms": 81, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 687, "event": "source_activity", "mono_ts": 38446.796, "dominant_source": "none", "mic_rms": 90, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 688, "event": "source_activity", "mono_ts": 38447.051, "dominant_source": "none", "mic_rms": 83, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 689, "event": "source_activity", "mono_ts": 38447.392, "dominant_source": "none", "mic_rms": 90, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 690, "event": "source_activity", "mono_ts": 38447.649, "dominant_source": "none", "mic_rms": 85, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 691, "event": "source_activity", "mono_ts": 38447.99, "dominant_source": "none", "mic_rms": 88, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 692, "event": "source_activity", "mono_ts": 38448.248, "dominant_source": "none", "mic_rms": 81, "system_rms": 0, "changed": false}
[Audio-Silence] turn=28 silence=6.77s
[WS] Main audio frame #401 size=6400B
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 693, "event": "audio_frame", "mono_ts": 38448.585, "recv_count": 401, "turn_id": 28, "speaker_id": null, "dominant_speaker": 1, "active_audio": false, "rms": 84, "frame_bytes": 6400}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 694, "event": "source_activity", "mono_ts": 38448.585, "dominant_source": "none", "mic_rms": 84, "system_rms": 0, "changed": false}
[WS-DEBUG] ASGI received dict with 'bytes' length: 6400
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 695, "event": "source_activity", "mono_ts": 38448.845, "dominant_source": "none", "mic_rms": 82, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 696, "event": "source_activity", "mono_ts": 38449.184, "dominant_source": "none", "mic_rms": 79, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 697, "event": "source_activity", "mono_ts": 38449.441, "dominant_source": "none", "mic_rms": 77, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 698, "event": "source_activity", "mono_ts": 38449.782, "dominant_source": "none", "mic_rms": 73, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 699, "event": "source_activity", "mono_ts": 38450.036, "dominant_source": "none", "mic_rms": 81, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 700, "event": "source_activity", "mono_ts": 38450.381, "dominant_source": "none", "mic_rms": 77, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 701, "event": "source_activity", "mono_ts": 38450.636, "dominant_source": "none", "mic_rms": 81, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 702, "event": "source_activity", "mono_ts": 38450.976, "dominant_source": "none", "mic_rms": 66, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 703, "event": "source_activity", "mono_ts": 38451.232, "dominant_source": "none", "mic_rms": 73, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 704, "event": "source_activity", "mono_ts": 38451.574, "dominant_source": "none", "mic_rms": 65, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 705, "event": "source_activity", "mono_ts": 38451.831, "dominant_source": "none", "mic_rms": 78, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 706, "event": "source_activity", "mono_ts": 38452.256, "dominant_source": "none", "mic_rms": 71, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 707, "event": "source_activity", "mono_ts": 38452.597, "dominant_source": "none", "mic_rms": 78, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 708, "event": "source_activity", "mono_ts": 38452.853, "dominant_source": "none", "mic_rms": 79, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 709, "event": "source_activity", "mono_ts": 38453.194, "dominant_source": "none", "mic_rms": 66, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 710, "event": "source_activity", "mono_ts": 38453.45, "dominant_source": "none", "mic_rms": 77, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 711, "event": "source_activity", "mono_ts": 38453.79, "dominant_source": "none", "mic_rms": 77, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 712, "event": "source_activity", "mono_ts": 38454.049, "dominant_source": "none", "mic_rms": 84, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 713, "event": "source_activity", "mono_ts": 38454.389, "dominant_source": "none", "mic_rms": 74, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 714, "event": "source_activity", "mono_ts": 38454.647, "dominant_source": "none", "mic_rms": 83, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 715, "event": "source_activity", "mono_ts": 38454.988, "dominant_source": "none", "mic_rms": 79, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 716, "event": "source_activity", "mono_ts": 38455.245, "dominant_source": "none", "mic_rms": 70, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 717, "event": "source_activity", "mono_ts": 38455.585, "dominant_source": "none", "mic_rms": 76, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 718, "event": "source_activity", "mono_ts": 38455.841, "dominant_source": "none", "mic_rms": 74, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 719, "event": "source_activity", "mono_ts": 38456.183, "dominant_source": "none", "mic_rms": 74, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 720, "event": "source_activity", "mono_ts": 38456.437, "dominant_source": "none", "mic_rms": 74, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 721, "event": "source_activity", "mono_ts": 38456.782, "dominant_source": "none", "mic_rms": 71, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 722, "event": "source_activity", "mono_ts": 38457.036, "dominant_source": "none", "mic_rms": 62, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 723, "event": "source_activity", "mono_ts": 38457.378, "dominant_source": "none", "mic_rms": 72, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 724, "event": "source_activity", "mono_ts": 38457.63, "dominant_source": "none", "mic_rms": 60, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 725, "event": "source_activity", "mono_ts": 38457.972, "dominant_source": "none", "mic_rms": 82, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 726, "event": "source_activity", "mono_ts": 38458.227, "dominant_source": "none", "mic_rms": 72, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 727, "event": "source_activity", "mono_ts": 38458.398, "dominant_source": "mic", "mic_rms": 1014, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 728, "event": "source_activity", "mono_ts": 38458.654, "dominant_source": "none", "mic_rms": 90, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 729, "event": "source_activity", "mono_ts": 38458.995, "dominant_source": "none", "mic_rms": 79, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 730, "event": "source_activity", "mono_ts": 38459.251, "dominant_source": "none", "mic_rms": 70, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 731, "event": "source_activity", "mono_ts": 38459.593, "dominant_source": "none", "mic_rms": 69, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 732, "event": "source_activity", "mono_ts": 38459.852, "dominant_source": "none", "mic_rms": 71, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 733, "event": "source_activity", "mono_ts": 38460.192, "dominant_source": "none", "mic_rms": 63, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 734, "event": "source_activity", "mono_ts": 38460.449, "dominant_source": "none", "mic_rms": 66, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 735, "event": "source_activity", "mono_ts": 38460.789, "dominant_source": "none", "mic_rms": 66, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 736, "event": "source_activity", "mono_ts": 38461.046, "dominant_source": "none", "mic_rms": 68, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 737, "event": "source_activity", "mono_ts": 38461.393, "dominant_source": "mic", "mic_rms": 413, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 738, "event": "source_activity", "mono_ts": 38461.644, "dominant_source": "none", "mic_rms": 66, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 739, "event": "source_activity", "mono_ts": 38461.985, "dominant_source": "none", "mic_rms": 72, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 740, "event": "source_activity", "mono_ts": 38462.241, "dominant_source": "none", "mic_rms": 75, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 741, "event": "source_activity", "mono_ts": 38462.589, "dominant_source": "none", "mic_rms": 69, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 742, "event": "source_activity", "mono_ts": 38462.836, "dominant_source": "none", "mic_rms": 81, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 743, "event": "source_activity", "mono_ts": 38463.18, "dominant_source": "none", "mic_rms": 77, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 744, "event": "source_activity", "mono_ts": 38463.437, "dominant_source": "none", "mic_rms": 88, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 745, "event": "source_activity", "mono_ts": 38463.774, "dominant_source": "none", "mic_rms": 67, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 746, "event": "source_activity", "mono_ts": 38464.032, "dominant_source": "none", "mic_rms": 93, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 747, "event": "source_activity", "mono_ts": 38464.376, "dominant_source": "none", "mic_rms": 64, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 748, "event": "audio_frame", "mono_ts": 38464.628, "recv_count": 481, "turn_id": 28, "speaker_id": null, "dominant_speaker": 1, "active_audio": false, "rms": 80, "frame_bytes": 6400}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 749, "event": "source_activity", "mono_ts": 38464.628, "dominant_source": "none", "mic_rms": 80, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 750, "event": "source_activity", "mono_ts": 38464.799, "dominant_source": "mic", "mic_rms": 293, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 751, "event": "source_activity", "mono_ts": 38465.055, "dominant_source": "none", "mic_rms": 83, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 752, "event": "source_activity", "mono_ts": 38465.397, "dominant_source": "none", "mic_rms": 66, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 753, "event": "source_activity", "mono_ts": 38465.654, "dominant_source": "none", "mic_rms": 67, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 754, "event": "source_activity", "mono_ts": 38465.995, "dominant_source": "none", "mic_rms": 65, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 755, "event": "source_activity", "mono_ts": 38466.251, "dominant_source": "none", "mic_rms": 57, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 756, "event": "source_activity", "mono_ts": 38466.59, "dominant_source": "none", "mic_rms": 80, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 757, "event": "source_activity", "mono_ts": 38466.848, "dominant_source": "none", "mic_rms": 70, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 758, "event": "source_activity", "mono_ts": 38467.187, "dominant_source": "none", "mic_rms": 71, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 759, "event": "source_activity", "mono_ts": 38467.447, "dominant_source": "none", "mic_rms": 73, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 760, "event": "source_activity", "mono_ts": 38467.787, "dominant_source": "none", "mic_rms": 87, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 761, "event": "source_activity", "mono_ts": 38468.044, "dominant_source": "none", "mic_rms": 73, "system_rms": 0, "changed": false}
[Audio-Silence] turn=28 silence=3.59s
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 762, "event": "source_activity", "mono_ts": 38468.385, "dominant_source": "none", "mic_rms": 60, "system_rms": 0, "changed": false}
[WS] Main audio frame #501 size=6400B
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 763, "event": "source_activity", "mono_ts": 38468.642, "dominant_source": "none", "mic_rms": 81, "system_rms": 0, "changed": false}
[WS-DEBUG] ASGI received dict with 'bytes' length: 6400
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 764, "event": "source_activity", "mono_ts": 38468.983, "dominant_source": "none", "mic_rms": 61, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 765, "event": "source_activity", "mono_ts": 38469.239, "dominant_source": "none", "mic_rms": 74, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 766, "event": "source_activity", "mono_ts": 38469.579, "dominant_source": "none", "mic_rms": 64, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 767, "event": "source_activity", "mono_ts": 38469.834, "dominant_source": "none", "mic_rms": 48, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 768, "event": "source_activity", "mono_ts": 38470.179, "dominant_source": "none", "mic_rms": 49, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 769, "event": "source_activity", "mono_ts": 38470.434, "dominant_source": "none", "mic_rms": 58, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 770, "event": "source_activity", "mono_ts": 38470.773, "dominant_source": "none", "mic_rms": 203, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 771, "event": "source_activity", "mono_ts": 38471.028, "dominant_source": "none", "mic_rms": 111, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 772, "event": "source_activity", "mono_ts": 38471.202, "dominant_source": "mic", "mic_rms": 721, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 773, "event": "source_activity", "mono_ts": 38471.456, "dominant_source": "none", "mic_rms": 83, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 774, "event": "source_activity", "mono_ts": 38471.797, "dominant_source": "none", "mic_rms": 90, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 775, "event": "source_activity", "mono_ts": 38472.053, "dominant_source": "mic", "mic_rms": 818, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 776, "event": "source_activity", "mono_ts": 38472.395, "dominant_source": "none", "mic_rms": 130, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 777, "event": "source_activity", "mono_ts": 38472.651, "dominant_source": "none", "mic_rms": 111, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 778, "event": "source_activity", "mono_ts": 38472.821, "dominant_source": "mic", "mic_rms": 382, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 779, "event": "source_activity", "mono_ts": 38473.248, "dominant_source": "mic", "mic_rms": 3173, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 780, "event": "source_activity", "mono_ts": 38473.588, "dominant_source": "none", "mic_rms": 195, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 781, "event": "source_activity", "mono_ts": 38473.848, "dominant_source": "none", "mic_rms": 165, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 782, "event": "source_activity", "mono_ts": 38474.016, "dominant_source": "mic", "mic_rms": 1261, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 783, "event": "source_activity", "mono_ts": 38474.441, "dominant_source": "mic", "mic_rms": 2314, "system_rms": 0, "changed": false}
[Voiceprint] Speaker confirmed: 1 → 2 (frames=4)
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 784, "event": "source_activity", "mono_ts": 38474.785, "dominant_source": "mic", "mic_rms": 2328, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 785, "event": "source_activity", "mono_ts": 38475.038, "dominant_source": "mic", "mic_rms": 2179, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 786, "event": "source_activity", "mono_ts": 38475.209, "dominant_source": "none", "mic_rms": 95, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 787, "event": "source_activity", "mono_ts": 38475.638, "dominant_source": "none", "mic_rms": 83, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 788, "event": "source_activity", "mono_ts": 38475.98, "dominant_source": "none", "mic_rms": 200, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 789, "event": "source_activity", "mono_ts": 38476.236, "dominant_source": "none", "mic_rms": 94, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 790, "event": "source_activity", "mono_ts": 38476.576, "dominant_source": "none", "mic_rms": 133, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 791, "event": "source_activity", "mono_ts": 38476.831, "dominant_source": "none", "mic_rms": 80, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 792, "event": "source_activity", "mono_ts": 38477.172, "dominant_source": "none", "mic_rms": 98, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 793, "event": "source_activity", "mono_ts": 38477.429, "dominant_source": "none", "mic_rms": 81, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 794, "event": "source_activity", "mono_ts": 38477.855, "dominant_source": "none", "mic_rms": 242, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 795, "event": "source_activity", "mono_ts": 38478.027, "dominant_source": "mic", "mic_rms": 366, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 796, "event": "source_activity", "mono_ts": 38478.454, "dominant_source": "none", "mic_rms": 106, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 797, "event": "source_activity", "mono_ts": 38478.793, "dominant_source": "mic", "mic_rms": 895, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 798, "event": "source_activity", "mono_ts": 38479.051, "dominant_source": "none", "mic_rms": 127, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 799, "event": "source_activity", "mono_ts": 38479.392, "dominant_source": "none", "mic_rms": 84, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 800, "event": "source_activity", "mono_ts": 38479.649, "dominant_source": "none", "mic_rms": 99, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 801, "event": "source_activity", "mono_ts": 38479.999, "dominant_source": "none", "mic_rms": 125, "system_rms": 0, "changed": false}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 802, "event": "source_activity", "mono_ts": 38480.248, "dominant_source": "mic", "mic_rms": 290, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 803, "event": "source_activity", "mono_ts": 38480.416, "dominant_source": "none", "mic_rms": 199, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 804, "event": "audio_frame", "mono_ts": 38480.586, "recv_count": 561, "turn_id": 28, "speaker_id": 2, "dominant_speaker": 2, "active_audio": true, "rms": 2114, "frame_bytes": 6400}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 805, "event": "source_activity", "mono_ts": 38480.586, "dominant_source": "mic", "mic_rms": 2114, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 806, "event": "source_activity", "mono_ts": 38480.845, "dominant_source": "none", "mic_rms": 103, "system_rms": 0, "changed": true}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 807, "event": "source_activity", "mono_ts": 38481.014, "dominant_source": "mic", "mic_rms": 587, "system_rms": 0, "changed": true}
[WS-DEBUG] ASGI received dict with 'text': {"command": "end_session"}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 808, "event": "command_end_session", "mono_ts": 38481.361}
[Memory] Session ended by user. Generating analysis for: 20260310_085330
[ASR-Tingwu] 任务已结束: {"Code":"0","Data":{"TaskId":"de9dd24fbcc74c1ab3b83a7a64472826","TaskKey":"interview_61bbe02f","TaskStatus":"ONGOING"},"Message":"success","RequestId":"5E64000B-A944-5EF7-B745-F46AC4972E0C"}
[Turn] 关闭 turn=28  reason=session_end  silence=1.21s  got_final=True  voiceprint_close=False  source_takeover_close=False  speaker_switched=False  dominant_speaker=2
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 809, "event": "turn_closed", "mono_ts": 38482.398, "turn_id": 28, "reason": "session_end", "force": true, "silence": 1.215, "got_final": true, "is_question_like": true, "voiceprint_close": false, "source_takeover_close": false, "source_role": "unknown", "speaker_switched": false, "dominant_speaker": 2}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 27, "event": "answer_scheduled", "mono_ts": 38482.398, "source": "asr", "question_id": 28, "question_preview": "咋没那么好，竹子。"}
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 27, "event": "answer_generation_start", "mono_ts": 38482.398, "source": "asr", "question_id": 28}
[LLM] Answer(seq=27): 哎呀，可能刚才我讲得太快了——比如在众唯安做电商决策Agent时，MonitorAgent意图识别92%准确率，但初期只有78%，我是通过把6大场景的query pattern拆开、单独微调分类器才拉上去的。
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 27, "event": "answer_generation_done", "mono_ts": 38484.26, "source": "asr", "question_id": 28, "answer_len": 104}
[LLM] 调用超时（>45s）
[Trace] {"trace_id": "20260310_085330-d411a1f1", "session_id": "20260310_085330", "seq": 813, "event": "ws_session_finalizing", "mono_ts": 38529.518, "transcript_size": 27}
INFO:     connection closed





qt.qpa.fonts: Populating font family aliases took 284 ms. Replace uses of missing font family "-apple-system" with one that exists to avoid this cost.
2026-03-09 11:28:16.627 python3.10[14681:176903] TSM AdjustCapsLockLEDForKeyTransitionHandling - _ISSetPhysicalKeyboardCapsLockLED Inhibit
2026-03-09 11:58:14.476 python3.10[14681:176903] error messaging the mach port for IMKCFRunLoopWakeUpReliable
zy@zy-MacBook-Pro Interviewer % python desktop_app/main.py
qt.qpa.fonts: Populating font family aliases took 258 ms. Replace uses of missing font family "-apple-system" with one that exists to avoid this cost.
2026-03-10 08:53:21.473 python3.10[32632:706587] error messaging the mach port for IMKCFRunLoopWakeUpReliable
2026-03-10 08:53:22.274 python3.10[32632:706587] TSM AdjustCapsLockLEDForKeyTransitionHandling - _ISSetPhysicalKeyboardCapsLockLED Inhibit
[Audio] 麦克风   → #3: MacBook Pro麦克风
[Audio] 系统声音 → #2: BlackHole 2ch  ch=2  rate=48000
[Audio] 麦克风流已开启（16kHz）
[Audio] BlackHole 流已开启， system_index=2，  ch=2  48000Hz→16000Hz  (audioop.ratecv)
[Desktop] Connected to Interview Copilot backend.
