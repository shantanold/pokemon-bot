import langchain
from chunker import pokemon_strategy_transcript_chunker
from langchain_openai import OpenAI
from langchain_community.document_loaders import TextLoader
from langchain_community.document_loaders import DirectoryLoader
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain_core.documents import Document
from langchain_core.vectorstores import InMemoryVectorStore
from langchain_openai import OpenAIEmbeddings
from dotenv import load_dotenv

import os


load_dotenv()
client = OpenAI(api_key=os.getenv("OPENAI_API_KEY"))
#load the pokemon strategy guide
directory_loader = DirectoryLoader("./resources", glob="**/*.txt", loader_cls=TextLoader)
documents = directory_loader.load()
loader = TextLoader("resources/how_to_win.txt")
#documents = loader.load()
#split the doc into chunks
split_docs = pokemon_strategy_transcript_chunker(documents)
# text_splitter = RecursiveCharacterTextSplitter(chunk_size=1000, chunk_overlap=10, separators=["?",".","\n","!"])
# split_docs = text_splitter.split_documents(documents)
#create an embedded vector database of the embeddings
embeddings_model = OpenAIEmbeddings(model="text-embedding-3-small")
vector_store = InMemoryVectorStore(embedding=embeddings_model)
vector_store.add_documents(split_docs)
retriever = vector_store.as_retriever()
prompt = "Speed"
dox = vector_store.similarity_search(prompt)
for d in dox:
    print(d.page_content)



#shitski = vector_store.from_embeddings(text_embeddings =list(zip(texts,embeddings)))



# response = client.chat.completions.create(
#     model="o1-mini",
#     messages=[
#         {
#             "role": "user", 
#             "content": prompt
#         }
#     ]
# )
# print(response.choices[0].message.content)

