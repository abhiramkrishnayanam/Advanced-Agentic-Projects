import json
import re 
import warnings
from dotenv import load_dotenv
warnings.filterwarnings('ignore')
load_dotenv(override=True)
from langchain_groq import ChatGroq
from langchain_community.vectorstores import FAISS
from langchain_huggingface import HuggingFaceEmbeddings
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import RetrievalQA
from langchain.schema import Document
from langchain.prompts import PromptTemplate

llm= ChatGroq(model="openai/gpt-oss-20b", temperature= 0)

def get_llm_response(user_query: str, clean_text: str) -> dict:
    print("get llm response")

    # --- Split HTML/text into chunks for retrieval ---
    splitter = RecursiveCharacterTextSplitter(chunk_size=400, chunk_overlap=50)
    docs = splitter.split_documents([Document(page_content=clean_text)])

    embeddings = HuggingFaceEmbeddings(model_name="sentence-transformers/all-MiniLM-L6-v2")
    vectorstore = FAISS.from_documents(docs, embeddings)
    retriever = vectorstore.as_retriever(search_kwargs={"k": 2})

    # --- Prompt Template with placeholders ---
    llm_prompt = """
You are a DOM analysis assistant. 
You receive raw HTML/text of a webpage (context) and a user query about an element.

Context (HTML/text):
{context}

User Query:
{question}

Task:
- Identify the DOM element that best matches the user query.
- Return the element that contains the actual **answer value**, not just a label.
- If the page uses label/value pairs (e.g., <th>Label</th><td>Value</td> or <div><span>Label:</span><span>Value</span>):
  → Always return the value element (e.g., <td>, <span>, <div>) rather than the label.
- If the query is about prices, ratings, titles, or other standalone elements:
  → Return the element that directly contains the visible value.
- Always return ONLY valid JSON with these keys:
  - "element_text": visible text of the element (string or null, should contain the answer value if possible)
  - "tag": the HTML tag name (string or null)
  - "css_selector": a valid CSS selector for Selenium (string or null)
  - "xpath": a valid XPath for Selenium (string or null)

Rules:
- Use the most direct selector (CSS or XPath) that points to the answer element.
- Prefer stable attributes like id, class, or semantic structure.
- Do NOT include reasoning, explanations, or extra text.
- If no clear match is found, return null for all fields.

Example valid outputs:

For Wikipedia infobox (query: "birth place"):
{{
  "element_text": "Bombay (now Mumbai), Maharashtra, India",
  "tag": "td",
  "css_selector": ".infobox td",
  "xpath": "//th[text()='Born']/following-sibling::td"
}}

For Amazon product page (query: "price"):
{{
  "element_text": "$999.00",
  "tag": "span",
  "css_selector": "span#priceblock_ourprice",
  "xpath": "//span[@id='priceblock_ourprice']"
}}

For a news site (query: "headline"):
{{
  "element_text": "Apple launches iPhone 16",
  "tag": "h1",
  "css_selector": "h1.headline",
  "xpath": "//h1[@class='headline']"
}}
"""


    qa_prompt = PromptTemplate(
        input_variables=["context", "question"],
        template=llm_prompt
    )

    qa_chain = RetrievalQA.from_chain_type(
        llm=llm,
        retriever=retriever,
        chain_type="stuff",
        chain_type_kwargs={"prompt": qa_prompt},
        return_source_documents=False,
    )

    # --- Run chain ---
    try:
        result = qa_chain.invoke({"context": clean_text, "question": user_query})
        raw_answer = result.get("result", "")
    except Exception as e:
        return {"element_text": None, "tag": None, "css_selector": None, "xpath": None}

    # --- Sanitize and parse JSON ---
    try:
        cleaned = re.sub(r"^```(?:json)?|```$", "", raw_answer.strip(), flags=re.MULTILINE)
        parsed = json.loads(cleaned)
    except Exception:
        return {"element_text": None, "tag": None, "css_selector": None, "xpath": None}

    return {
        "element_text": parsed.get("element_text"),
        "tag": parsed.get("tag"),
        "css_selector": parsed.get("css_selector"),
        "xpath": parsed.get("xpath")
    }

# if __name__ == "__main__":
#     # Example HTML/text
#     sample_html = """
#     <html>
#         <body>
#             <h1>Welcome to DemoBlaze</h1>
#             <a href="/cart" id="cartur">Cart</a>
#             <button id="login2">Log In</button>
#         </body>
#     </html>
#     """

#     # Clean text (simulating what you would get from BeautifulSoup)
#     clean_text = sample_html  # you could also strip tags if you want

#     # Example query
#     query = "Cart"

#     # Call the function
#     result = get_llm_response(query, clean_text)

#     # Print the result
#     print("LLM Result:", result)