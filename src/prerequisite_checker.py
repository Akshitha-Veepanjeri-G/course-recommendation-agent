"""
Prerequisite Checker Module

Validates whether a student (given their known or accumulated skills)
meets the prerequisite requirements for any course in the catalogue.
Also identifies missing prerequisite skills and candidate courses that teach them.
"""

from typing import Dict, List, Set, Union


def check_prerequisites(course: dict, available_skills: Union[List[str], Set[str]]) -> dict:
    """
    Checks if all prerequisites for a given course are present in available_skills.

    Args:
        course (dict): Course object from the catalogue containing 'prerequisites'.
        available_skills (list or set): Skills known or accumulated by the student.

    Returns:
        dict: A structured summary containing:
            - satisfied (bool): True if all prerequisites are met, False otherwise.
            - missing_prerequisites (list): List of skill names that are missing.
            - satisfied_prerequisites (list): List of skill names that are satisfied.
            - status_message (str): Human-readable status string.
    """
    prereqs = course.get("prerequisites", [])
    skills_set = set(available_skills)

    satisfied_prereqs = [p for p in prereqs if p in skills_set]
    missing_prereqs = [p for p in prereqs if p not in skills_set]

    is_satisfied = len(missing_prereqs) == 0

    if not prereqs:
        status_message = "No prerequisites required."
    elif is_satisfied:
        status_message = f"All prerequisites satisfied: {', '.join(satisfied_prereqs)}"
    else:
        status_message = f"Missing prerequisites: {', '.join(missing_prereqs)}"

    return {
        "satisfied": is_satisfied,
        "missing_prerequisites": missing_prereqs,
        "satisfied_prerequisites": satisfied_prereqs,
        "status_message": status_message
    }


def find_prerequisite_courses(missing_skills: List[str], course_catalogue: List[dict]) -> List[dict]:
    """
    Finds courses in the catalogue that teach any of the missing prerequisite skills.

    Args:
        missing_skills (list): List of skill names that need to be acquired.
        course_catalogue (list): Full list of course dictionaries from catalogue.

    Returns:
        list: List of course dictionaries that teach at least one missing skill.
    """
    needed_courses = []
    missing_set = set(missing_skills)

    for course in course_catalogue:
        taught = set(course.get("skills_taught", []))
        if taught.intersection(missing_set):
            needed_courses.append(course)

    return needed_courses


def run_prerequisite_tests():
    """
    Runs validation test cases covering key prerequisite scenarios.
    """
    print("=== Running Prerequisite Checker Tests ===")

    # Dummy courses for testing
    course_no_prereqs = {
        "course_id": "CS101",
        "course_name": "Python Basics",
        "prerequisites": []
    }

    course_pandas = {
        "course_id": "CS104",
        "course_name": "Data Analysis with Pandas",
        "prerequisites": ["Python Basics"]
    }

    course_ml = {
        "course_id": "CS106",
        "course_name": "Machine Learning Fundamentals",
        "prerequisites": ["Python Basics", "Pandas", "Statistics"]
    }

    course_deep_learning = {
        "course_id": "CS107",
        "course_name": "Deep Learning",
        "prerequisites": ["Machine Learning"]
    }

    # Test Case 1: A course with no prerequisites
    res1 = check_prerequisites(course_no_prereqs, [])
    assert res1["satisfied"] is True
    print("[PASS] Test 1 (No Prereqs):", res1["status_message"])

    # Test Case 2: A course whose prerequisites are fully satisfied
    res2 = check_prerequisites(course_pandas, ["Python Basics"])
    assert res2["satisfied"] is True
    print("[PASS] Test 2 (Fully Satisfied):", res2["status_message"])

    # Test Case 3: A course with one missing prerequisite
    res3 = check_prerequisites(course_deep_learning, ["Python Basics"])
    assert res3["satisfied"] is False
    assert res3["missing_prerequisites"] == ["Machine Learning"]
    print("[PASS] Test 3 (One Missing Prereq):", res3["status_message"])

    # Test Case 4: A course with multiple missing prerequisites (no skills known)
    res4 = check_prerequisites(course_ml, [])
    assert res4["satisfied"] is False
    assert res4["missing_prerequisites"] == ["Python Basics", "Pandas", "Statistics"]
    print("[PASS] Test 4 (Multiple Missing Prereqs):", res4["status_message"])

    # Test Case 5: A student who already has some prerequisite skills
    res5 = check_prerequisites(course_ml, ["Python Basics"])
    assert res5["satisfied"] is False
    assert res5["satisfied_prerequisites"] == ["Python Basics"]
    assert res5["missing_prerequisites"] == ["Pandas", "Statistics"]
    print("[PASS] Test 5 (Partially Satisfied):", res5["status_message"])

    print("=== All 5 Prerequisite Checker Tests Passed Successfully! ===\n")


if __name__ == "__main__":
    run_prerequisite_tests()
