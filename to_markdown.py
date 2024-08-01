import json
import os
FILE = "doc/documentation.json"
def json_to_markdown(json_data):
    markdown_content = ""
    
    for key, value in json_data.items():
        # Extract the file name from the key
        file_name = os.path.basename(key)
        
        # Create the header
        markdown_content += f"## {file_name}\n\n"
        
        # Add the content
        markdown_content += f"{value}\n\n"
    
    return markdown_content

# Assuming your JSON data is stored in a file called 'data.json'
with open(FILE, 'r') as json_file:
    data = json.load(json_file)

markdown_output = json_to_markdown(data)

# Write the markdown content to a file
with open('output.md', 'w') as md_file:
    md_file.write(markdown_output)

print("Markdown file 'output.md' has been generated successfully.")