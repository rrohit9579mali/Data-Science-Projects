import streamlit as st
import pandas as pd
import joblib

from recommendation import show_recommendation


st.set_page_config(
    page_title="Coding Platform Analyzer",
    page_icon="💻",
    layout="wide"
)

model = joblib.load("platform_score_model.pkl")


st.sidebar.title("Coding Platform Analyzer")

option = st.sidebar.radio(
    "Select Option",
    ["Platform Score Prediction", "Recommendation System"]
)


if option == "Platform Score Prediction":

    st.title("📊 Platform Score Prediction")

    st.write("Predict the score of a coding platform.")

    col1, col2 = st.columns(2)

    with col1:

        platform = st.selectbox(
            "Platform",
            ["HackerRank", "Codeforces", "CodeChef", "LeetCode"]
        )

        active_users = st.number_input(
            "Active Users (Millions)",
            1.0, 30.0, 15.0
        )

        avg_rating = st.number_input(
            "Average Rating",
            3.5, 5.0, 4.3, step=0.1
        )

        problems_count = st.number_input(
            "Problems Count",
            500, 4000, 2250
        )

        problems_difficulty = st.selectbox(
            "Problems Difficulty",
            ["Easy", "Medium", "Hard", "Varied"]
        )

        job_integration = st.selectbox(
            "Job Integration",
            ["Yes", "Limited", "No"]
        )

        contest_frequency = st.selectbox(
            "Contest Frequency",
            ["Weekly", "Monthly", "Biweekly", "Occasionally"]
        )

    with col2:

        pricing_model = st.selectbox(
            "Pricing Model",
            ["Free", "Freemium", "Paid"]
        )

        founded_year = st.number_input(
            "Founded Year",
            2005, 2022, 2015
        )

        mobile_app = st.selectbox(
            "Mobile App Available",
            [True, False]
        )

        certifications = st.selectbox(
            "Certifications Offered",
            [True, False]
        )

        learning_paths = st.number_input(
            "Learning Paths",
            1, 10, 5
        )

        forum_activity = st.selectbox(
            "Forum Activity Level",
            ["High", "Medium", "Low"]
        )

    if st.button("Predict Platform Score"):

        data = pd.DataFrame({
            "Platform": [platform],
            "Active_Users_M": [active_users],
            "Avg_Rating": [avg_rating],
            "Problems_Count": [problems_count],
            "Problems_Difficulty": [problems_difficulty],
            "Job_Integration": [job_integration],
            "Contest_Frequency": [contest_frequency],
            "Pricing_Model": [pricing_model],
            "Founded_Year": [founded_year],
            "Mobile_App_Available": [mobile_app],
            "Certifications_Offered": [certifications],
            "Learning_Paths": [learning_paths],
            "Forum_Activity_Level": [forum_activity]
        })

        score = model.predict(data)[0]

        st.subheader("🏆 Platform Score")

        st.write(f"### {score:.2f} / 137")

        st.progress(
            min(score / 137, 1.0)
        )

        if score >= 120:
            st.success("🔥 Excellent")

        elif score >= 105:
            st.success("🟢 Good")

        elif score >= 90:
            st.warning("🟡 Average")

        elif score >= 70:
            st.warning("🟠 Below Average")

        else:
            st.error("🔴 Low")


else:

    show_recommendation()
