from flask import Flask, render_template, jsonify, send_from_directory
import os
import json
import glob

app = Flask(__name__, template_folder='.')

# Root directory for results
RESULTS_DIR = os.path.abspath(os.path.join(os.path.dirname(__file__), '../../../../'))

@app.route('/')
def index():
    return render_template('dashboard.html')

@app.route('/api/results')
def list_results():
    """List all emulsion result JSON files"""
    files = glob.glob(os.path.join(RESULTS_DIR, 'emulsion_*.json'))
    results = []
    for f in files:
        results.append({
            'filename': os.path.basename(f),
            'timestamp': os.path.getmtime(f)
        })
    # Sort by timestamp descending
    results.sort(key=lambda x: x['timestamp'], reverse=True)
    return jsonify(results)

@app.route('/api/results/<filename>')
def get_result(filename):
    """Get content of a specific result file"""
    # Security check: ensure filename is just a filename
    filename = os.path.basename(filename)
    filepath = os.path.join(RESULTS_DIR, filename)
    
    if not os.path.exists(filepath):
        return jsonify({'error': 'File not found'}), 404
        
    with open(filepath, 'r') as f:
        return jsonify(json.load(f))

if __name__ == '__main__':
    print("\n" + "="*50)
    print("EdgeWatch Emulsion Dashboard")
    print("URL: http://localhost:5005")
    print("="*50 + "\n")
    app.run(host='0.0.0.0', port=5005, debug=True)
