"""
Main Entry Point Module

Combines deterministic recommendation components and AI explanation layer
into a complete end-to-end Course Recommendation Agent pipeline.
Saves final submission JSON outputs to the outputs/ directory.
"""

import json
import os
import sys
from typing import Dict, List, Any

try:
    from src.recommender import filter_courses_by_goal, generate_learning_path, validate_learning_path
    from src.ai_explainer import enrich_recommendation_with_explanations
except ImportError:
    from recommender import filter_courses_by_goal, generate_learning_path, validate_learning_path
    from ai_explainer import enrich_recommendation_with_explanations


def load_json_file(file_path: str) -> Any:
    """
    Loads and parses a JSON file from disk cleanly.
    """
    if not os.path.exists(file_path):
        raise FileNotFoundError(f"File not found: {file_path}")
    with open(file_path, "r", encoding="utf-8") as f:
        return json.load(f)


def validate_student_profile(student_profile: dict) -> dict:
    """
    Validates that a student profile contains all required input fields.
    """
    required_fields = ["student_id", "name", "learning_goal", "known_skills"]
    missing = [field for field in required_fields if field not in student_profile]

    if missing:
        return {
            "valid": False,
            "message": f"Invalid student profile! Missing required fields: {', '.join(missing)}"
        }

    if not isinstance(student_profile.get("known_skills"), list):
        return {
            "valid": False,
            "message": "Invalid student profile! 'known_skills' must be a list."
        }

    return {"valid": True, "message": "Student profile is valid."}


def save_output_json(result: dict, output_dir: str = "outputs") -> str:
    """
    Saves a student recommendation result object to a clean JSON file in output_dir.
    """
    os.makedirs(output_dir, exist_ok=True)
    student_id = result.get("student_id", "UNKNOWN")
    file_name = f"{student_id}_path.json"
    file_path = os.path.join(output_dir, file_name)

    # Clean internal success/message flags before writing submission JSON
    output_data = {
        "student_id": result.get("student_id"),
        "student_name": result.get("student_name"),
        "learning_goal": result.get("learning_goal"),
        "initial_known_skills": result.get("initial_known_skills"),
        "recommended_learning_path": result.get("recommended_learning_path", [])
    }

    with open(file_path, "w", encoding="utf-8") as f:
        json.dump(output_data, f, indent=2)

    return file_path


def run_deterministic_pipeline(student_profile: dict, course_catalogue: List[dict]) -> dict:
    """
    Runs the deterministic recommendation pipeline for a single student.

    Steps:
    1. Validate student profile input fields.
    2. Filter catalogue courses by student learning goal.
    3. Calculate prerequisite-safe learning path and priority ordering.
    4. Validate generated path against safety rules.
    5. Return clean deterministic output object.
    """
    prof_validation = validate_student_profile(student_profile)
    if not prof_validation["valid"]:
        return {
            "success": False,
            "student_id": student_profile.get("student_id", "UNKNOWN"),
            "student_name": student_profile.get("name", "Student"),
            "learning_goal": student_profile.get("learning_goal", "N/A"),
            "initial_known_skills": student_profile.get("known_skills", []),
            "recommended_learning_path": [],
            "message": prof_validation["message"]
        }

    path_result = generate_learning_path(student_profile, course_catalogue)
    if not path_result.get("success"):
        return path_result

    path_validation = validate_learning_path(path_result, course_catalogue)
    if not path_validation["valid"]:
        return {
            "success": False,
            "student_id": student_profile["student_id"],
            "student_name": student_profile["name"],
            "learning_goal": student_profile["learning_goal"],
            "initial_known_skills": student_profile["known_skills"],
            "recommended_learning_path": [],
            "message": f"Path validation failed: {'; '.join(path_validation['errors'])}"
        }

    return {
        "success": True,
        "student_id": path_result["student_id"],
        "student_name": path_result["student_name"],
        "learning_goal": path_result["learning_goal"],
        "initial_known_skills": path_result["initial_known_skills"],
        "recommended_learning_path": path_result["recommended_learning_path"],
        "message": path_result["message"]
    }


def run_full_pipeline(student_profile: dict, course_catalogue: List[dict], enable_ai: bool = True) -> dict:
    """
    Runs the complete recommendation pipeline (Deterministic Selection + AI Explanation Enrichment).
    """
    deterministic_result = run_deterministic_pipeline(student_profile, course_catalogue)
    if not deterministic_result.get("success") or not enable_ai:
        return deterministic_result

    return enrich_recommendation_with_explanations(deterministic_result, student_profile)


def run_pipeline_for_all_profiles(data_dir: str = "data", output_dir: str = "outputs", enable_ai: bool = True) -> List[dict]:
    """
    Loads data files, runs full pipeline for all 4 profiles, and saves output JSON files.
    """
    catalogue_file = os.path.join(data_dir, "courses.json")
    profiles_file = os.path.join(data_dir, "student_profiles.json")

    catalogue = load_json_file(catalogue_file)
    profiles = load_json_file(profiles_file)

    results = []
    print("\n=======================================================")
    print("        FULL COURSE RECOMMENDATION PIPELINE RUN        ")
    print("=======================================================\n")

    for profile in profiles:
        result = run_full_pipeline(profile, catalogue, enable_ai=enable_ai)
        results.append(result)

        if result["success"]:
            saved_file = save_output_json(result, output_dir=output_dir)
            print(f"• Student ID    : {result['student_id']} ({result['student_name']})")
            print(f"  Goal          : {result['learning_goal']}")
            print(f"  Status        : SUCCESS ({len(result['recommended_learning_path'])} Steps)")
            print(f"  Output Saved  : {saved_file}")
            print("  Learning Path :")
            for step in result["recommended_learning_path"]:
                print(f"    Step {step['step']}: {step['course_id']} - {step['course_name']} [{step['difficulty']}]")
        else:
            print(f"• Student ID    : {result.get('student_id')} - FAILED ({result.get('message')})")
        print("-" * 55)

    return results


def run_integration_tests():
    """
    Runs full pipeline integration tests.
    """
    print("\n=== Running Full Pipeline Integration Tests ===")

    catalogue = load_json_file(os.path.join("data", "courses.json"))
    profiles = load_json_file(os.path.join("data", "student_profiles.json"))

    for profile in profiles:
        det = run_deterministic_pipeline(profile, catalogue)
        full = run_full_pipeline(profile, catalogue, enable_ai=True)

        assert det["success"] == full["success"]
        assert len(det["recommended_learning_path"]) == len(full["recommended_learning_path"])

        for d_step, f_step in zip(det["recommended_learning_path"], full["recommended_learning_path"]):
            assert d_step["course_id"] == f_step["course_id"]
            assert d_step["course_name"] == f_step["course_name"]
            assert d_step["step"] == f_step["step"]
            assert "recommendation_reason" in f_step

    print("[PASS] Test 1: Full pipeline preserves exact deterministic course selection and order across all profiles.")
    print("=== All Integration Tests Passed Successfully! ===\n")


if __name__ == "__main__":
    run_integration_tests()
    run_pipeline_for_all_profiles()
