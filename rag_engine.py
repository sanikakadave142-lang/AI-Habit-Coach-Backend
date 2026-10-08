import os

from dotenv import load_dotenv
from langchain_community.document_loaders import TextLoader
from langchain_text_splitters import RecursiveCharacterTextSplitter
from langchain_google_genai import GoogleGenerativeAIEmbeddings
from langchain_community.vectorstores import Chroma

load_dotenv()

GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

if not GEMINI_API_KEY:
    raise ValueError("GEMINI_API_KEY is not configured")

KNOWLEDGE_FILE = os.path.join(
    os.path.dirname(__file__),
    "rag",
    "knowledge",
    "habit_guide.txt"
)

VECTOR_DB_PATH = os.path.join(
    os.path.dirname(__file__),
    "rag",
    "chroma_db"
)


def get_vector_store():

    embeddings = GoogleGenerativeAIEmbeddings(
        model="models/gemini-embedding-001",
        google_api_key=GEMINI_API_KEY
    )

    if os.path.exists(VECTOR_DB_PATH):
        return Chroma(
            persist_directory=VECTOR_DB_PATH,
            embedding_function=embeddings
        )

    loader = TextLoader(
        KNOWLEDGE_FILE,
        encoding="utf-8"
    )

    documents = loader.load()

    splitter = RecursiveCharacterTextSplitter(
        chunk_size=500,
        chunk_overlap=50
    )

    chunks = splitter.split_documents(documents)

    vector_store = Chroma.from_documents(
        documents=chunks,
        embedding=embeddings,
        persist_directory=VECTOR_DB_PATH
    )

    return vector_store


def search_knowledge(question: str):

    vector_store = get_vector_store()

    results = vector_store.similarity_search(
        question,
        k=3
    )

    if not results:
        return ""

    knowledge = "\n\n".join(
        document.page_content
        for document in results
    )

    return knowledge
