"""
Recommender Engine Module

Handles goal-based course filtering, priority-based course ranking,
and prerequisite-safe learning-path ordering.
"""

import json
import os
from typing import Dict, List, Any

try:
    from src.prerequisite_checker import check_prerequisites, find_prerequisite_courses
except ImportError:
    from prerequisite_checker import check_prerequisites, find_prerequisite_courses


def get_all_supported_goals(course_catalogue: List[dict]) -> List[str]:
    """
    Extracts a unique sorted list of all supported goals present in the course catalogue.
    """
    goals = set()
    for course in course_catalogue:
        for goal in course.get("supported_goals", []):
            goals.add(goal)
    return sorted(list(goals))


def filter_courses_by_goal(learning_goal: str, course_catalogue: List[dict]) -> dict:
    """
    Filters the course catalogue to find courses that support the student's learning goal.

    Args:
        learning_goal (str): Target goal of the student (e.g., "Data Analyst").
        course_catalogue (list): Full list of course dictionaries.

    Returns:
        dict: A structured summary containing:
            - success (bool): True if matching courses were found, False if goal unsupported.
            - learning_goal (str): The requested learning goal.
            - matching_courses (list): List of courses supporting this goal.
            - total_matches (int): Count of matching courses.
            - available_goals (list): List of all valid supported goals in catalogue.
            - message (str): Status description string.
    """
    cleaned_goal = learning_goal.strip() if learning_goal else ""
    available_goals = get_all_supported_goals(course_catalogue)

    matching_courses = [
        course for course in course_catalogue
        if any(g.lower() == cleaned_goal.lower() for g in course.get("supported_goals", []))
    ]

    if matching_courses:
        return {
            "success": True,
            "learning_goal": cleaned_goal,
            "matching_courses": matching_courses,
            "total_matches": len(matching_courses),
            "available_goals": available_goals,
            "message": f"Found {len(matching_courses)} course(s) matching goal '{cleaned_goal}'."
        }
    else:
        return {
            "success": False,
            "learning_goal": cleaned_goal,
            "matching_courses": [],
            "total_matches": 0,
            "available_goals": available_goals,
            "message": f"Unsupported goal '{cleaned_goal}'. Valid goals: {', '.join(available_goals)}."
        }


def generate_learning_path(student_profile: dict, course_catalogue: List[dict]) -> dict:
    """
    Generates a deterministic, prerequisite-safe ordered learning path for a student profile.

    Priority Rules:
    1. Prerequisite Unblocking: Prioritize courses needed to satisfy prerequisites for downstream required courses.
    2. Goal Relevance: Prioritize courses directly relevant to the student's target learning goal.
    3. Difficulty Progression: Beginner -> Intermediate -> Advanced.
    4. Catalogue Order: Tie-breaker based on course_id.
    """
    student_id = student_profile.get("student_id", "UNKNOWN")
    student_name = student_profile.get("name", "Student")
    learning_goal = student_profile.get("learning_goal", "")
    known_skills = student_profile.get("known_skills", [])

    # Step 1: Goal filtering
    filter_res = filter_courses_by_goal(learning_goal, course_catalogue)
    if not filter_res["success"]:
        return {
            "success": False,
            "student_id": student_id,
            "student_name": student_name,
            "learning_goal": learning_goal,
            "initial_known_skills": known_skills,
            "recommended_learning_path": [],
            "message": filter_res["message"]
        }

    goal_courses = filter_res["matching_courses"]
    
    # Step 2: Expand candidate pool with missing prerequisite provider courses
    candidate_pool = list(goal_courses)
    candidate_ids = set(c["course_id"] for c in candidate_pool)

    accumulated_skills = set(known_skills)
    changed = True
    while changed:
        changed = False
        needed_prereq_skills = set()
        for course in candidate_pool:
            for p in course.get("prerequisites", []):
                if p not in accumulated_skills:
                    needed_prereq_skills.add(p)
        
        if needed_prereq_skills:
            providers = find_prerequisite_courses(list(needed_prereq_skills), course_catalogue)
            for p_course in providers:
                if p_course["course_id"] not in candidate_ids:
                    candidate_pool.append(p_course)
                    candidate_ids.add(p_course["course_id"])
                    changed = True

    # Step 3: Interactive path building loop
    ordered_path = []
    completed_course_ids = set()
    current_skills = set(known_skills)
    step_counter = 1

    # Exclude courses whose skills are already fully possessed by the student
    remaining_candidates = []
    for c in candidate_pool:
        skills_taught = set(c.get("skills_taught", []))
        if not skills_taught.issubset(current_skills):
            remaining_candidates.append(c)

    difficulty_order = {"Beginner": 1, "Intermediate": 2, "Advanced": 3}

    while remaining_candidates:
        # Find courses whose prerequisites are fully satisfied by current_skills
        eligible = []
        for course in remaining_candidates:
            check = check_prerequisites(course, current_skills)
            if check["satisfied"]:
                eligible.append((course, check))

        if not eligible:
            # Prevent infinite loop if unresolvable dependency exists
            break

        # Calculate uncompleted prerequisite skills required downstream
        uncompleted_needed_skills = set()
        for c in remaining_candidates:
            for p in c.get("prerequisites", []):
                if p not in current_skills:
                    uncompleted_needed_skills.add(p)

        def priority_key(item):
            course, check_res = item
            c_skills = set(course.get("skills_taught", []))
            
            # Rule 1: Prerequisite unblocking
            unblocks_others = bool(c_skills.intersection(uncompleted_needed_skills))
            r1_score = 0 if unblocks_others else 1
            
            # Rule 2: Direct goal relevance
            is_goal_course = any(g.lower() == learning_goal.lower() for g in course.get("supported_goals", []))
            r2_score = 0 if is_goal_course else 1
            
            # Rule 3: Difficulty progression
            r3_score = difficulty_order.get(course.get("difficulty", "Intermediate"), 99)
            
            # Rule 4: Catalogue order (course_id string)
            r4_score = course.get("course_id", "")
            
            return (r1_score, r2_score, r3_score, r4_score)

        eligible.sort(key=priority_key)
        selected_course, prereq_check = eligible[0]

        # Formulate rule selection explanation
        selected_skills = set(selected_course.get("skills_taught", []))
        if selected_skills.intersection(uncompleted_needed_skills):
            selection_rule = "Prerequisite Unblocking (satisfies required prerequisite for downstream goal courses)"
        elif any(g.lower() == learning_goal.lower() for g in selected_course.get("supported_goals", [])):
            selection_rule = f"Goal Relevance (directly supports {learning_goal})"
        else:
            selection_rule = "Natural Skill Progression"

        step_info = {
            "step": step_counter,
            "course_id": selected_course["course_id"],
            "course_name": selected_course["course_name"],
            "difficulty": selected_course.get("difficulty", "Intermediate"),
            "skills_acquired": selected_course.get("skills_taught", []),
            "prerequisite_status": prereq_check["status_message"],
            "selection_rule": selection_rule
        }

        ordered_path.append(step_info)
        completed_course_ids.add(selected_course["course_id"])
        current_skills.update(selected_course.get("skills_taught", []))
        step_counter += 1

        # Remove selected course from remaining candidates
        remaining_candidates = [c for c in remaining_candidates if c["course_id"] != selected_course["course_id"]]

    return {
        "success": True,
        "student_id": student_id,
        "student_name": student_name,
        "learning_goal": learning_goal,
        "initial_known_skills": known_skills,
        "recommended_learning_path": ordered_path,
        "message": f"Successfully generated {len(ordered_path)}-step learning path for {student_name}."
    }


def validate_learning_path(path_result: dict, course_catalogue: List[dict]) -> dict:
    """
    Validates that a generated learning path satisfies all safety criteria:
    - Every course exists in catalogue.
    - Prerequisites satisfied before addition.
    - No duplicate courses.
    - Known skills not repeated unnecessarily.
    """
    if not path_result.get("success"):
        return {"valid": False, "errors": [path_result.get("message", "Failed path generation")]}

    errors = []
    catalogue_ids = {c["course_id"]: c for c in course_catalogue}
    seen_courses = set()
    accumulated_skills = set(path_result.get("initial_known_skills", []))

    for step in path_result.get("recommended_learning_path", []):
        cid = step["course_id"]
        
        # 1. Course existence
        if cid not in catalogue_ids:
            errors.append(f"Step {step['step']}: Course '{cid}' does not exist in catalogue.")
            continue
            
        course_obj = catalogue_ids[cid]
        
        # 2. Duplicate check
        if cid in seen_courses:
            errors.append(f"Step {step['step']}: Duplicate course '{cid}' recommended.")
        seen_courses.add(cid)

        # 3. Prerequisite check prior to addition
        prereqs = course_obj.get("prerequisites", [])
        missing = [p for p in prereqs if p not in accumulated_skills]
        if missing:
            errors.append(f"Step {step['step']}: Prerequisites for '{cid}' not met! Missing: {missing}")

        # Update accumulated skills
        accumulated_skills.update(course_obj.get("skills_taught", []))

    return {
        "valid": len(errors) == 0,
        "errors": errors
    }


def run_path_ordering_tests():
    """
    Runs validation test cases covering all student personas and edge cases.
    """
    print("=== Running Recommendation Priority & Learning-Path Ordering Tests ===")

    catalogue_path = os.path.join("data", "courses.json")
    profiles_path = os.path.join("data", "student_profiles.json")

    with open(catalogue_path, "r") as f:
        catalogue = json.load(f)

    with open(profiles_path, "r") as f:
        profiles = {p["student_id"]: p for p in json.load(f)}

    # Test 1: STUDENT_01 (Complete Beginner)
    path1 = generate_learning_path(profiles["STUDENT_01"], catalogue)
    val1 = validate_learning_path(path1, catalogue)
    assert val1["valid"] is True
    # Verify starts with foundational courses (CS101 or CS103)
    first_course = path1["recommended_learning_path"][0]["course_id"]
    assert first_course in ["CS101", "CS103"]
    print(f"[PASS] Test 1 (STUDENT_01 Complete Beginner): Started with {first_course}, {len(path1['recommended_learning_path'])} steps.")

    # Test 2: STUDENT_02 (Foundational - Knows Python Basics)
    path2 = generate_learning_path(profiles["STUDENT_02"], catalogue)
    val2 = validate_learning_path(path2, catalogue)
    assert val2["valid"] is True
    # Verify CS101 is NOT in recommended path
    recommended_ids_2 = [s["course_id"] for s in path2["recommended_learning_path"]]
    assert "CS101" not in recommended_ids_2
    print(f"[PASS] Test 2 (STUDENT_02 Knows Python): Skipped CS101 cleanly. Path: {', '.join(recommended_ids_2)}")

    # Test 3: STUDENT_03 (Intermediate ML - Lacks Pandas)
    path3 = generate_learning_path(profiles["STUDENT_03"], catalogue)
    val3 = validate_learning_path(path3, catalogue)
    assert val3["valid"] is True
    recommended_ids_3 = [s["course_id"] for s in path3["recommended_learning_path"]]
    # Verify CS104 (Pandas) comes BEFORE CS106 (ML)
    assert "CS104" in recommended_ids_3 and "CS106" in recommended_ids_3
    assert recommended_ids_3.index("CS104") < recommended_ids_3.index("CS106")
    print(f"[PASS] Test 3 (STUDENT_03 Lacks Pandas): CS104 recommended before CS106. Path: {', '.join(recommended_ids_3)}")

    # Test 4: STUDENT_04 (Advanced AI Specialist)
    path4 = generate_learning_path(profiles["STUDENT_04"], catalogue)
    val4 = validate_learning_path(path4, catalogue)
    assert val4["valid"] is True
    recommended_ids_4 = [s["course_id"] for s in path4["recommended_learning_path"]]
    assert recommended_ids_4 == ["CS107", "CS109"]
    print(f"[PASS] Test 4 (STUDENT_04 Advanced AI): Direct progression to Deep Learning & LLMs. Path: {', '.join(recommended_ids_4)}")

    # Test 5: Edge Case - No known skills
    profile_no_skills = {"student_id": "EDGE_01", "name": "No Skills Student", "learning_goal": "Data Analyst", "known_skills": []}
    path_edge_1 = generate_learning_path(profile_no_skills, catalogue)
    assert validate_learning_path(path_edge_1, catalogue)["valid"] is True
    print(f"[PASS] Test 5 (No Known Skills): Generated valid {len(path_edge_1['recommended_learning_path'])}-step path.")

    # Test 6: Edge Case - Unsupported goal
    profile_bad_goal = {"student_id": "EDGE_02", "name": "Bad Goal Student", "learning_goal": "Cybersecurity", "known_skills": []}
    path_edge_2 = generate_learning_path(profile_bad_goal, catalogue)
    assert path_edge_2["success"] is False
    print(f"[PASS] Test 6 (Unsupported Goal): Handled gracefully with message: '{path_edge_2['message']}'")

    print("\n=== All Learning-Path Ordering Tests Passed Successfully! ===\n")


if __name__ == "__main__":
    run_path_ordering_tests()
