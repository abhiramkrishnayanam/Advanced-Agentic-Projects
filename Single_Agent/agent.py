from dataclasses import dataclass, field
from typing import List
import streamlit as st
import fitz
import os
from langchain_groq import ChatGroq
from langchain_core.messages import HumanMessage
from dataclasses import replace
from langchain_core.prompts import ChatPromptTemplate
from langgraph.graph import StateGraph, START, END


import warnings
from dotenv import load_dotenv
warnings.filterwarnings('ignore')
load_dotenv(override=True)

@dataclass
class State:
    job_description: str = ""
    resume: str = ""
    summary: str = ""
    skills: List[str] = field(default_factory=list)
    match_score: float = 0.0
    suggestions: str = ""

######################################################
llm= ChatGroq(model="gemma2-9b-it", temperature= 0)

def Summarize_node(state:State):
    jd = state.job_description
    response =llm.invoke([
        HumanMessage(content=f"Summarize the following job description in 3 lines: \n{jd} ")
    ])

    summary =response.content
    return replace(state, summary=summary)
######################################################

def extract_skills_node(state:State):
    jd = state.job_description
    
    prompt_template = ChatPromptTemplate.from_messages([
    ("system", "You are an expert recruiter extracting key skills."),
    ("human", "Extract only the key technical and soft skills from the following job description and return them as a flat Python list (no explanations or formatting):\n\n{jd}")
])

    prompt = prompt_template.format_messages(jd=jd)

    response = llm.invoke(prompt)

    skills_text = response.content

    try:
        skills = eval(skills_text)
        if not isinstance(skills, list):
            raise ValueError()
    
    except:
        skills = [s.strip() for s in skills_text.split(",")]

    return replace(state, skills=skills)

######################################################
def match_resume_node(state: State):
    skills = state.skills
    resume = state.resume.lower()

    matched = [skill for skill in skills if skill.lower() in resume]
    score =round ((len(matched) / len(skills))*100, 2) if skills else 0.0

    return replace(state, match_score=score)

######################################################
def suggest_improvements_node(state:State):
    llm = ChatGroq(model="gemma2-9b-it", temperature= 0.3)
    jd = state.job_description
    resume = state.resume

    prompt =(
        f"My resume is : \n{resume}\n\n"
        f"Job Description: \n{jd}\n\n"
        f"Suggest specific improvements to better match the resume to this JD."
    )
    
    response = llm.invoke(prompt)
    return replace(state, suggestions=response.content)

######################################################
builder = StateGraph(State)

builder.add_node("Summarize", Summarize_node)
builder.add_node("extract_skills",extract_skills_node)
builder.add_node("match_resume", match_resume_node)
builder.add_node("Suggestions", suggest_improvements_node)

builder.add_edge(START, "Summarize")
builder.add_edge("Summarize", "extract_skills")
builder.add_edge("extract_skills", "match_resume")

#Conditional edge
def check_match(state):
    return "Suggestions" if state.match_score < 75 else "end"

builder.add_conditional_edges(
    "match_resume",
    check_match,
    {
        "Suggestions": "Suggestions",
        "end": END
    }
)


builder.add_edge("Suggestions", END)


app= builder.compile()
######################################################

st.title("🔍 Resume Matcher AI")

st.subheader("📝 Paste Job Description")
jd_text = st.text_area("Paste the Job Description here (you can copy-paste the text):", height=200)
if jd_text:
    st.success("Job description received!")

# Upload Resume (PDF)
st.subheader("📤 Upload Your Resume")
uploaded_file = st.file_uploader("Upload your resume (PDF)", type = 'pdf')
if uploaded_file:
    st.success("Job description received!")


def extract_text_from_pdf(file):
    doc = fitz.open(stream=file.read(), filetype="pdf")
    return "".join([page.get_text() for page in doc])



if uploaded_file is not None:
    resume_text = extract_text_from_pdf(uploaded_file)

    with st.spinner("🚀 Running Resume Matcher..."):
        result = app.invoke({
            "job_description": jd_text,
            "resume": resume_text
        })

    # Display Results
    st.success("✅ Analysis Complete!")

    st.subheader("📌 Job Description Summary:")
    st.write(result["summary"])

    st.subheader("💼 Extracted Key Skills:")
    st.write(result["skills"])

    st.subheader("📊 Resume Match Score:")
    st.metric(label="Match Score (%)", value=result["match_score"])

    if result["match_score"] < 75:
        st.subheader("🛠 Suggestions to Improve Your Resume:")
        st.write(result["suggestions"])
    else:
        st.balloons()
        st.success("🎉 Great match! Your resume aligns well with the job description.")