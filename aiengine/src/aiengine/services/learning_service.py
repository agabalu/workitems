#!/usr/bin/env python3
"""
Learning Engine Service
"""
import sys
import os
sys.path.insert(0, '/aiengine/src/aiengine')

from flask import Flask, jsonify
import logging
import time

app = Flask(__name__)
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger('LearningEngine')

# Simple learning metrics
learning_stats = {
    'total_learning_iterations': 0,
    'models_trained': 0,
    'accuracy_improvements': 0,
    'last_training': None
}

@app.route('/api/status')
def status():
    return jsonify({
        'status': 'running',
        'service': 'learning-engine',
        'stats': learning_stats
    })

@app.route('/api/learn', methods=['POST'])
def trigger_learning():
    learning_stats['total_learning_iterations'] += 1
    learning_stats['last_training'] = time.time()
    logger.info("🧠 Learning iteration triggered")
    return jsonify({'status': 'learning_triggered', 'iteration': learning_stats['total_learning_iterations']})

@app.route('/api/stats')
def get_stats():
    return jsonify(learning_stats)

if __name__ == '__main__':
    logger.info("🚀 Starting Learning Engine on port 8877")
    app.run(host='0.0.0.0', port=8877, debug=False)
