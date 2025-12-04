#!/usr/bin/env python3
"""
Domain Adapter Service
"""
import sys
import os
sys.path.insert(0, '/aiengine/src/aiengine')

from flask import Flask, jsonify
import logging

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('DomainAdapter')

@app.route('/api/status')
def status():
    return jsonify({'status': 'running', 'service': 'domain-adapter'})

@app.route('/api/domains')
def domains():
    return jsonify({
        'supported_domains': [
            'infrastructure', 'finance', 'healthcare',
            'natural_language', 'computer_vision', 'manufacturing'
        ]
    })

if __name__ == '__main__':
    logger.info("🚀 Starting Domain Adapter on port 8083")
    app.run(host='0.0.0.0', port=8083, debug=False)
