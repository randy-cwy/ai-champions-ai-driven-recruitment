import streamlit as st
from streamlit_navigation_bar import st_navbar
import pandas as pd
import json
import zipfile
import io
from about import about_page
from methodology import methodology_page
from download import download
from helper.utility import check_password
from helper.file_handler import process_job_description_file
from helper.skills_mapping import load_skills_future_framework, llm_assisted_skill_matching, remove_duplicate_skills
from helper.bulk_resume_processor import process_bulk_resumes
from helper.scoring import score_all_candidates
from helper.assessment_generator import generate_assessment_with_answers, create_candidate_docs, create_answer_key_doc
  
# region <--------- Streamlit Page Configuration --------->

st.set_page_config(
    layout="centered", 
    page_title="AI-Driven Skills Matching",
    page_icon="mydocs/robot.png",
    initial_sidebar_state="collapsed"
)

if "authenticated" not in st.session_state:
    st.header("AI Champions Project Type A 🚀")
    st.markdown("""
        #### Accelerating Recruitment through AI-Driven Skills Matching - *An LLM Application*
        Streamline hiring with our AI-driven recruitment tool! Match job responsibilities to candidate skills, rank top talent with precision, and generate customized assessments—all in one seamless platform. Discover how AI can transform your recruitment process!
        """)
    st.divider()

if not st.session_state.get("authenticated", False):  
    if check_password():
        st.session_state["authenticated"] = True 
        st.rerun() 
    else:
        st.stop() 

# endregion <--------- Streamlit Page Configuration --------->

pages = ["Home", "Sample Files", "About", "Methodology"]

styles = {
    "nav": {
        "background-color": "#004B87",
        "font-family": "'Inter', sans-serif",
    },
    "div": {
        "max-width": "32rem",
    },
    "span": {
        "border-radius": "0rem",
        "color": "#FFFFFF",
        "margin": "0 0.125rem",
        "padding": "10.4375rem 0.625rem",
        "font-family": "'Inter', sans-serif",
        "font-weight": "300",
    },
    "active": {
        "background-color": "#FEA20A",  # CCCS gold color for active item
        "color": "#004B87",  # Blue text on active
        "font-weight": "600",
        "box-shadow": "inset 0px 0px 5px rgba(0, 0, 0, 0.2)",
    },
    "hover": {
        "background-color": "#FEA20A",  # CCCS gold color for hover
        "color": "#004B87",  # Blue text on hover
        "transition": "background-color 0.3s ease, color 0.3s ease",  
    },
}

page = st_navbar(pages, styles=styles)

if page == "About":
    # Call the About Page Function
    about_page()
elif page == "Methodology":
    methodology_page()
elif page == "Sample Files":
    download()
elif page == "Home":
    # Main page content
    st.title("LLM-Powered Job Description Parsing and Candidate Scoring")
    with st.expander("IMPORTANT NOTICE"):
        st.write("""
            This web application is developed as a proof-of-concept prototype. The information provided here is NOT intended for actual usage and should not be relied upon for making any decisions, especially those related to financial, legal, or healthcare matters.

            Furthermore, please be aware that the LLM may generate inaccurate or incorrect information. You assume full responsibility for how you use any generated output.

            Always consult with qualified professionals for accurate and personalized advice.
        """)

    # Step 1: Upload necessary files
    st.subheader("Step 1: Upload Files")

    # Upload a job description file
    jd_file = st.file_uploader("Upload a Job Description (.docx, .pdf)", type=["docx", "pdf"])

    # Upload the SkillsFuture Framework
    framework_file = st.file_uploader("Upload the SkillsFuture Framework (.xlsx)", type=["xlsx"])

    # Bulk upload different resumes
    resume_files = st.file_uploader("Upload Resumes (.docx, .pdf)", type=["docx", "pdf"], accept_multiple_files=True)

    # Check if all files are uploaded
    if jd_file and framework_file and resume_files:
        st.success("Files uploaded successfully!")

        # Step 2: Prompt the user for the number of top candidates
        st.subheader("Step 2: Select Number of Top Candidates")
        top_n = st.number_input("Enter the number of top candidates to display", min_value=1, max_value=len(resume_files))

        # Step 3: Process and store results in a DataFrame or recompute if requested
        button_label = "Recompute Score" if "candidate_df" in st.session_state else "Process Candidate Resumes"

        if st.button(button_label):
            # Clear or reset any session state variables to avoid display of old data
            st.session_state.pop("candidate_df", None)
            st.session_state.pop("jd_matched_skills", None)
            st.session_state.pop("top_n_candidates", None)
            st.session_state.pop("assessment_generated", None)
            st.session_state.pop("candidate_results", None)  # Clear old candidate_results

            # Process Job Description and Skills Framework
            with st.spinner("🤖 Loading..."):
                jd_text, _ = process_job_description_file(jd_file)
                framework_df = load_skills_future_framework(framework_file)
                jd_matched_skills = llm_assisted_skill_matching(jd_text, framework_df)

                # Remove duplicates and save jd_matched_skills in session state
                jd_matched_skills = remove_duplicate_skills(json.loads(jd_matched_skills))
                st.session_state["jd_matched_skills"] = jd_matched_skills

                # Process resumes with progress bar and additional details
                status_text = st.empty()
                progress_bar = st.progress(0)
                total_files = len(resume_files)

                candidate_results = {}

                # Process resumes with progress bar
                for index, resume_file in enumerate(resume_files):
                    # Show the current progress with file details
                    current_file = resume_file.name
                    status_text.markdown(f"**Processing file {index + 1}/{total_files}: `{current_file}`**")
                    
                    # Process each resume
                    result = process_bulk_resumes([resume_file], framework_df)
                    candidate_results.update(result)
                    
                    # Update progress bar and display percentage
                    progress_percentage = (index + 1) / total_files
                    status_text.markdown(f"**Progress: {int(progress_percentage * 100)}% completed**")
                    progress_bar.progress(progress_percentage)

                # Clear the progress bar and status message once done
                progress_bar.empty()
                status_text.empty()

                # Store candidate results in session state
                st.session_state["candidate_results"] = candidate_results  # <-- Store results here

                # Score candidates and save results
                candidate_scores = score_all_candidates(candidate_results, jd_matched_skills)
                
                # Store the scores in a DataFrame and in session state
                candidate_df = pd.DataFrame(candidate_scores.items(), columns=["Candidate", "Score"])
                candidate_df = candidate_df.sort_values(by="Score", ascending=False).reset_index(drop=True)
                st.session_state["candidate_df"] = candidate_df

        # Step 4: Display Results with Expandable Details
        if "candidate_df" in st.session_state:
            st.subheader(f"Top {top_n} Candidates:")
            
            # Display each candidate's details in an expander
            top_candidates = st.session_state.candidate_df.head(top_n)
            candidate_results = st.session_state["candidate_results"]  # Load candidate skills data
            
            for _, row in top_candidates.iterrows():
                candidate_name = row["Candidate"]
                score = row["Score"]
                
                # Create an expander for each candidate
                with st.expander(f"{candidate_name} - {score:.2f}%"):
                    st.write(f"**Overall Score**: {score:.2f}%")
                    
                    # Fetch this candidate’s detailed info from candidate_results
                    candidate_info = candidate_results.get(candidate_name, {})
                    
                    # Display candidate qualifications if available
                    qualification = candidate_info.get("Qualification", "N/A")
                    st.write(f"**Qualification**: {qualification}")
                    
                    # Display matched skills and their proficiency levels
                    st.write("**Current Skillset:**")
                    skills = candidate_info.get("Skills", [])
                    if skills:
                        for skill in skills:
                            skill_name = skill.get("Skill", "Unknown Skill")
                            proficiency = skill.get("Proficiency Level", "Unknown Proficiency")
                            explanation = skill.get("Explanation", "No explanation provided")
                            
                            # Show each skill with its details in an organized format
                            st.markdown(f"""
                            - **{skill_name}**
                                - **Proficiency Level**: {proficiency}
                                - **Explanation**: {explanation}
                            """)
                    else:
                        st.write("No matched skills found for this candidate.")

            # Generate Assessment Button (reset the generated state if recomputing)
            generate_label = f"Generate {top_n} Assessment Documents"
            if st.button(generate_label, disabled=st.session_state.get("is_generating_assessment", False)):
                # Set the flag to indicate assessment generation is in progress
                st.session_state["is_generating_assessment"] = True
                st.session_state["assessment_generated"] = False

                # Retrieve candidate names from the top N candidates in the session state DataFrame
                top_candidates = st.session_state.candidate_df.head(top_n)
                candidate_names = top_candidates["Candidate"].tolist()
                
                # Generate assessment with progress bar
                with st.spinner("✍️ Generating assessment documents..."):
                    assessment_data = generate_assessment_with_answers(st.session_state["jd_matched_skills"])

                    # Progress bar and status text for generating assessment documents
                    assessment_status_text = st.empty()
                    assessment_progress_bar = st.progress(0)
                    total_candidates = len(candidate_names)

                    for index, candidate_name in enumerate(candidate_names):
                        # Update status text with the current progress
                        assessment_status_text.text(f"Generating assessment for {candidate_name} ({index + 1}/{total_candidates})")
                        
                        # Create assessment document for the current candidate
                        create_candidate_docs([candidate_name], assessment_data)
                        
                        # Update progress bar
                        assessment_progress_bar.progress((index + 1) / total_candidates)

                    # Clear the progress bar and status text once done
                    assessment_progress_bar.empty()
                    assessment_status_text.empty()

                    create_answer_key_doc(assessment_data)
                    
                    # Zip the generated files
                    zip_buffer = io.BytesIO()
                    with zipfile.ZipFile(zip_buffer, "w") as zip_file:
                        for candidate_name in candidate_names:
                            filename = f"{candidate_name.replace(' ', '_')}_Assessment.docx"
                            zip_file.write(filename)
                        zip_file.write("Assessment_Answer_Key.docx")
                    zip_buffer.seek(0)
                    
                    st.session_state["zip_buffer"] = zip_buffer
                    st.session_state["assessment_generated"] = True

                # Reset the loading flag
                st.session_state["is_generating_assessment"] = False

                # Display download button only if assessment is generated
                if st.session_state.get("assessment_generated", False):
                    st.download_button(
                        label="Download Assessment Files",
                        data=st.session_state["zip_buffer"],
                        file_name="Assessments.zip",
                        mime="application/zip"
                    )
