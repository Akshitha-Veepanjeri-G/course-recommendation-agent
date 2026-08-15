"""
Streamlit Web Interface for Course Recommendation Agent

Imports and reuses existing deterministic recommendation logic and AI explainer modules.
"""

import json
import os
import streamlit as st

from src.main import load_json_file, run_full_pipeline
from src.recommender import get_all_supported_goals


def get_all_catalogue_skills(course_catalogue: list) -> list:
    """
    Extracts all unique skills taught across courses in the catalogue.
    """
    skills = set(["Excel"])
    for course in course_catalogue:
        skills.update(course.get("skills_taught", []))
    return sorted(list(skills))


def main():
    st.set_page_config(
        page_title="Course Recommendation Agent",
        page_icon="🎓",
        layout="centered"
    )

    # 1. Title
    st.title("🎓 Course Recommendation Agent")

    # 2. Description
    st.markdown(
        "This agent generates a personalized, prerequisite-safe learning path based on your background, "
        "known skills, and career learning goals."
    )
    st.divider()

    catalogue_path = os.path.join("data", "courses.json")
    if not os.path.exists(catalogue_path):
        st.error("Course catalogue data file (`data/courses.json`) not found.")
        return

    catalogue = load_json_file(catalogue_path)
    supported_goals = get_all_supported_goals(catalogue)
    available_skills = get_all_catalogue_skills(catalogue)

    profiles_path = os.path.join("data", "student_profiles.json")
    sample_profiles = []
    if os.path.exists(profiles_path):
        sample_profiles = load_json_file(profiles_path)

    st.subheader("1. Enter Student Profile")

    profile_options = ["Custom Profile"] + [f"{p['student_id']}: {p['name']} ({p['learning_goal']})" for p in sample_profiles]
    selected_preset = st.selectbox("Load Sample Profile (Optional):", profile_options)

    default_name = ""
    default_bg = ""
    default_goal_idx = 0
    default_skills = []

    if selected_preset != "Custom Profile":
        preset_id = selected_preset.split(":")[0]
        preset_data = next((p for p in sample_profiles if p["student_id"] == preset_id), None)
        if preset_data:
            default_name = preset_data.get("name", "")
            default_bg = preset_data.get("background", "")
            g_name = preset_data.get("learning_goal", "")
            if g_name in supported_goals:
                default_goal_idx = supported_goals.index(g_name)
            default_skills = [s for s in preset_data.get("known_skills", []) if s in available_skills]

    # 3. Student Inputs
    student_name = st.text_input("Student Name:", value=default_name, placeholder="e.g. Alex Rivera")
    background = st.text_area("Background & Experience:", value=default_bg, placeholder="e.g. High school teacher with no prior programming experience.")

    col1, col2 = st.columns(2)
    with col1:
        learning_goal = st.selectbox("Target Learning Goal:", supported_goals, index=default_goal_idx)
    with col2:
        known_skills = st.multiselect("Known Skills:", available_skills, default=default_skills)

    st.divider()

    # 4. Generate Button
    if st.button("Generate Learning Path", type="primary", use_container_width=True):
        if not student_name.strip():
            st.error("Please enter a Student Name.")
            return

        if not background.strip():
            st.error("Please provide a brief background description.")
            return

        # 5. Create student profile dict
        student_profile = {
            "student_id": "CUSTOM_USER",
            "name": student_name.strip(),
            "background": background.strip(),
            "learning_goal": learning_goal,
            "known_skills": known_skills
        }

        with st.spinner("Generating personalized learning path..."):
            result = run_full_pipeline(student_profile, catalogue, enable_ai=True)

        if not result.get("success"):
            st.error(f"Failed to generate path: {result.get('message', 'Unknown error')}")
            return

        path = result.get("recommended_learning_path", [])
        if not path:
            st.warning("No recommended courses found for the selected goal.")
            return

        # 8. Success message
        st.success(f"Successfully generated a {len(path)}-step personalized learning path for {student_name}!")

        # 6. Display Summary Information
        source_label = result.get("explanation_source", "Fallback")
        source_badge = "🟢 Gemini AI" if source_label == "Gemini AI" else "🟡 Fallback"

        st.subheader("2. Recommendation Overview")
        st.markdown(f"**Student**: {student_name}  \n"
                    f"**Target Goal**: `{learning_goal}`  \n"
                    f"**Starting Skills**: {', '.join(known_skills) if known_skills else '*None (Absolute Beginner)*'}  \n"
                    f"**Recommended Steps**: {len(path)} courses  \n"
                    f"**Explanation Source**: {source_badge}")
        st.divider()

        # 7. Display Learning Path Cards
        st.subheader("3. Ordered Learning Path")

        for step in path:
            step_num = step["step"]
            c_name = step["course_name"]
            c_id = step["course_id"]
            diff = step["difficulty"]
            acquired = ", ".join(step["skills_acquired"])
            prereq = step["prerequisite_status"]
            reason = step["recommendation_reason"]

            with st.container():
                st.markdown(f"### Step {step_num}: {c_id} - {c_name}")
                badge_color = "green" if diff == "Beginner" else "orange" if diff == "Intermediate" else "red"
                st.markdown(f"**Difficulty**: :{badge_color}[{diff}]  \n"
                            f"**Skills Acquired**: `{acquired}`  \n"
                            f"**Prerequisite Status**: {prereq}")
                st.info(f"**Why this course?**  \n{reason}")
                st.markdown("---")

    # 11. Footer
    st.caption("Built for the AI Agent Challenge")


if __name__ == "__main__":
    main()
