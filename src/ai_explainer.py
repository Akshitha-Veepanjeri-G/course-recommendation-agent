"""
AI Explainer Module

Generates natural, personalized rationale text for course recommendations.
Uses Google GenAI SDK (Gemini API) with refined deterministic fallback templates.
"""

import json
import os
from typing import Dict, List, Any
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv()


def generate_fallback_explanation(student_profile: dict, step_info: dict) -> str:
    """
    Generates a natural, personalized 1-2 sentence explanation connecting the student's
    background/known skills to the course step and their overall learning goal.
    """
    background = student_profile.get("background", "")
    goal = student_profile.get("learning_goal", "")
    known_skills = student_profile.get("known_skills", [])
    course_id = step_info.get("course_id", "")
    skills_taught = step_info.get("skills_acquired", [])

    # Personas / background contextual matching
    if "Excel" in known_skills or "Marketing" in background:
        if course_id == "CS103":
            return "Building on your Excel spreadsheet experience as a Marketing Analyst, learning SQL allows you to query databases directly rather than relying on manual exports."
        elif course_id == "CS104":
            return "With your Python foundation in place, this course upgrades your analytical workflow from spreadsheets to scalable data cleaning with Pandas."
        elif course_id == "CS110":
            return "Combining your new SQL and Pandas skills with your marketing background, this step enables you to build interactive dashboards to communicate business insights."
        elif course_id == "CS111":
            return "This course rounds out your Data Analyst toolkit by teaching you how to automatically scrape and ingest web data into Python for your analysis."

    if "Software" in background or "Junior Software Engineer" in background:
        if course_id == "CS104":
            return "Leveraging your strong programming and math background, mastering Pandas gives you the essential data manipulation tools needed before tackling machine learning algorithms."
        elif course_id == "CS106":
            return "With Pandas, Linear Algebra, and Statistics in your toolkit, this course is your direct gateway into core supervised and unsupervised machine learning models."
        elif course_id == "CS107":
            return "Building on your ML foundation, learning PyTorch and neural network architectures prepares you for complex deep learning applications."
        elif course_id == "CS108":
            return "Combining your software engineering background with your ML knowledge, MLOps completes your path by teaching you how to deploy models into production APIs."

    if "Data Scientist" in background or "Scikit-Learn" in known_skills:
        if course_id == "CS107":
            return "Given your solid foundation in classical machine learning, advancing to deep neural networks is the ideal next step for high-dimensional data modeling."
        elif course_id == "CS109":
            return "With deep learning mastered, this final step equips you with transformer architectures and LLM prompt engineering to achieve your goal as an AI Research Specialist."

    if not known_skills or "teacher" in background.lower():
        if course_id == "CS101":
            return "Starting from scratch, Python Basics introduces fundamental programming concepts in a clear, beginner-friendly way to kickstart your transition into data analysis."
        elif course_id == "CS103":
            return "Alongside Python, SQL is an essential entry-level skill that lets you query and manage relational database tables."
        elif course_id == "CS104":
            return "Now that you understand basic Python, this course teaches you Pandas so you can inspect, clean, and analyze real-world datasets."
        elif course_id == "CS110":
            return "This course teaches you to turn clean data into visual reports and executive dashboards, fulfilling a core requirement for a Data Analyst."
        elif course_id == "CS111":
            return "Web scraping equips you with the practical ability to gather raw datasets directly from web pages and public APIs."

    skills_str = ", ".join(skills_taught)
    return f"This step builds on your current preparation by teaching {skills_str}, bridging your existing skills toward your goal of becoming a {goal}."


def build_explanation_prompt(student_profile: dict, learning_path: List[dict]) -> str:
    """
    Constructs a structured prompt for the LLM detailing the student and the selected course path.
    """
    background = student_profile.get("background", "No background details provided.")
    goal = student_profile.get("learning_goal", "Target Goal")
    known_skills = ", ".join(student_profile.get("known_skills", [])) or "None (Absolute Beginner)"

    path_summary = []
    for step in learning_path:
        path_summary.append(
            f"Step {step['step']}: {step['course_id']} - {step['course_name']} ({step['difficulty']})\n"
            f"  - Skills Taught: {', '.join(step['skills_acquired'])}"
        )

    courses_text = "\n\n".join(path_summary)

    prompt = f"""
System Role: You are an expert personalized learning-path advisor.
The Python recommendation engine has already selected the exact courses and order. Do NOT add, remove, or reorder courses.

STUDENT PROFILE:
- Background: {background}
- Target Learning Goal: {goal}
- Known Skills: {known_skills}

COURSES TO EXPLAIN:
{courses_text}

INSTRUCTIONS:
Return a JSON array of strings containing EXACTLY {len(learning_path)} items.
Item i corresponds to the explanation for Step i+1.
Each explanation MUST:
1. Be 1-2 natural, encouraging, personalized sentences.
2. Connect the student's background or existing skills to why this course is the logical next step for their goal.
3. DO NOT repeat phrases like "All prerequisites satisfied" or "Prerequisite status".
4. DO NOT simply restate course titles or list skills verbatim.

Return valid JSON format:
[
  "Natural explanation for step 1...",
  "Natural explanation for step 2..."
]
"""
    return prompt


def generate_ai_explanations(student_profile: dict, deterministic_path: List[dict]) -> tuple[List[str], str]:
    """
    Generates personalized explanations for each course step in the deterministic path.

    Attempts to call Gemini API via google-genai SDK if GEMINI_API_KEY is available.
    Falls back gracefully to template-based explanations if API is missing or fails.
    Returns a tuple of (explanations_list, explanation_source_string).
    """
    if not deterministic_path:
        return [], "Fallback"

    api_key = os.getenv("GEMINI_API_KEY") or os.getenv("GOOGLE_API_KEY")

    if not api_key or api_key == "your_gemini_api_key_here":
        return [
            generate_fallback_explanation(student_profile, step)
            for step in deterministic_path
        ], "Fallback"

    try:
        from google import genai
        client = genai.Client(api_key=api_key)
        prompt = build_explanation_prompt(student_profile, deterministic_path)

        response = client.models.generate_content(
            model="gemini-3.5-flash",
            contents=prompt,
        )

        response_text = response.text.strip()
        if response_text.startswith("```json"):
            response_text = response_text[7:]
        if response_text.endswith("```"):
            response_text = response_text[:-3]
        response_text = response_text.strip()

        explanations = json.loads(response_text)

        if isinstance(explanations, list) and len(explanations) == len(deterministic_path):
            return [str(e) for e in explanations], "Gemini AI"
        else:
            raise ValueError("AI response list size does not match selected course count.")

    except Exception as e:
        print(f"[AI Explainer Info] LLM API call fallback engaged ({e}). Using natural fallbacks.")
        return [
            generate_fallback_explanation(student_profile, step)
            for step in deterministic_path
        ], "Fallback"


def enrich_recommendation_with_explanations(recommendation_result: dict, student_profile: dict) -> dict:
    """
    Enriches the deterministic recommendation result by attaching a 'recommendation_reason'
    to every course step without altering course selection, order, or prerequisites.
    Also tags the result with explanation_source ('Gemini AI' or 'Fallback').
    """
    if not recommendation_result.get("success"):
        return recommendation_result

    path = recommendation_result.get("recommended_learning_path", [])
    explanations, source = generate_ai_explanations(student_profile, path)

    enriched_path = []
    for idx, step in enumerate(path):
        reason = explanations[idx] if idx < len(explanations) else generate_fallback_explanation(student_profile, step)
        step_copy = dict(step)
        step_copy["recommendation_reason"] = reason
        enriched_path.append(step_copy)

    enriched_result = dict(recommendation_result)
    enriched_result["recommended_learning_path"] = enriched_path
    enriched_result["explanation_source"] = source
    return enriched_result


def run_ai_explainer_tests():
    """
    Runs unit and fallback tests for the AI Explainer component.
    """
    print("\n=== Running AI Explainer Component Tests ===")

    sample_student = {
        "student_id": "STUDENT_02",
        "name": "Sarah Chen",
        "background": "Marketing Analyst with basic Python",
        "learning_goal": "Data Analyst",
        "known_skills": ["Excel", "Python Basics"]
    }

    sample_deterministic_path = [
        {
            "step": 1,
            "course_id": "CS103",
            "course_name": "SQL & Database Fundamentals",
            "difficulty": "Beginner",
            "skills_acquired": ["SQL"],
            "prerequisite_status": "No prerequisites required.",
            "selection_rule": "Prerequisite Unblocking"
        },
        {
            "step": 2,
            "course_id": "CS104",
            "course_name": "Data Analysis with Pandas & NumPy",
            "difficulty": "Intermediate",
            "skills_acquired": ["Pandas", "Data Analysis"],
            "prerequisite_status": "All prerequisites satisfied: Python Basics",
            "selection_rule": "Prerequisite Unblocking"
        }
    ]

    deterministic_result = {
        "success": True,
        "student_id": "STUDENT_02",
        "student_name": "Sarah Chen",
        "learning_goal": "Data Analyst",
        "initial_known_skills": ["Excel", "Python Basics"],
        "recommended_learning_path": sample_deterministic_path
    }

    fallback_reasons = [generate_fallback_explanation(sample_student, s) for s in sample_deterministic_path]
    assert len(fallback_reasons) == 2
    assert "prerequisites satisfied" not in fallback_reasons[0].lower()
    print("[PASS] Test 1: Natural fallback explanations generated correctly without repeating prerequisite_status.")

    enriched = enrich_recommendation_with_explanations(deterministic_result, sample_student)
    assert enriched["success"] is True
    assert len(enriched["recommended_learning_path"]) == len(sample_deterministic_path)

    for original, enriched_step in zip(sample_deterministic_path, enriched["recommended_learning_path"]):
        assert original["course_id"] == enriched_step["course_id"]
        assert original["course_name"] == enriched_step["course_name"]
        assert original["step"] == enriched_step["step"]
        assert "recommendation_reason" in enriched_step

    print("[PASS] Test 2: Enriched recommendation preserves exact course path, IDs, and order.")
    print("=== All AI Explainer Tests Passed Successfully! ===\n")


if __name__ == "__main__":
    run_ai_explainer_tests()
