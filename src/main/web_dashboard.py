#!/usr/bin/env python3
"""
Web Dashboard for Translation Review
Lightweight Flask-based interface for CSV review and editing
"""

import csv
import json
import os
from pathlib import Path
from datetime import datetime
from typing import Dict, List, Optional

try:
    from flask import Flask, render_template_string, request, jsonify
except ImportError:
    print("Flask not installed. Install with: pip install flask")
    Flask = None

from translate_manager import normalize_translation_text
from state_manager import StateManager, CSVStatus
from glossary_manager import GlossaryManager


class TranslationDashboard:
    """Web dashboard for translation review"""

    def __init__(
        self,
        output_dir: str,
        state_db_path: str,
        db_path: str = None,
        glossary_dir: str = None,
        port: int = 8000
    ):
        if not Flask:
            raise RuntimeError("Flask not installed. Install with: pip install flask")

        self.output_dir = Path(output_dir)
        self.state_mgr = StateManager(state_db_path)
        self.glossary_mgr = GlossaryManager(db_path, glossary_dir) if db_path else None
        self.port = port
        self.app = Flask(__name__)
        self._setup_routes()

    def _setup_routes(self):
        """Setup Flask routes"""

        @self.app.route('/')
        def index():
            """Dashboard home"""
            return self._render_index()

        @self.app.route('/api/pending-csvs')
        def get_pending_csvs():
            """Get list of pending CSVs"""
            csv_files = list(self.output_dir.glob('*.csv'))
            csv_list = []

            for csv_file in sorted(csv_files):
                try:
                    with open(csv_file, 'r', encoding='utf-8-sig', newline='') as f:
                        reader = csv.DictReader(f)
                        rows = list(reader)

                    total = len(rows)
                    translated = sum(1 for r in rows if r.get('dest_text', '').strip())
                    pct = (translated / total * 100) if total > 0 else 0

                    csv_list.append({
                        'filename': csv_file.name,
                        'path': str(csv_file),
                        'total': total,
                        'translated': translated,
                        'percent': pct
                    })
                except Exception as e:
                    print(f"Error reading {csv_file}: {e}")

            csv_list.sort(key=lambda x: x['percent'], reverse=True)
            return jsonify(csv_list)

        @self.app.route('/api/csv/<filename>')
        def get_csv(filename):
            """Get CSV file contents"""
            csv_path = self.output_dir / filename
            if not csv_path.exists():
                return jsonify({'error': 'File not found'}), 404

            try:
                with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
                    reader = csv.DictReader(f)
                    rows = []
                    for idx, row in enumerate(reader, start=2):
                        rows.append({
                            'line': idx,
                            **row
                        })

                return jsonify(rows)
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/csv/<filename>/row/<int:line>', methods=['POST'])
        def update_csv_row(filename, line):
            """Update a single CSV row"""
            csv_path = self.output_dir / filename
            if not csv_path.exists():
                return jsonify({'error': 'File not found'}), 404

            try:
                data = request.json
                dest_text = data.get('dest_text', '').strip()

                # Read CSV
                with open(csv_path, 'r', encoding='utf-8-sig', newline='') as f:
                    rows = list(csv.DictReader(f))

                # Update row (line is 1-indexed from header, rows are 0-indexed)
                if 0 <= line - 2 < len(rows):
                    rows[line - 2]['dest_text'] = dest_text

                # Write back
                if rows:
                    fieldnames = list(rows[0].keys())
                    with open(csv_path, 'w', encoding='utf-8', newline='') as f:
                        writer = csv.DictWriter(f, fieldnames=fieldnames)
                        writer.writeheader()
                        writer.writerows(rows)

                    return jsonify({'success': True})

                return jsonify({'error': 'Empty CSV'}), 400
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/glossary/<lang>')
        def get_glossary(lang):
            """Get glossary for language"""
            if not self.glossary_mgr:
                return jsonify({'error': 'Glossary not available'}), 501

            try:
                glossary = self.glossary_mgr.load_glossary_json(
                    f"{self.glossary_mgr.glossary_dir}/translation_glossary_{lang}.json"
                )
                entries = [
                    {'source': k, 'target': v}
                    for k, v in list(glossary.items())[:50]
                ]
                return jsonify(entries)
            except Exception as e:
                return jsonify({'error': str(e)}), 500

        @self.app.route('/api/status')
        def get_status():
            """Get translation status"""
            summary = self.state_mgr.get_status_summary()
            return jsonify(summary)

    def _render_index(self) -> str:
        """Render dashboard HTML"""
        html = """
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Translation Dashboard</title>
    <style>
        * { margin: 0; padding: 0; box-sizing: border-box; }
        body { font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background: #f5f5f5; }
        .container { max-width: 1200px; margin: 0 auto; padding: 20px; }
        header { background: #2c3e50; color: white; padding: 20px; border-radius: 4px; margin-bottom: 30px; }
        h1 { font-size: 24px; margin-bottom: 10px; }
        .tabs { display: flex; gap: 10px; margin-bottom: 20px; border-bottom: 2px solid #ddd; }
        .tab-btn { padding: 12px 20px; background: none; border: none; cursor: pointer; font-size: 14px; color: #666; border-bottom: 3px solid transparent; transition: all 0.2s; }
        .tab-btn.active { color: #2c3e50; border-bottom-color: #2c3e50; }
        .tab-content { display: none; }
        .tab-content.active { display: block; }
        .csv-list { display: grid; gap: 15px; }
        .csv-item { background: white; padding: 20px; border-radius: 4px; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }
        .csv-item h3 { font-size: 16px; margin-bottom: 10px; }
        .progress { width: 100%; height: 8px; background: #eee; border-radius: 4px; overflow: hidden; }
        .progress-bar { height: 100%; background: #27ae60; transition: width 0.3s; }
        .progress-text { font-size: 12px; color: #666; margin-top: 5px; }
        .csv-editor { display: none; margin-top: 20px; }
        .csv-editor.active { display: block; }
        table { width: 100%; border-collapse: collapse; background: white; }
        th, td { padding: 12px; text-align: left; border-bottom: 1px solid #ddd; }
        th { background: #f5f5f5; font-weight: 600; }
        tr:hover { background: #fafafa; }
        textarea { width: 100%; padding: 8px; border: 1px solid #ddd; border-radius: 4px; font-family: monospace; font-size: 12px; resize: vertical; }
        button { padding: 8px 16px; background: #3498db; color: white; border: none; border-radius: 4px; cursor: pointer; font-size: 13px; }
        button:hover { background: #2980b9; }
        .status-badge { display: inline-block; padding: 4px 8px; border-radius: 3px; font-size: 11px; font-weight: 600; }
        .status-pass { background: #d4edda; color: #155724; }
        .status-fail { background: #f8d7da; color: #721c24; }
        .glossary-list { display: grid; gap: 10px; }
        .glossary-entry { background: white; padding: 15px; border-radius: 4px; border-left: 3px solid #3498db; }
        .glossary-entry .source { font-weight: 600; color: #2c3e50; }
        .glossary-entry .target { color: #666; font-size: 14px; }
    </style>
</head>
<body>
    <div class="container">
        <header>
            <h1>Translation Dashboard</h1>
            <p>Review and edit translations before import</p>
        </header>

        <div class="tabs">
            <button class="tab-btn active" onclick="switchTab('review')">Review CSVs</button>
            <button class="tab-btn" onclick="switchTab('glossary')">Glossary</button>
            <button class="tab-btn" onclick="switchTab('status')">Status</button>
        </div>

        <!-- Review Tab -->
        <div id="review" class="tab-content active">
            <h2>Pending Translations</h2>
            <p style="color: #666; margin-bottom: 20px;">Click a file to review and edit translations</p>
            <div class="csv-list" id="csv-list"></div>
            <div class="csv-editor" id="csv-editor">
                <button onclick="closeEditor()">Close Editor</button>
                <table id="csv-table"></table>
            </div>
        </div>

        <!-- Glossary Tab -->
        <div id="glossary" class="tab-content">
            <h2>Glossaries</h2>
            <p style="color: #666; margin-bottom: 20px;">Pre-populated translations for common terms</p>
            <div id="glossary-list"></div>
        </div>

        <!-- Status Tab -->
        <div id="status" class="tab-content">
            <h2>Pipeline Status</h2>
            <div id="status-info" style="background: white; padding: 20px; border-radius: 4px;"></div>
        </div>
    </div>

    <script>
        function switchTab(tabName) {
            document.querySelectorAll('.tab-content').forEach(el => el.classList.remove('active'));
            document.querySelectorAll('.tab-btn').forEach(el => el.classList.remove('active'));
            document.getElementById(tabName).classList.add('active');
            event.target.classList.add('active');

            if (tabName === 'review') loadPendingCSVs();
            else if (tabName === 'glossary') loadGlossaries();
            else if (tabName === 'status') loadStatus();
        }

        function loadPendingCSVs() {
            fetch('/api/pending-csvs')
                .then(r => r.json())
                .then(csvs => {
                    const html = csvs.map(csv => `
                        <div class="csv-item">
                            <h3 onclick="viewCSV('${csv.filename}')" style="cursor: pointer; color: #3498db;">
                                📄 ${csv.filename}
                            </h3>
                            <div class="progress">
                                <div class="progress-bar" style="width: ${csv.percent}%"></div>
                            </div>
                            <div class="progress-text">${csv.translated}/${csv.total} (${csv.percent.toFixed(1)}%)</div>
                        </div>
                    `).join('');
                    document.getElementById('csv-list').innerHTML = html;
                });
        }

        function viewCSV(filename) {
            fetch(`/api/csv/${filename}`)
                .then(r => r.json())
                .then(rows => {
                    const table = document.getElementById('csv-table');
                    table.innerHTML = `
                        <tr>
                            <th>#</th>
                            <th>Source</th>
                            <th>Destination</th>
                            <th>Context</th>
                            <th>Action</th>
                        </tr>
                    ` + rows.map(row => `
                        <tr>
                            <td>${row.line}</td>
                            <td><small>${(row.source_text || '').substring(0, 60)}</small></td>
                            <td>
                                <textarea rows="2" id="dest_${row.line}" onchange="saveRow('${filename}', ${row.line}, this.value)">
                                    ${row.dest_text || ''}
                                </textarea>
                            </td>
                            <td><small>${row.context || '-'}</small></td>
                            <td>${row.dest_text ? '✓' : '◯'}</td>
                        </tr>
                    `).join('');
                    document.getElementById('csv-editor').classList.add('active');
                });
        }

        function closeEditor() {
            document.getElementById('csv-editor').classList.remove('active');
            loadPendingCSVs();
        }

        function saveRow(filename, line, value) {
            fetch(`/api/csv/${filename}/row/${line}`, {
                method: 'POST',
                headers: { 'Content-Type': 'application/json' },
                body: JSON.stringify({ dest_text: value })
            }).then(r => r.json()).then(data => {
                if (data.success) console.log('Saved');
            });
        }

        function loadGlossaries() {
            const langs = ['es', 'pt'];
            let html = '';
            Promise.all(langs.map(lang =>
                fetch(`/api/glossary/${lang}`)
                    .then(r => r.json())
                    .then(entries => {
                        html += `<h3>${lang.toUpperCase()}</h3><div class="glossary-list">` +
                            entries.map(e => `
                                <div class="glossary-entry">
                                    <div class="source">${e.source}</div>
                                    <div class="target">→ ${e.target}</div>
                                </div>
                            `).join('') + '</div>';
                    })
            )).then(() => {
                document.getElementById('glossary-list').innerHTML = html;
            });
        }

        function loadStatus() {
            fetch('/api/status')
                .then(r => r.json())
                .then(status => {
                    const html = `
                        <p><strong>Batches Pending Extract:</strong> ${status.batches_PENDING_EXTRACT || 0}</p>
                        <p><strong>Batches Pending Review:</strong> ${status.batches_PENDING_REVIEW || 0}</p>
                        <p><strong>Batches Imported:</strong> ${status.batches_IMPORTED || 0}</p>
                        <p><strong>Generated Files (ES):</strong> ${status.generated_es_pass || 0} passed</p>
                        <p><strong>Generated Files (PT):</strong> ${status.generated_pt_pass || 0} passed</p>
                    `;
                    document.getElementById('status-info').innerHTML = html;
                });
        }

        loadPendingCSVs();
    </script>
</body>
</html>
        """
        return html

    def run(self, debug: bool = False):
        """Start the web server"""
        print(f"\n{'=' * 60}")
        print(f"Translation Dashboard starting on http://localhost:{self.port}")
        print(f"Open your browser and navigate to http://localhost:{self.port}")
        print(f"Press Ctrl+C to stop")
        print(f"{'=' * 60}\n")

        try:
            self.app.run(host='localhost', port=self.port, debug=debug, use_reloader=False)
        except KeyboardInterrupt:
            print("\n\nDashboard stopped.")

    def close(self):
        """Close resources"""
        self.state_mgr.close()
        if self.glossary_mgr:
            self.glossary_mgr.close()
