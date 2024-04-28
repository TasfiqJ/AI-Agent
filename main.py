from llama_index.llms.ollama import Ollama
from llama_parse import LlamaParse
from llama_index.core import VectorStoreIndex, SimpleDirectoryReader, PromptTemplate
from dotenv import load_dotenv
from llama_index.core.tools import QueryEngineTool, ToolMetadata
from llama_index.core.agent import ReActAgent

load_dotenv()

llm = Ollama(model="mistral", request_timeout=30.0)

parser = LlamaParse(result_type="markdown")

file_extractor = {".pdf": parser}
documents = SimpleDirectoryReader("./data", file_extractor=file_extractor).load_data()

embed_model = resolve_embed_model("local:BAAI/bge-m3")
vector_index = VectorStoreIndex.from_documents(documents, embed_model=embed_model)
query_engine = vector_index.as_query_engine(llm=llm)

# result = query_engine.query("What are some of the routes in the api?")
# print(result)

tools = [
    QueryEngineTool(
        query_engine=query_engine,
        metadata=ToolMetadata(
            name="api_documentation",
            description="this gives documentation about code for an API. Use this for reading docs for the API",
        ),
    ),
    code_reader,
]

code_llm = Ollama(model="codellama")
agent = ReActAgent.from_tools(tools, llm=code_llm, verbose=True, context=context)

while (prompt := input("Enter a prompt (q to quit): ")) != "q":
    result = agent.query(prompt)
    print(result)
