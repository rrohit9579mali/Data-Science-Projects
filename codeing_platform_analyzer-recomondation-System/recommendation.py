import streamlit as st
import pandas as pd


platform_profiles = pd.DataFrame({

    "Platform": [
        "CodeChef",
        "Codeforces",
        "HackerRank",
        "LeetCode"
    ],

    "Problems_Difficulty": [
        "Easy",
        "Hard",
        "Medium",
        "Easy"
    ],

    "Job_Integration": [
        "No",
        "Yes",
        "No",
        "Limited"
    ],

    "Contest_Frequency": [
        "Occasionally",
        "Biweekly",
        "Occasionally",
        "Occasionally"
    ],

    "Pricing_Model": [
        "Paid",
        "Paid",
        "Paid",
        "Paid"
    ],

    "Certifications_Offered": [
        True,
        False,
        False,
        True
    ],

    "Forum_Activity_Level": [
        "Low",
        "High",
        "Low",
        "Medium"
    ]
})


platform_profiles.set_index("Platform", inplace=True)


def calculate_match_score(user, platform):

    weights = {
        "Job_Integration": 25,
        "Contest_Frequency": 20,
        "Problems_Difficulty": 15,
        "Pricing_Model": 15,
        "Forum_Activity_Level": 15,
        "Certifications_Offered": 10
    }

    score = 0

    for feature in weights:

        if user[feature] == platform[feature]:
            score += weights[feature]

    return score


def recommend_platforms(user):

    recommendations = []

    for name, platform in platform_profiles.iterrows():

        score = calculate_match_score(
            user,
            platform
        )

        recommendations.append({
            "Platform": name,
            "Match Score": score
        })

    recommendations.sort(
        key=lambda x: x["Match Score"],
        reverse=True
    )

    return recommendations


def show_recommendation():

    st.title("🤖 Coding Platform Recommendation")

    st.write(
        "Select your preferences to find a suitable coding platform."
    )

    col1, col2 = st.columns(2)

    with col1:

        job = st.selectbox(
            "Job Integration",
            ["Yes", "Limited", "No"]
        )

        contest = st.selectbox(
            "Contest Frequency",
            ["Weekly", "Monthly", "Biweekly", "Occasionally"]
        )

        difficulty = st.selectbox(
            "Problem Difficulty",
            ["Easy", "Medium", "Hard", "Varied"]
        )

    with col2:

        pricing = st.selectbox(
            "Pricing Model",
            ["Free", "Freemium", "Paid"]
        )

        forum = st.selectbox(
            "Forum Activity",
            ["High", "Medium", "Low"]
        )

        certification = st.selectbox(
            "Certifications Offered",
            [True, False]
        )

    if st.button("Recommend Platform"):

        user_preferences = {
            "Job_Integration": job,
            "Contest_Frequency": contest,
            "Problems_Difficulty": difficulty,
            "Pricing_Model": pricing,
            "Forum_Activity_Level": forum,
            "Certifications_Offered": certification
        }

        results = recommend_platforms(
            user_preferences
        )

        best = results[0]

        st.success(
            f"🏆 Recommended Platform: {best['Platform']}"
        )

        st.metric(
            "Match Score",
            f"{best['Match Score']}%"
        )

        st.subheader("Platform Ranking")

        result_df = pd.DataFrame(results)

        result_df.index = range(
            1,
            len(result_df) + 1
        )

        st.dataframe(
            result_df,
            use_container_width=True
        )