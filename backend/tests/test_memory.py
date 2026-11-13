from app.agents.graph import merge_memory, memory_from, ask_for_missing


def test_marks_merge_across_turns():
    mem = memory_from({"intent": "admission_eligibility", "programme": "B.Tech CSE", "marks": {"Physics": 65, "IT": 74}})
    u = merge_memory({"intent": "general", "marks": {"Mathematics": 44}}, mem, "I GOT 44 IN MATHS")
    assert u["marks"] == {"Physics": 65, "IT": 74, "Mathematics": 44}
    assert u["intent"] == "admission_eligibility" and u["programme"] == "B.Tech CSE"


def test_new_value_replaces_same_subject():
    mem = {"marks": {"Maths": 44, "Physics": 65}}
    u = merge_memory({"intent": "admission_eligibility", "marks": {"Mathematics": 80}}, mem, "sorry maths was 80")
    assert u["marks"] == {"Physics": 65, "Mathematics": 80}


def test_new_programme_keeps_marks():
    mem = {"intent": "admission_eligibility", "programme": "B.Tech CSE", "marks": {"Physics": 70, "Maths": 80, "English": 75}}
    u = merge_memory({"intent": "admission_eligibility", "programme": "BBA"}, mem, "what about BBA")
    assert u["programme"] == "BBA" and u["marks"]["Physics"] == 70


def test_no_memory_is_noop():
    u = {"intent": "fees", "programme": "BBA"}
    assert merge_memory(u, {}, "BBA fees") == u


def test_ask_for_missing_example():
    out = ask_for_missing(["Physics %", "your highest-scoring other subject and its % (not vocational)"])
    assert "- Physics %" in out and "Example reply: Physics 78, English 88" in out
