from flask import Flask, request, render_template, send_file
from werkzeug.utils import secure_filename
import os
import tempfile
import PyPDF2
import cv2
import pytesseract
import camelot
import pandas as pd
from PIL import Image
import numpy as np
from langchain_community.llms import OpenAI
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

app = Flask(__name__)

#os.environ["OPENAI_API_KEY"] = "api-key"

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part'
        file = request.files['file']
        if file.filename == '':
            return 'No selected file'
        if file and file.filename.endswith('.pdf'):
            filename = secure_filename(file.filename)
            with tempfile.NamedTemporaryFile(delete=False, suffix='.pdf') as temp_file:
                file.save(temp_file.name)
                tables = extract_tables(temp_file.name)
            os.unlink(temp_file.name)
            csv_files = save_tables_as_csv(tables)
            return render_template('download.html', csv_files=csv_files)
    return render_template('upload.html')

def extract_tables(pdf_path):
    tables = []
    
    camelot_tables = camelot.read_pdf(pdf_path, pages='all', flavor='stream')
    for table in camelot_tables:
        tables.append(table.df)
    
    if not tables:
        pdf = PyPDF2.PdfReader(pdf_path)
        for page_num in range(len(pdf.pages)):
            page = pdf.pages[page_num]
            if '/XObject' in page['/Resources']:
                xObject = page['/Resources']['/XObject'].get_object()
                for obj in xObject:
                    if xObject[obj]['/Subtype'] == '/Image':
                        size = (xObject[obj]['/Width'], xObject[obj]['/Height'])
                        data = xObject[obj].get_data()
                        img = Image.frombytes('RGB', size, data)
                        img_cv = cv2.cvtColor(np.array(img), cv2.COLOR_RGB2BGR)
                        
                        text = pytesseract.image_to_string(img_cv)
                        
                        llm = OpenAI(temperature=0)
                        prompt = PromptTemplate(
                            input_variables=["text"],
                            template="Extract all tables from the following text and format them as CSV:\n\n{text}"
                        )
                        chain = LLMChain(llm=llm, prompt=prompt)
                        result = chain.run(text)
                        
                        for table_str in result.split('\n\n'):
                            if table_str.strip():
                                df = pd.read_csv(pd.compat.StringIO(table_str))
                                tables.append(df)
    
    return tables

def save_tables_as_csv(tables):
    csv_files = []
    for i, table in enumerate(tables):
        csv_filename = f'table_{i+1}.csv'
        table.to_csv(csv_filename, index=False)
        csv_files.append(csv_filename)
    return csv_files

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(filename, as_attachment=True)

if __name__ == '__main__':
    app.run(debug=True)