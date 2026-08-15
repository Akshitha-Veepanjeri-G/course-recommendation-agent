"""
Final Validation Test Suite Module

Runs comprehensive edge-case and end-to-end tests for the Course Recommendation Agent.
"""

import json
import os
import sys

try:
    from src.main import load_json_file, run_deterministic_pipeline, run_full_pipeline, validate_student_profile
    from src.recommender import filter_courses_by_goal, generate_learning_path, validate_learning_path
    from src.ai_explainer import generate_fallback_explanation, enrich_recommendation_with_explanations
except ImportError:
    from main import load_json_file, run_deterministic_pipeline, run_full_pipeline, validate_student_profile
    from recommender import filter_courses_by_goal, generate_learning_path, validate_learning_path
    from ai_explainer import generate_fallback_explanation, enrich_recommendation_with_explanations


def run_all_final_tests():
    print("=======================================================")
    print("     COURSE RECOMMENDATION AGENT - FINAL TEST SUITE    ")
    print("=======================================================\n")

    catalogue = load_json_file(os.path.join("data", "courses.json"))
    profiles = load_json_file(os.path.join("data", "student_profiles.json"))

    test_results = []

    # TEST 1: Four Required Sample Profiles
    try:
        for profile in profiles:
            res = run_full_pipeline(profile, catalogue, enable_ai=True)
            assert res["success"] is True, f"Failed for {profile['student_id']}"
            assert len(res["recommended_learning_path"]) > 0
            for step in res["recommended_learning_path"]:
                assert "recommendation_reason" in step and len(step["recommendation_reason"]) > 0
        test_results.append(("Test 1: Four Required Sample Profiles", "PASSED", "All 4 profiles generated valid enriched learning paths."))
    except Exception as e:
        test_results.append(("Test 1: Four Required Sample Profiles", "FAILED", str(e)))

    # TEST 2: No Known Skills
    try:
        no_skills_prof = {
            "student_id": "TEST_02",
            "name": "No Skills Student",
            "background": "No prior experience",
            "learning_goal": "Data Analyst",
            "known_skills": []
        }
        res2 = run_full_pipeline(no_skills_prof, catalogue, enable_ai=True)
        assert res2["success"] is True
        first_course = res2["recommended_learning_path"][0]["course_id"]
        assert first_course in ["CS101", "CS103"], f"Expected foundational start, got {first_course}"
        test_results.append(("Test 2: No Known Skills", "PASSED", f"Handled gracefully, started with foundational course {first_course}."))
    except Exception as e:
        test_results.append(("Test 2: No Known Skills", "FAILED", str(e)))

    # TEST 3: Unknown Skills
    try:
        unknown_skills_prof = {
            "student_id": "TEST_03",
            "name": "Unknown Skills Student",
            "background": "Graphic Designer",
            "learning_goal": "Data Analyst",
            "known_skills": ["Graphic Design", "French", "Python Basics"]
        }
        res3 = run_full_pipeline(unknown_skills_prof, catalogue, enable_ai=True)
        assert res3["success"] is True
        rec_ids = [s["course_id"] for s in res3["recommended_learning_path"]]
        assert "CS101" not in rec_ids
        test_results.append(("Test 3: Unknown Skills", "PASSED", "Ignored irrelevant skills ('Graphic Design', 'French') cleanly and recognized 'Python Basics'."))
    except Exception as e:
        test_results.append(("Test 3: Unknown Skills", "FAILED", str(e)))

    # TEST 4: Unsupported Goal
    try:
        unsupported_goal_prof = {
            "student_id": "TEST_04",
            "name": "Unsupported Goal Student",
            "background": "IT Admin",
            "learning_goal": "Cybersecurity Specialist",
            "known_skills": []
        }
        res4 = run_full_pipeline(unsupported_goal_prof, catalogue, enable_ai=True)
        assert res4["success"] is False
        assert "Unsupported goal" in res4["message"]
        test_results.append(("Test 4: Unsupported Goal", "PASSED", "Returned clear failure message with valid available goals without crashing."))
    except Exception as e:
        test_results.append(("Test 4: Unsupported Goal", "FAILED", str(e)))

    # TEST 5: Missing Student Information
    try:
        missing_info_prof = {
            "student_id": "TEST_05",
            "name": "Incomplete Profile"
        }
        res5 = run_full_pipeline(missing_info_prof, catalogue, enable_ai=True)
        assert res5["success"] is False
        assert "Missing required fields" in res5["message"]
        test_results.append(("Test 5: Missing Student Info", "PASSED", "Input validation caught missing profile fields cleanly."))
    except Exception as e:
        test_results.append(("Test 5: Missing Student Info", "FAILED", str(e)))

    # TEST 6: Prerequisite Safety
    try:
        for profile in profiles:
            res6 = run_deterministic_pipeline(profile, catalogue)
            val6 = validate_learning_path(res6, catalogue)
            assert val6["valid"] is True, f"Validation errors: {val6['errors']}"
        test_results.append(("Test 6: Prerequisite Safety", "PASSED", "All generated paths passed 100% prerequisite and duplicate safety checks."))
    except Exception as e:
        test_results.append(("Test 6: Prerequisite Safety", "FAILED", str(e)))

    # TEST 7: AI Failure / Fallback
    try:
        os.environ["GEMINI_API_KEY"] = ""
        os.environ["GOOGLE_API_KEY"] = ""
        res7 = run_full_pipeline(profiles[0], catalogue, enable_ai=True)
        assert res7["success"] is True
        assert len(res7["recommended_learning_path"]) > 0
        for step in res7["recommended_learning_path"]:
            assert "recommendation_reason" in step and len(step["recommendation_reason"]) > 0
        test_results.append(("Test 7: AI Failure / Fallback", "PASSED", "Fallback explanations generated cleanly when API key is unconfigured."))
    except Exception as e:
        test_results.append(("Test 7: AI Failure / Fallback", "FAILED", str(e)))

    # TEST 8: AI Path Preservation
    try:
        for profile in profiles:
            det = run_deterministic_pipeline(profile, catalogue)
            full = run_full_pipeline(profile, catalogue, enable_ai=True)
            assert det["recommended_learning_path"] == [
                {k: v for k, v in step.items() if k != "recommendation_reason"}
                for step in full["recommended_learning_path"]
            ]
        test_results.append(("Test 8: AI Path Preservation", "PASSED", "Verified AI enrichment does not alter course IDs, step count, order, or prereqs."))
    except Exception as e:
        test_results.append(("Test 8: AI Path Preservation", "FAILED", str(e)))

    print("| Test | Result | Notes |")
    print("|------|--------|-------|")
    for name, status, notes in test_results:
        print(f"| **{name}** | `{status}` | {notes} |")
    print()

    passed = sum(1 for _, s, _ in test_results if s == "PASSED")
    failed = sum(1 for _, s, _ in test_results if s == "FAILED")
    print(f"Total Tests: {len(test_results)} | Passed: {passed} | Failed: {failed}\n")

    return test_results


if __name__ == "__main__":
    run_all_final_tests()
