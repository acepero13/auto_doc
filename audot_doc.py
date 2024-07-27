import os
import json
import pickle
from git import Repo
from langchain.llms import Ollama
from langchain.text_splitter import RecursiveCharacterTextSplitter
from langchain.chains import LLMChain
from langchain.prompts import PromptTemplate
from langchain.docstore.document import Document
from langchain.chains.summarize import load_summarize_chain
from langchain.embeddings import HuggingFaceEmbeddings
from langchain.vectorstores import FAISS

class ContextManager:
    def __init__(self, llm, save_dir):
        self.llm = llm
        self.save_dir = save_dir
        self.embeddings = HuggingFaceEmbeddings()
        self.vector_store = FAISS.from_texts(["Initial context"], embedding=self.embeddings)
        self.context_summary = "Initial project context."

    def update_context(self, new_content, content_type):
        self.vector_store.add_texts([new_content])
        update_prompt = PromptTemplate(
            input_variables=["current_summary", "new_content", "content_type"],
            template="Current project summary: {current_summary}\n\nNew {content_type} content: {new_content}\n\nUpdate the project summary to incorporate this new information:"
        )
        update_chain = LLMChain(llm=self.llm, prompt=update_prompt)
        self.context_summary = update_chain.run(current_summary=self.context_summary, new_content=new_content, content_type=content_type)

    def get_relevant_context(self, query, k=3):
        relevant_docs = self.vector_store.similarity_search(query, k=k)
        return "\n".join([doc.page_content for doc in relevant_docs])

    def save_state(self):
        with open(os.path.join(self.save_dir, 'context_manager.pkl'), 'wb') as f:
            pickle.dump({
                'vector_store': self.vector_store,
                'context_summary': self.context_summary
            }, f)

    def load_state(self):
        state_file = os.path.join(self.save_dir, 'context_manager.pkl')
        if os.path.exists(state_file):
            with open(state_file, 'rb') as f:
                state = pickle.load(f)
                self.vector_store = state['vector_store']
                self.context_summary = state['context_summary']
            return True
        return False

class CodebaseAnalyzer:
    def __init__(self, repo_path, config_path, save_dir):
        self.repo_path = repo_path
        self.repo = Repo(repo_path)
        self.config = self.load_config(config_path)
        self.save_dir = save_dir
        os.makedirs(save_dir, exist_ok=True)
        self.llm = Ollama(model=self.config.get('model', 'qwen:7b'))
        self.text_splitter = RecursiveCharacterTextSplitter(
            chunk_size=self.config.get('chunk_size', 2000),
            chunk_overlap=self.config.get('chunk_overlap', 200),
            length_function=len,
        )
        self.context_manager = ContextManager(self.llm, save_dir)
        self.documentation = {}
        self.skip_folders = self.config.get('skip_folders', [])

    def load_config(self, config_path):
        with open(config_path, 'r') as f:
            return json.load(f)

    def save_progress(self):
        with open(os.path.join(self.save_dir, 'documentation.json'), 'w') as f:
            json.dump(self.documentation, f)
        self.context_manager.save_state()

    def load_progress(self):
        doc_file = os.path.join(self.save_dir, 'documentation.json')
        if os.path.exists(doc_file):
            with open(doc_file, 'r') as f:
                self.documentation = json.load(f)
            self.context_manager.load_state()
            return True
        return False

    def should_skip_folder(self, folder_path):
        return any(skip_folder in folder_path for skip_folder in self.skip_folders)

    def analyze_codebase(self):
        if self.load_progress():
            print("Resuming from previous analysis...")
        else:
            print("Starting new analysis...")

        for root, dirs, files in os.walk(self.repo_path):
            if '.git' in dirs:
                dirs.remove('.git')
            
            relative_path = os.path.relpath(root, self.repo_path)
            
            if self.should_skip_folder(relative_path):
                print(f"Skipping folder: {relative_path}")
                dirs[:] = []  # This prevents os.walk from recursing into subfolders
                continue

            if 'src/test' in relative_path or 'src\\test' in relative_path: # skip test folders
                continue
            
            if relative_path not in self.documentation:
                if len(files) == 0:
                    continue
                folder_doc = self.analyze_folder(relative_path, files)
                self.documentation[relative_path] = folder_doc
                self.context_manager.update_context(folder_doc, "folder")
                print(f"Analyzed folder: {relative_path}")
                print(f"Folder documentation:\n{folder_doc}\n")
                self.save_progress()
            
            for file in files:
                if self.should_analyze_file(file):
                    file_path = os.path.join(relative_path, file)
                    if file_path not in self.documentation:
                        file_doc = self.analyze_file(file_path)
                        self.documentation[file_path] = file_doc
                        self.context_manager.update_context(file_doc, "file")
                        print(f"Analyzed file: {file_path}")
                        print(f"File documentation:\n{file_doc}\n")
                        self.save_progress()
        
        return self.documentation

    def should_analyze_file(self, file_name):
        return any(file_name.endswith(ext) for ext in self.config['file_extensions'])

    def analyze_folder(self, folder_path, files):
    
        files_to_analyze = [f for f in files if self.should_analyze_file(f)]
        if len(files_to_analyze) == 0:
            return ""
        relevant_context = self.context_manager.get_relevant_context(folder_path)
        prompt = PromptTemplate(
            input_variables=["folder_path", "files", "context"],
            template=self.config.get('folder_prompt', "Given the following context:\n{context}\n\nDescribe the purpose and contents of the folder {folder_path} containing files {files}. Also, explain how this folder might relate to other parts of the project:")
        )
        chain = LLMChain(llm=self.llm, prompt=prompt)
        return chain.run(folder_path=folder_path, files=', '.join(files_to_analyze), context=relevant_context)

    def analyze_file(self, file_path):
        with open(os.path.join(self.repo_path, file_path), 'r') as file:
            content = file.read()
        
        chunks = self.text_splitter.split_text(content)
        
        if len(chunks) > self.config.get('max_chunks', 10):
            return self.analyze_large_file(file_path, chunks)
        
        relevant_context = self.context_manager.get_relevant_context(file_path)
        prompt = PromptTemplate(
            input_variables=["file_path", "chunk", "context"],
            template=self.config.get('file_prompt', "Given the following context:\n{context}\n\nAnalyze and document the following part of a code file:\n\nFile: {file_path}\n\nContent:\n{chunk}\n\nProvide documentation and explain how this file might relate to other parts of the project:")
        )
        chain = LLMChain(llm=self.llm, prompt=prompt)
        
        chunk_docs = []
        for i, chunk in enumerate(chunks):
            chunk_doc = chain.run(file_path=file_path, chunk=chunk, context=relevant_context)
            chunk_docs.append(chunk_doc)
            print(f"Analyzed chunk {i+1}/{len(chunks)} of file {file_path}")
            print(f"Chunk documentation:\n{chunk_doc}\n")
        
        combined_prompt = PromptTemplate(
            input_variables=["file_path", "chunk_docs", "context"],
            template=self.config.get('combine_prompt', "Given the following context:\n{context}\n\nCombine and summarize the following documentation chunks for file {file_path}:\n\n{chunk_docs}\n\nProvide a comprehensive documentation including relationships to other project components:")
        )
        combined_chain = LLMChain(llm=self.llm, prompt=combined_prompt)
        return combined_chain.run(file_path=file_path, chunk_docs="\n\n".join(chunk_docs), context=relevant_context)

    def analyze_large_file(self, file_path, chunks):
        docs = [Document(page_content=chunk, metadata={"source": file_path}) for chunk in chunks]
        chain = load_summarize_chain(self.llm, chain_type="map_reduce")
        summary = chain.run(docs)
        print(f"Generated summary for large file: {file_path}")
        print(f"Summary:\n{summary}\n")
        
        relevant_context = self.context_manager.get_relevant_context(file_path)
        relationship_prompt = PromptTemplate(
            input_variables=["file_path", "summary", "context"],
            template="Given the following context:\n{context}\n\nFor the large file {file_path} with summary:\n{summary}\n\nExplain how this file might relate to other parts of the project:"
        )
        relationship_chain = LLMChain(llm=self.llm, prompt=relationship_prompt)
        relationships = relationship_chain.run(file_path=file_path, summary=summary, context=relevant_context)
        print(f"Generated relationships for large file: {file_path}")
        print(f"Relationships:\n{relationships}\n")
        
        return f"Large file summary for {file_path}:\n{summary}\n\nRelationships:\n{relationships}"

    def generate_documentation(self):
        documentation = self.analyze_codebase()
        
        project_prompt = PromptTemplate(
            input_variables=["documentation", "context_summary"],
            template=self.config.get('project_prompt', "Based on the following component documentation and overall context summary, provide a comprehensive overview of the project structure, functionality, and component relationships:\n\nContext Summary: {context_summary}\n\nComponent Documentation: {documentation}\n\nProject Overview:")
        )
        project_chain = LLMChain(llm=self.llm, prompt=project_prompt)
        project_summary = project_chain.run(documentation=str(documentation), context_summary=self.context_manager.context_summary)
        
        print("Generated overall project summary")
        print(f"Project Summary:\n{project_summary}\n")
        
        return {
            "project_summary": project_summary,
            "component_documentation": documentation
        }

# Usage example
if __name__ == "__main__":
    repo_path = "/home/acepero13/projects/java/cca-conversation-generation-library"
    config_path = "/home/acepero13/projects/autodoc/autodoc_python/config.py"
    save_dir = "/home/acepero13/projects/autodoc/autodoc_python/doc"
    
    analyzer = CodebaseAnalyzer(repo_path, config_path, save_dir)
    documentation = analyzer.generate_documentation()
    
    print("Analysis complete. Full documentation:")
    print(documentation["project_summary"])
    for component, doc in documentation["component_documentation"].items():
        print(f"\n{component}:\n{doc}")