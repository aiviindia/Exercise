import os
import logging
from flask import Flask, request, render_template, send_file
import camelot
import pandas as pd
from werkzeug.utils import secure_filename

app = Flask(__name__)

UPLOAD_FOLDER = 'uploads'
OUTPUT_FOLDER = 'output'
ALLOWED_EXTENSIONS = {'pdf'}

app.config['UPLOAD_FOLDER'] = UPLOAD_FOLDER
app.config['OUTPUT_FOLDER'] = OUTPUT_FOLDER

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

def extract_tables(filepath):
    tables = []
    try:
        logger.info("Attempting table extraction with lattice mode...")
        tables = camelot.read_pdf(filepath, pages='all', flavor='lattice')
        
        if len(tables) == 0:
            logger.info("No tables found with lattice mode. Trying stream mode...")
            tables = camelot.read_pdf(filepath, pages='all', flavor='stream')
        
        logger.info(f"Extracted {len(tables)} tables from the PDF.")
    except Exception as e:
        logger.error(f"Error during table extraction: {str(e)}")
    
    return tables

@app.route('/', methods=['GET', 'POST'])
def upload_file():
    if request.method == 'POST':
        if 'file' not in request.files:
            return 'No file part'
        file = request.files['file']
        if file.filename == '':
            return 'No selected file'
        if file and allowed_file(file.filename):
            filename = secure_filename(file.filename)
            filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
            file.save(filepath)
            
            tables = extract_tables(filepath)
            
            csv_files = []
            for i, table in enumerate(tables):
                if table.df.empty:
                    logger.warning(f"Table {i+1} is empty. Skipping...")
                    continue
                
                csv_filename = f'table_{i+1}.csv'
                csv_filepath = os.path.join(app.config['OUTPUT_FOLDER'], csv_filename)
                table.to_csv(csv_filepath, index=False)
                csv_files.append(csv_filename)
            
            if not csv_files:
                return "No tables were successfully extracted from the PDF. The file might not contain any tables, or they might not be in a format Camelot can recognize."
            
            return render_template('results.html', csv_files=csv_files)
    return render_template('upload.html')

@app.route('/download/<filename>')
def download_file(filename):
    return send_file(os.path.join(app.config['OUTPUT_FOLDER'], filename), as_attachment=True)

if __name__ == '__main__':
    os.makedirs(UPLOAD_FOLDER, exist_ok=True)
    os.makedirs(OUTPUT_FOLDER, exist_ok=True)
    app.run(debug=True)