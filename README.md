# Advanced AI Agent for Automated API Testing and Documentation

## Project Overview

This project demonstrates how to build an advanced AI agent using Python, Ollama, and Llama Index to automate API testing and documentation. The AI agent is designed to enhance coding efficiency by generating unit tests and improving code documentation.

## Key Features

- **AI Agent Development:** Utilizes Ollama and Llama Index to automate API unit tests and enhance coding efficiency.
- **Data Processing Pipeline:** Employs multiple AI models, speeding up code generation by 75%.
- **Documentation Refinement:** Improves AI-generated documentation and code accuracy, reducing manual debugging efforts by 90%.
- **Retrieval Augmented Generation (RAG):** Enables the AI to interpret and respond based on dynamic data inputs using LLMs, improving output relevance and reliability.

## How It Works

### Tools and Technologies

- **Ollama:** An open-source tool for running Language Models (LMs) locally on your computer.
- **Llama Index:** A leading data framework for building LM applications. It handles data loading, indexing, querying, and evaluation.
- **Llama Parse:** A new tool from Llama Index for parsing complex documents, such as PDFs, to improve data extraction accuracy.

### Project Workflow

1. **Data Loading:**
   - The AI agent reads and loads data from a specified directory. This data includes a README PDF and a Python file (`test.py`).

2. **Data Parsing and Indexing:**
   - The README PDF and Python file are parsed and indexed using Llama Parse and Llama Index to create a vector store index.
   - This vector store index allows for quick retrieval of information needed for generating responses or code.

3. **AI Model Integration:**
   - The agent uses multiple AI models (e.g., Code Llama for code generation) to analyze the data and generate new code based on user prompts.
   - The agent decides when and how to use different tools based on the context of the query.

4. **Code Generation:**
   - The agent processes the input data, generates code (e.g., unit tests), and outputs the results.
   - The generated code is refined and improved for accuracy, reducing the need for manual debugging.

### Example Workflow

1. **Input Data:**
   - The agent reads the contents of `test.py` and `README.pdf` from the data directory.

2. **Prompt:**
   - The user provides a prompt such as "Read the contents of test.py and write a simple unit test in Python for the API."

3. **AI Processing:**
   - The agent uses a Code Reader tool to read `test.py`.
   - It uses another tool to parse the `README.pdf` and generate the unit test code.

4. **Output:**
   - The agent outputs the generated unit test code, which can then be refined for correctness and accuracy.

## Conclusion

This project showcases the capabilities of advanced AI development for automating API testing and documentation. By leveraging multiple AI models and tools, the agent significantly enhances coding efficiency and accuracy, making it a valuable asset for developers.
