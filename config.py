{
  "file_extensions": [".java"],
  "model": "codeqwen:7b-chat",
  "chunk_size": 2000,
  "chunk_overlap": 200,
  "max_chunks": 10,
  "folder_prompt": "Describe the purpose and contents of the folder {folder_path} containing files {files}. Provide a general overview of what the package does and explain how things are related. Assume the reader is a software engineer who is not deeply familiar with the project and this documentation should be part of his onboarding. Provide practical examples and use cases to illustrate how to use the software. Important:  Explain not just how to use something, but why and when to use it. As a context: The project is a library that given FFT (Fault-Finding tree) dialogs express as graphml files, they need to be converted into geniOs conversational dialogs. The project should also provide API for querying the dialog nodes from the graph",
  "file_prompt": "Analyze and document the following part of a code file:\n\nFile: {file_path}\n\nContent:\n{chunk}\n\n Document all relevant parts. Include code examples where you see appropiated. The documentation should be consice and explain the responsability of the classes. Do not list all methods and explain them, rather explain class responsabilities, purpose and important domain concepts. Use clear, simple language. Avoid jargon unless necessary, and explain complex concepts thoroughly. Do not output the code. Important:  Explain not just how to use something, but why and when to use it. .\nDocumentation:",
  "combine_prompt": "Combine and summarize the following documentation chunks for file {file_path}:\n\n{chunk_docs}\n\nCombined Documentation:",
  "project_prompt": "Based on the following component documentation, provide an overall summary of the project structure and functionality:\n\n{documentation}\n\nProject Summary:"
}