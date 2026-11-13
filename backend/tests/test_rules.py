"""Unit tests for the deterministic rule engine. Run: uv run pytest -q"""
import app.rules.engine as R
from app.rules.engine import (INSUFFICIENT, MEETS, NEEDS_VERIFICATION, NOT_MET, best_of_three, check_admission,
                              check_attendance, classes_needed)

BTECH_CSE = {"min_percentage": 55, "ib_min_credits": 24, "score_basis": "class12_best_of_3",
             "compulsory_subjects": ["Physics", "Mathematics"],
             "excluded_third_subjects": ["Music", "Dance", "Painting", "Home Science", "Arts"]}


def test_best_of_three_uses_compulsory_plus_highest():
    score, chosen, err = best_of_three({"Physics": 80, "Maths": 70, "Chemistry": 60, "English": 90},
                                       ["Physics", "Mathematics"], [])
    assert err is None and chosen == ["Physics", "Mathematics", "English"] and score == 80.0


def test_vocational_subject_not_counted():
    score, chosen, _ = best_of_three({"Physics": 50, "Mathematics": 50, "Music": 100, "Chemistry": 60},
                                     ["Physics", "Mathematics"], ["Music"])
    assert "Music" not in chosen and score == round((50 + 50 + 60) / 3, 2)


def test_meets_btech_cse():
    r = check_admission({"marks": {"Physics": 88, "Chemistry": 85, "Maths": 91}}, BTECH_CSE)
    assert r.status == MEETS and r.computed["best_of_3"] == 88.0


def test_boundary_exactly_55_passes_and_54_99_fails():
    assert check_admission({"marks": {"Physics": 55, "Maths": 55, "Chemistry": 55}}, BTECH_CSE).status == MEETS
    r = check_admission({"marks": {"Physics": 54.97, "Maths": 55, "Chemistry": 55}}, BTECH_CSE)
    assert r.status == NOT_MET


def test_missing_compulsory_subject_fails():
    r = check_admission({"marks": {"Physics": 95, "Chemistry": 95, "Biology": 95}}, BTECH_CSE)
    # not mentioned != not studied: ask, and say plainly that without Maths the rule is not met
    assert r.status == INSUFFICIENT and r.missing == ["Mathematics %"]
    assert any("not meet" in c.detail for c in r.checks)


def test_no_marks_is_insufficient():
    r = check_admission({}, BTECH_CSE)
    assert r.status == INSUFFICIENT and r.missing


def test_ib_route():
    assert check_admission({"board": "IB", "ib_credits": 24}, BTECH_CSE).status == MEETS
    assert check_admission({"board": "IB", "ib_credits": 23}, BTECH_CSE).status == NOT_MET


def test_interview_programme_needs_verification():
    crit = dict(BTECH_CSE, selection_components=["personal interview"])
    r = check_admission({"marks": {"Physics": 90, "Maths": 90, "Chemistry": 90}}, crit)
    assert r.status == NEEDS_VERIFICATION


def test_attendance_uses_latest_university_rule_75():
    r = check_attendance({"ABAI3063L Agentic AI": 74, "ABAI3009L Generative AI": 79}, "SoAI")
    assert r.computed["threshold_pct"] == 75
    assert r.status == NOT_MET
    assert r.checks[0].passed is False and r.checks[1].passed is True


def test_scset_old_70_rule_is_superseded():
    r = check_attendance({"CSET101": 72}, "SCSET")
    assert r.computed["threshold_pct"] == 75 and r.status == NOT_MET
    assert "70%" in r.computed["note"]


def test_classes_needed():
    out = classes_needed(attended=20, held=28, threshold_pct=75)
    assert out["needed"] == 4  # (20+4)/(28+4) = 75%


def test_pcm_average_asks_for_subject_marks_instead_of_guessing():
    # "82% in PCM" is an average: the rule needs Physics, Maths and the best other subject.
    r = check_admission({"marks": {"PCM": 82}}, BTECH_CSE)
    assert r.status == INSUFFICIENT
    assert any("Physics" in m for m in r.missing) and any("Mathematics" in m for m in r.missing)
    assert r.computed["provisional_min_best_of_3"] == 82  # Best-of-3 >= PCM average (Chemistry is eligible)


def test_then_exact_marks_give_a_verdict():
    r = check_admission({"marks": {"Physics": 80, "Mathematics": 84, "English": 90, "Chemistry": 82}}, BTECH_CSE)
    assert r.status == MEETS and r.computed["best_of_3"] == round((80 + 84 + 90) / 3, 2)


def test_only_two_subjects_asks_for_third():
    r = check_admission({"marks": {"Physics": 60, "Maths": 60}}, BTECH_CSE)
    assert r.status == INSUFFICIENT and r.missing


def test_overall_percentage_only_asks_for_subjects():
    r = check_admission({"marks": {"overall": 88}}, BTECH_CSE)
    assert r.status == INSUFFICIENT and r.missing


def test_impossible_marks_are_rejected():
    # Regression: Chemistry=450 produced "Best of 3 = 191.67% — meets criteria".
    r = check_admission({"marks": {"Physics": 60, "Chemistry": 450, "Maths": 65, "English": 56}}, BTECH_CSE)
    assert r.status == INSUFFICIENT
    assert any(c.name.startswith("Invalid mark") and c.passed is False for c in r.checks)
    assert check_admission({"marks": {"Physics": -5, "Maths": 70, "Chemistry": 70}}, BTECH_CSE).status == INSUFFICIENT


def test_safety_fast_path_detects_and_returns_contacts():
    from app.agents import safety
    assert safety.detect("I AM THE STUDENT I AM BEING RAGGED") == "ragging"
    assert safety.detect("seniors are harassing me in hostel") == "ragging"
    assert safety.detect("I want to die") == "self_harm"
    assert safety.detect("When is the end sem exam?") is None
    r = safety.respond("ragging", "SoAI")
    assert "1800-180-5522" in r["answer"] and "Rajeev Tiwari" in r["answer"] and r["status"] == "URGENT_SUPPORT"
    assert "14416" in safety.respond("self_harm", None)["answer"]


def test_smalltalk_fast_path():
    from app.agents import smalltalk
    for t in ["hello", "HELLO", "hi!", "what can you do", "thanks", "Good morning"]:
        assert smalltalk.detect(t), t
    for t in ["hello what is the fee for btech ai", "Am I eligible for BBA?", "help me with attendance rules please"]:
        assert smalltalk.detect(t) is None, t
    r = smalltalk.respond("greet", {"role": "student", "name": "Chirag Duhoon", "school": "SoAI", "programme": "B.Tech AI", "semester": 5})
    assert "Hi Chirag" in r["answer"] and "SoAI" in r["answer"]


def test_scholarship_continuation_soai_needs_8_5():
    from app.rules.engine import check_scholarship
    r = check_scholarship(8.53, "SoAI", True, backlogs=False, ufm=False, disciplinary=False)
    assert r.status == MEETS and r.computed["min_cgpa"] == 8.5
    assert check_scholarship(8.3, "SoAI", True, backlogs=False, ufm=False, disciplinary=False).status == NOT_MET
    assert check_scholarship(8.3, "SCSET", True, backlogs=False, ufm=False, disciplinary=False).status == MEETS


def test_ufm_or_disciplinary_case_disqualifies():
    from app.rules.engine import check_scholarship
    assert check_scholarship(9.5, "SCSET", True, backlogs=False, ufm=True, disciplinary=False).status == NOT_MET
    r = check_scholarship(8.3, "SCSET", False, backlogs=False, ufm=False, disciplinary=True, top_10_percent=True)
    assert r.status == NOT_MET and r.computed["scheme"] == "academic"


def test_academic_scholarship_needs_top_10_percent_confirmation():
    from app.rules.engine import check_scholarship
    r = check_scholarship(8.3, "SCSET", False, backlogs=False, ufm=False, disciplinary=False)
    assert r.status == NEEDS_VERIFICATION and r.computed["amount_pct_of_tuition"] == 10


def test_refund_windows_2026_27():
    from app.rules.engine import check_refund
    assert check_refund("2026-09-30").computed["tuition_refund"] == "full"
    assert "1,000" in check_refund("2026-10-15").computed["tuition_refund"]
    assert check_refund("2026-11-05").status == NEEDS_VERIFICATION
    assert check_refund(hostel_day=0).computed["hostel_refund_pct"] == 100
    assert check_refund(hostel_day=7).computed["hostel_refund_pct"] == 50
    assert check_refund(hostel_day=9).computed["hostel_refund_pct"] == 25
    assert check_refund(hostel_day=11).computed["hostel_refund_pct"] == 0


def test_human_written_percentages_do_not_crash():
    from app.rules.engine import parse_percentages
    assert parse_percentages({"Computer": "below 75", "Maths": "60%", "Env": "around 70", "x": "n/a"}) == \
        {"Computer": 74.99, "Maths": 60.0, "Env": 70.0}
    r = check_attendance(parse_percentages({"Computer": "below 75"}), "SCSET")
    assert r.status == NOT_MET


def test_ufm_known_without_asking_scheme():
    from app.rules.engine import check_scholarship
    r = check_scholarship(None, "SoAI", None, ufm=True)
    assert r.status == NOT_MET and not r.missing


def test_scholarship_amount_on_official_tuition():
    from app.rules.engine import scholarship_amounts
    r = scholarship_amounts("B.Tech CSE", {"year_1": 380000, "year_2": 390000, "year_3": 400000, "year_4": 400000}, 50)
    assert r.computed["total_tuition"] == 1570000 and r.computed["total_tuition_payable"] == 785000
    assert r.computed["per_year"][0]["payable"] == 190000


def test_merit_scholarship_annexure_a():
    from app.rules.engine import check_merit_scholarship
    assert check_merit_scholarship("B.Tech (Artificial Intelligence)", "jee", 90).computed["scholarship_pct"] == 50
    assert check_merit_scholarship("B.Tech (Artificial Intelligence)", "jee", 95).computed["scholarship_pct"] == 100
    assert check_merit_scholarship("B.Tech (Computer Science Engineering)", "jee", 99).computed["scholarship_pct"] == 50
    assert check_merit_scholarship("B.Tech (Mechanical Engineering)", "jee", 86).computed["scholarship_pct"] == 50
    assert check_merit_scholarship("BCA (Artificial Intelligence)", "xii", 92).computed["scholarship_pct"] == 50
    assert check_merit_scholarship("BCA", "xii", 92).computed["scholarship_pct"] == 30
    assert check_merit_scholarship("B.Tech (Computer Science Engineering)", "jee", 60).status == NOT_MET


def test_merit_scholarship_asks_programme_but_shows_options():
    from app.rules.engine import check_merit_scholarship
    r = check_merit_scholarship(None, "jee", 90)
    assert r.status == INSUFFICIENT and any("programme" in m for m in r.missing)
    opts = {o["programme"]: o["scholarship_pct"] for o in r.computed["by_programme"]}
    assert opts["B.Tech (Artificial Intelligence)"] == 50 and opts["B.Tech CSE / B.Tech + M.Tech CSE (Dual Degree)"] == 50


def test_entrance_exam_is_not_a_subject():
    r = check_admission({"marks": {"JEE": 82}}, BTECH_CSE)
    assert r.status == INSUFFICIENT and "Jee" not in str(r.checks)
    assert any(c.name == "Rule needs" and "55%" in c.detail for c in r.checks)


def test_typo_subject_is_recognised():
    assert R.canon("PJYSICS") == "Physics" and R.canon("mathamatics") == "Mathematics" and R.canon("IT") == "IT"


def test_unmentioned_compulsory_subject_asks_instead_of_rejecting():
    crit = {"min_percentage": 55, "score_basis": "best_of_3", "compulsory_subjects": ["Physics", "Mathematics"]}
    rr = R.check_admission({"marks": {"Maths": 44, "IT": 74, "English": 80}}, crit)
    assert rr.status == R.INSUFFICIENT and rr.missing == ["Physics %"]


def test_best_of_3_is_an_average_not_per_subject():
    crit = {"min_percentage": 55, "score_basis": "best_of_3", "compulsory_subjects": ["Physics", "Mathematics"]}
    rr = R.check_admission({"marks": {"PJYSICS": 65, "IT": 74, "Maths": 44}}, crit)
    assert rr.status == R.MEETS and rr.computed["best_of_3"] == 61.0


def test_superseded_rules_skips_dict_topics_and_links_newer_rule():
    facts = {
        "min_attendance_end_sem": [
            {"id": "new", "value_pct": 75, "scope": "university"},
            {"id": "old", "value_pct": 70, "scope": "SCSET", "superseded_by": "new"},
        ],
        "scholarship_policy": {"source": {"title": "x"}, "allocation": "merit"},  # dict topic: used to crash the endpoint
    }
    out = R.superseded_rules(facts)
    assert len(out) == 1
    assert out[0]["older"]["value_pct"] == 70 and out[0]["newer"]["value_pct"] == 75


def test_superseded_rules_on_real_seed_data():
    out = R.superseded_rules()
    assert any(c["topic"] == "min_attendance_end_sem" and c["newer"]["value_pct"] == 75 for c in out)
