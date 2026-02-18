import json
from langchain_community.embeddings import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_community.vectorstores import FAISS
from langchain.chains import RetrievalQA
from langchain.prompts import PromptTemplate
from langchain.docstore.document import Document
from langchain_groq import ChatGroq
import warnings
from dotenv import load_dotenv
warnings.filterwarnings('ignore')
load_dotenv(override=True)

def load_documents(file_path: str):
    with open(file_path, "r", encoding="utf-8") as f:
        data = json.load(f)
    return [Document(page_content=item["page_content"]) for item in data]

docs = load_documents("knowledge_base.json")

splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50)
splits = splitter.split_documents(docs)

embeddings = HuggingFaceEmbeddings(
    model_name="sentence-transformers/all-MiniLM-L6-v2"
)

vectorstore = FAISS.from_documents(splits, embeddings)

retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

llm = ChatGroq(model="openai/gpt-oss-20b", temperature=0)

# Guardrail prompt
QA_PROMPT = PromptTemplate(
    input_variables=["context", "question"],
    template="""
You are a customer support assistant for an e-commerce platform.

Answer the customer’s question ONLY using the provided context.

If the context does not contain enough information to answer,
respond strictly in JSON as:
{{
  "flag": true,
  "answer": "This query requires human support."
}}

Otherwise, respond strictly in JSON as:
{{
  "flag": false,
  "answer": "<your helpful answer>"
}}

Context:
{context}

Question: {question}
"""
)

qa_chain = RetrievalQA.from_chain_type(
    llm=llm,
    retriever=retriever,
    chain_type="stuff",
    chain_type_kwargs={"prompt": QA_PROMPT},
    return_source_documents=True
)

# LangGraph Node
# ---------------------------------------

def qa_generator(query: str):
    """Run QA chain and return parsed answer or flag status."""
    result = qa_chain({"query": query})
    raw_answer = result["result"].strip()
    parsed = json.loads(raw_answer)
    return parsed   # just return parsed dict, let node handle state



        

# if __name__ == "__main__":
#     query="Do you offer installation services for large appliances like refrigerators or washing machines?"
#     response = qa_generator(query)   # qa_node expects a dict, not a Pydantic object
#     print(response)

